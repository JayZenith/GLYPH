# SFT → RLVR for a Rust tool-use agent: where supervised learning ends and RL begins

Teaching `Qwen3-4B-Base` to be a coding agent on real Rust tasks led to experiments regarding — *how much can reinforcement learning add on top of a good SFT model, and how do you tell before you burn the GPUs?*

The short version: SFT taught the protocol and the skill cleanly. The first RL runs after that **regressed** it. That was not a useless failure: it exposed exactly where RLVR has no gradient and where our eval harnesses were measuring different things. The final run only worked after we stopped asking RL to fix everything, used `pass@k` to find the few prompts where the policy already had partial capability, tightened the reward/anchor, fixed the training stack, and evaluated the checkpoint on the same vLLM harness as the baseline. On that narrow 8-prompt band, step 25 moved **47/64 → 54/64** solves.

Then the last check landed: the same checkpoint was run on the original 69-prompt HF/Transformers formal eval. It regressed badly: **52/69 → 19/69 valid traces** and **68/69 → 47/69 terminal tool successes**. So the final result is not "I trained a better deployable agent." It is narrower and more honest: RLVR can improve a carefully selected mixed pass@k band, but this full-parameter GRPO run still damaged the broader tool-protocol distribution.

The model speaks a tiny tool-use protocol:

```bash
assistant ->  CALL read_file {"id":"c1","file_path":"src/lib.rs"}
tool      ->  RESULT c1: status: success  stdout: ...
assistant ->  CALL apply_patch {"id":"c2","file_path":"...","find":"...","replace":"..."}
tool      ->  RESULT c2: status: success  stdout: patch applied
assistant ->  CALL cargo_run {"id":"c3","project_path":"."}
tool      ->  RESULT c3: status: success  stdout: ada:4,bob:2,cy:8
assistant ->  FINAL: patched the filter pipeline; stdout now matches.
```

Tools execute **for real** against sandboxed crates. `cargo_run` only counts as success if stdout exactly matches the oracle; `cargo_test` only if the tests pass. There is no reward model to fool.

---

## 1. The stack: PRIME-RL and `verifiers`, in plain terms

Because the whole project runs on [PRIME-RL](https://github.com/PrimeIntellect-ai/prime-rl)
and [`verifiers`](https://github.com/PrimeIntellect-ai/verifiers), here's the mental model you need before any of the results make sense.

### `verifiers` — the environment/reward interface that PRIME-RL consumes to run RL 

`verifiers` is the library that defines *what a rollout is* and *how it's scored*. Two pieces matter:

- **`MultiTurnEnv`** — a multi-turn environment. To create one, you implement two methods:
  - `env_response(messages, state)` — given what the model just produced, it parses `CALL ...`, creates/reuses a sandbox, rewrites paths into that sandbox, **executes the real Rust/cargo tool**, and hands back a `RESULT` block as the tool turn.
  - `is_completed(state)` — decide when the episode/rollout ends (no pending calls left, or the tool-round budget is exhausted).
- **`Rubric`** — a weighted collection of reward functions, each with a weight. The episode/rollout scalar reward is the weighted sum. Ours has exactly one: `_rust_tool_reward` at weight 1.0 which looks at trajectory and scores things like valid structure, malformed CALL syntax, and real cargo_test/cargo_run success. 

Our custom Rust/cargo environment, `rl/task_trace.py::RustToolEnv`, subclasses `MultiTurnEnv`. The loop is exactly the protocol above: model emits `CALL` → `env_response` copies the crate into a fresh per-rollout sandbox, runs the real tool, formats the `RESULT` → repeat until no pending calls left or tool-round cap is reached. In successful trajectories, the model emits a `FINAL` response.

```python
class RustToolEnv(vf.MultiTurnEnv):
    async def env_response(self, messages, state):
        calls = parse_call_blocks(latest_assistant(state))      # CALL tool {...}
        result = execute_rust_tool(self.executor, call.tool, call.params)  # real cargo
        return [{"role": "tool", "content": format_result_block(call.id, result)}]

    async def is_completed(self, state):
        return no_pending_calls(state) or rounds_used >= self.max_tool_rounds

rubric = vf.Rubric(parser=parser)
rubric.add_reward_func(_rust_tool_reward, weight=1.0)   # one scalar per rollout
```

This is **RLVR** — *RL with Verifiable Rewards*. The reward isn't a learned preference model; it's the ground-truth output of a verifier (tests pass / stdout matches). That makes the signal hard to game, but **sparse and binary**: most rollouts receive either a large success reward or nothing. Hold that thought — it's the whole story later.

### PRIME-RL — the asynchronous training loop

PRIME-RL splits RL into three processes that run concurrently, talking over the
filesystem:

```
                 weights (checkpoint/weight sync via filesystem)
   ┌──────────┐  ───────────────────────────►  ┌─────────────┐
   │ TRAINER  │                                 │  INFERENCE  │  vLLM, serves
   │ (FSDP,   │                                 │  (policy)   │  the current policy
   │  GRPO)   │  ◄───────────────────────────   └─────────────┘
   └──────────┘   training batches (rollouts)          │ generates rollouts
        ▲                                              ▼
        │                                        ┌──────────────┐
        │                                        │ ORCHESTRATOR │  runs the verifiers
        └──── KL anchor ◄──── ┌─────────┐        │  env, scores │  env, applies the
                              │ TEACHER │ ◄───── │  & filters   │  rubric, filters
                              │ (frozen │        └──────────────┘
                              │  vLLM)  │
                              └─────────┘
```

- **Orchestrator** drives the `verifiers` environment: it asks the inference engine for
  completions, runs the multi-turn tool loop, scores each rollout with the rubric, and
  assembles training batches. It also runs the **rollout filters**.
- **Trainer** does the policy-gradient update (GRPO) under FSDP, then **broadcasts the
  new weights** to the inference engine so the next rollouts are on-policy.
- **Inference** is a vLLM server holding the current policy.
- **Teacher** is a second, *frozen* vLLM server (here it's SFT_V1 itself). The trainer
  adds a KL penalty pulling the policy toward the teacher's distribution — the **anchor**
  that stops RL from wandering off a cliff.

### GRPO and the zero-advantage filter (the load-bearing concept)

PRIME-RL uses **GRPO** (Group Relative Policy Optimization). For each prompt it samples a
*group* of `G` rollouts (we used 8, then 16), scores each, and computes the advantage of
rollout *i* by normalizing within its own group:

```
A_i = (r_i − mean(r_group)) / std(r_group)
```

No value network — the group's own mean is the baseline. This has a brutal consequence:

> **If every rollout in a group gets the same reward, `std = 0`, every advantage is 0,
> and the group contributes no gradient.**

PRIME-RL makes this explicit with the **`zero_advantage` filter** (enforced in
`rl/configs/task_trace/orchestrator.toml`): groups where all rollouts scored identically
are dropped before the trainer ever sees them. This is efficient — but it also means
**a prompt the model already solves every time, or fails every time, teaches RL nothing.**
The only prompts that produce a gradient are the ones with *within-group variance*: some
rollouts pass, some don't. Remember this; it is the entire reason this project ended the
way it did.

---

## 2. SFT: teaching the protocol works

SFT_V1 is `Qwen3-4B-Base` fine-tuned on `signal_1062` — 1062 synthetic-but-real traces
(GPT-authored task specs → materialized into actual crates → kept only if real tool
execution matched the intended trajectory). Assistant-only loss masking, 3 epochs.

![SFT_V1 training loss](assets/fig_sft_loss.png)

On the 69 held-out prompts SFT_V1 is genuinely good at the *hard* part — solving:

| metric | SFT_V1 | what it means |
|---|---|---|
| `terminal_tool_success` | **0.986** | reaches a passing verifier on 68/69 |
| `valid_traces` | 52 / 69 | solved **and** stopped cleanly |
| `clean_end_rate` | 0.754 | emitted `FINAL` right after the last tool |

A real rollout, scored +8 by the verifier (4 turns, no wasted moves):

```text
CALL read_file {"id":"c1","file_path":".../src/main.rs"}
RESULT c1: status: success  stdout: fn main() { let records = [("ada", Some(4)), ...
CALL apply_patch {"id":"c2","find":".filter(|entry| ...","replace":".filter_map(|(name, score)| ..."}
RESULT c2: status: success  stdout: patch applied
CALL cargo_run {"id":"c3","project_path":"."}
RESULT c3: status: success  stdout: ada:4,bob:2,cy:8        ← exact oracle match
FINAL: patched the filter pipeline; stdout now matches.
```

The model reads, forms a hypothesis, patches, **verifies against the real compiler**, and
stops. That's the capability SFT installed, and it's solid.

### The one persistent gap: stopping

The 0.99-vs-0.75 gap is one failure mode: the model **solves, then keeps going**. It
reaches a passing `cargo_test`, then patches again, and again, until it hits the 15-round
cap and the trace ends on a bare `<|im_start|>assistant` with no `FINAL`. We threw data at
it — `signal_v2` (variable-depth recovery) and `signal_v3` (deeper coverage, oversampled
clean `PASS→FINAL` endings):

| model | data | valid | clean_end | terminal |
|---|---|---|---|---|
| SFT_V1 | signal_1062 (depth-1 recovery) | 52 | 0.754 | 0.986 |
| SFT_V2 | + variable-depth recovery | 48 | 0.70 | 0.96 |
| SFT_V3 | + deep coverage, oversample clean | 50 | 0.725 | 0.99 |

Stopping **plateaued at 0.72–0.75** regardless. The added recovery data did not produce
cleaner stopping; in inspected failures it could also encourage extra recovery attempts
instead of earlier termination. So we asked the obvious question: **is stopping an RL
problem?**

---

## 3. Experiment 1 — RL to teach stopping, and how it collapsed

`RLVR_V1` was the first attempt: shape a reward that punishes churning past a success and
rewards the clean `FINAL`. It used a stacked-penalty reward, `teacher-tau 0.01` (almost no
anchor), and cut exploration (temp 0.8→0.6, rollouts 8→4). The result was not a small
regression — it was a **capability collapse**, not just a finalization regression:

![RLVR_V1 collapse](assets/fig_collapse.png)

```
held-out 69:  valid 52 → 20   clean_end 0.75 → 0.33   terminal 0.99 → 0.70   task_failure 1 → 21
```

The model got *worse at solving*, not just worse at finalizing. The likely post-mortem
had four GRPO failure modes stacked:

1. **Unbounded stacked penalties.** Bad rollouts scored −13 to −23 against +12 for a
   solve. A single catastrophic rollout could dominate its group's advantage and drag the
   update.
2. **Weak positive path on failures.** On unsolved tasks, the reward mostly supplied
   negative contrast, so the optimizer could push away from working SFT behavior instead
   of toward a better repair strategy.
3. **No anchor.** `teacher-tau 0.01` let the policy drift off the SFT manifold; nothing
   pulled it back.
4. **Starved gradient.** With only four rollouts per prompt, many groups had no reward
   variance; the few that survived were noisy.

**Lesson:** a verifier-grounded RL reward must be **bounded, success-anchored (there is
always a positive path), and KL-anchored to the SFT model**, with enough rollouts for
within-group variance. Get any of those wrong and GRPO eats your SFT model.

### The measurement that reframed the whole project

We rebuilt the reward correctly (bounded, +8 verifier-dominant, hard anchor) and even
tried the most aggressive credit trick — `terminal_on_success`, which ends the episode one
turn *after* the first pass to force a clean stop/churn decision (`RLVR_B`). It **also**
regressed (52 → 19). At which point we stopped tuning and *measured the policy on the
training distribution*:

> On the **training** prompts, how often does SFT_V1 actually churn?
> - temp-0: **0 churn** (72 clean / 24 unsolved of 96)
> - temp-0.8, depth≥3: **0 / 16 churn**

That measurement was real, but the stronger claim I first wanted to make from it was too
blunt. It shows the original RL training prompts did **not** expose the churn/stopping
failure, so those prompts could not provide a stop-after-success gradient. It does **not**
prove the held-out failures were missing Rust capability.

The later pass@8 scan corrected the story. The 17 SFT_V1 formal failures were almost all
already successful at the verifier level: in the original HF/Transformers formal eval,
16/17 had `terminal_tool_success=True` but no clean `FINAL`; only one was a true task
failure. When the **same prompts/cases** were rescanned with the vLLM pass@8 harness,
those same 17 became 9 prompts at 8/8 and 8 mixed prompts, with **0 capability gaps**. So
the "stopping gap" was not simply "the model cannot solve these tasks." It was
protocol-termination instability that appeared under the HF/Transformers formal eval but
was much less absolute under the vLLM pass@8 diagnostic. The prompts were the same; the
difference was inference harness, sampling, and scoring criterion.

The usable RL lesson is narrower: do not assume a reward can fix a failure just because
that failure appears in one eval. First check whether the same failure mode appears under
the RL rollout harness and scoring rule. In the stop-focused runs, the training rollouts
did not expose solved-but-no-`FINAL` behavior, so the stop reward had little useful
contrast to reinforce. Later, pass@8 showed the same held-out prompts had verifier-success
capability under vLLM sampling, which changed the story from "missing Rust capability" to
"termination/protocol stability differs by harness and scoring."

---

## 4. The pivot — RLVR for what it's actually good at

So we pointed RL at the thing it's *designed* for: **lifting solve-rate where the policy
partially solves**, because that's exactly where the within-group variance (some pass,
some fail) gives GRPO a gradient.

The tool to find that band is a **pass@k scan**. Run SFT_V1 on each train prompt `k=8`
times at T=0.8 and bucket by how many rollouts solve it:

- `solves == 8` → **solved** (no variance → no gradient → RL can't help)
- `0 < solves < 8` → **rlvr-target** (variance exists → gradient → RL *might* help)
- `solves == 0` → **capability-gap** (RL can't cross a wall the policy never clears)

Here is that scan over 134 train prompts — and it's the most important figure in the
project:

![pass@k banding](assets/fig_passk_band.png)

```
capability-gap (0):  0      rlvr-target (1–7): 39      solved (8): 95
```

Read this honestly and it's already the answer. **95 of 134 prompts are fully solved.**
The 39 "addressable" prompts are jammed against the ceiling — 27 of them are at 7/8, i.e.
they fail once out of eight runs, usually to a *random decoding slip*, not a real skill
gap. And there are **zero** capability-gap prompts. The model is at its ceiling for this
data distribution. There is almost no exploitable gradient here. We ran RL anyway — partly
to confirm the prediction, partly because "the scan says stop" is a hard thing to trust
until you've watched it happen.

---

## 5. Experiment 2 — RLVR_PASSK_25, the capability-lift run

We trained GRPO from SFT_V1 on the 39-prompt rlvr-target band with a **minimal,
verifier-dominant reward** (the termination tails from Experiment 1 are zeroed — this run
optimizes solving only):

```text
verifier_success_bonus   +8.0    ← the whole signal (a real cargo pass)
structure_valid_bonus    +0.5    ┐
no_call_penalty          −2.0    ├ format floor (don't emit garbage)
malformed_call_penalty   −1.0    ┘ per parser-breaking typo, capped at 4
everything about stopping  0.0    ← zeroed; off-target for this run
```

Knobs from the lessons: `teacher-tau 0.2` (hard anchor), `rollouts-per-example 8`,
`temperature 0.8`, `zero_advantage` filter enforced. Checkpoint every 25 steps.

**Training dynamics** tell the story before eval does:

![RLVR_PASSK_25 training](assets/fig_passk25_train.png)

The reward is **noisy and trendless**, bouncing between 0 and 7 with no convergence, and
~36% of groups are filtered out as zero-advantage on average (often far more). That's the
signature of a band with no stable gradient: each step a handful of high-variance prompts
shove the weights one way, the next step shoves them back.

**Evaluation** — and here we hit a methodology point worth its own paragraph. The "before"
baseline and the "after" checkpoint must be measured on the **same inference engine**, or
you're comparing the model to the harness. We scanned both SFT_V1 and the step-25
checkpoint with the *same* vLLM scanner on the *same* 39 prompts:

![RLVR_PASSK_25 eval](assets/fig_passk25_eval.png)

```
mean pass@k on 39 targets:   SFT_V1 0.907  →  RLVR_PASSK_25 0.875   (−3.2 pts, 283 → 273 solves)
per-prompt moves:            6 up · 13 down · 20 flat
```

It **regressed**. And the per-prompt histogram shows *why*: every win (one beautiful 4→8,
a couple of 7→8s) is paid for by a loss (7→5, 6→4, two 8→6s among the supposedly-solved
prompts). RL didn't *lift* the band — it **churned** it, reshuffling which prompts the dice
favor, while quietly bleeding the already-solved prompts via parameter drift.

### Why it regressed (the mechanism, not the vibe)

1. **No reward variance to learn from.** The band is overwhelmingly near-ceiling — 27 of
   the 39 are at 7/8 on the defining scan, and on the vLLM re-measurement 23 of them
   actually hit 8/8 (which supports the point: many 7/8 prompts were near-ceiling sampling
   instability, not consistent errors). There's no stable direction to descend — RL just
   trades one random slip for another.
2. **Drift on the saturated prompts.** While the optimizer chases the handful of genuinely
   partial prompts, it nudges shared weights, and the already-solved prompts — which have
   no countervailing gradient — drift downward. (A follow-up run with `teacher-tau 0.3` and
   16 rollouts tightened the anchor and *still* drifted; the untrained 8/8 prompts slid
   1.00 → 0.96.)
3. **Sparse binary reward + full-parameter updates.** +8-or-nothing over a 4B full
   fine-tune produces small, noisy gradients; the *net* movement on a ceiling'd
   distribution is down, because there's more to lose than to gain.

The deeper truth is the one the pass@k scan stated up front: **for this SFT model and this
134-prompt training pool, there was almost no capability for RL to add.** The 39-prompt
band was too close to the ceiling and too noisy. The regression was not just a tuning
failure; it was largely a property of the data.

But it also suggested the way out: stop treating `pass@k` as a post-hoc graph, and use it
as a **target selector**.

---

## 6. The final run — a narrow pass@8 win, then the robustness check failed

At this point the project felt like a mess. The stopping story was no longer "the model
can't solve these"; it was "on the same held-out prompts, the model often reaches verifier
success under sampling, but clean termination is fragile and harness-dependent."
The broad 39-prompt pass@k run had regressed. A previous RL run may have solved one
held-out failure, but the model was worse overall, so it was not a clean win. The only
honest path left was narrower:

1. Re-run SFT_V1 with `pass@8` on the **original 17 held-out failures**.
2. Keep only prompts where SFT_V1 already showed latent capability (`0 < solves < 8`).
3. Train RLVR only on those mixed prompts.
4. Re-evaluate the same 8 prompts with the same vLLM pass@8 harness.

That scan changed the interpretation of the held-out failures. SFT_V1 was not 0/8 on
them. It had latent capability: on the 17 original failures, 9 were already 8/8 under
the vLLM pass@8 harness and 8 were mixed. This is an engine/harness caveat, not a
footnote: the original failures came from the HF/Transformers formal eval, while this
diagnostic was vLLM at T=0.8 and counted `terminal_tool_success`, not necessarily clean
`FINAL`. Still, for RLVR targeting, it identified which prompts had within-group verifier
variance. The final RL dataset became exactly those **8 mixed held-out-failure prompts**,
stored as:

```text
synthetic_data/rl_prompts_heldout69_passk_targets.jsonl
synthetic_data/heldout69_passk_target_names.txt
```

We also changed the reward shape. The earlier `+8`-only solve reward could positively
reinforce brittle solutions: any passing rollout looked equally good, even if it reached
success by luck, used messy tool behavior, or stopped poorly. The final reward kept the
verifier dominant, but added bounded structure around it:

```text
structure_valid_bonus                 +0.5
no_call_penalty                       -2.0
malformed_call_penalty                -1.0
final_once_bonus                      +0.5
missing_final_penalty                 -0.5
verifier_success_bonus                +8.0
verifier_success_clean_final_bonus    +3.0
tool_after_success_penalty            -2.0
tool_budget_exhausted_penalty         -1.5
failed_verifier_penalty               -0.25  capped at -1.5
```

This is still not "reward engineering magic." The verifier remains the main signal. The
extra terms mostly prevent RL from treating a brittle pass and a clean pass as identical.

The run itself was not smooth. It took multiple failed launches to get a real checkpoint:

- `seq_len=8192`, `max_model_len=8192` failed because teacher scoring needs at least one
  extra token (`8192 + 1 > 8192`).
- `max_model_len=9216` got past teacher scoring but tool traces reached ~9.6k tokens.
- one-trainer-GPU full fine-tune OOMed at the LM head.
- two trainer GPUs still OOMed on backward.
- the final fix was PRIME-RL activation checkpointing plus fused LM-head chunking.

This was the part that felt like actual blood, sweat, and tears: not one clean command,
but a live loop of killing leaked GPU workers, reading the exact 400/OOM traces, raising
context only when the logs proved it, checking whether a checkpoint really existed, and
refusing to call anything a win until the same pass@8 harness measured it against the
SFT baseline.

The exact successful training command was:

```bash
python rl/train.py \
  --data synthetic_data/rl_prompts_heldout69_passk_targets.jsonl \
  --output outputs/rlvr_heldout69_passk8_targets_seq8192_mlen12288_train2_memfix \
  --max-steps 50 \
  --batch-size 8 \
  --rollouts-per-example 8 \
  --seq-len 8192 \
  --max-model-len 12288 \
  --teacher-max-model-len 12288 \
  --max-completion-tokens 1536 \
  --learning-rate 2e-7 \
  --checkpoint-interval 25 \
  --temperature 0.8 \
  --max-tool-rounds 15 \
  --tool-timeout 30 \
  --teacher-tau 0.4 \
  --activation-checkpointing \
  --fused-lm-head-token-chunk-size auto \
  --prime-rl-gpu-ids 0,1,2 \
  --num-infer-gpus 1 \
  --num-train-gpus 2 \
  --gpus-per-node 3 \
  --port 8000 \
  --teacher-device 3
```

This was run on a 4xA100 instance. GPUs `0,1,2` were assigned to PRIME-RL
(trainer + inference); GPU `3` was reserved for the frozen teacher via
`--teacher-device 3`, so it is intentionally outside `--prime-rl-gpu-ids`.

Then we stopped training at step 25 and ran the matched vLLM pass@8 sweep on the same 8
targets:

![narrow RLVR step-25 run](assets/fig_heldout69_step25.png)

```bash
NAMES=$(paste -sd, synthetic_data/heldout69_passk_target_names.txt)
PYTHONPATH=/workspace/glyph python sft/passk_scan_vllm.py \
  --sft-model outputs/rlvr_heldout69_passk8_targets_seq8192_mlen12288_train2_memfix/weights/step_25 \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
  --prompt-section post_eval_heldout_69 \
  --cases-root synthetic_data/eval_blueprints \
  --names "$NAMES" \
  -k 8 \
  --temperature 0.8 \
  --max-new-tokens 4000 \
  --max-tool-rounds 15 \
  --tool-timeout 30 \
  --max-model-len 12288 \
  --dtype bfloat16 \
  --output results/RLVR_HELDOUT69_PASSK_STEP25/passk8_step25_8targets.json \
  --no-resume
```

Result:

```text
SFT_V1:   47/64 = 0.734
step_25:  54/64 = 0.844
delta:    +7 solves, +10.9 points
```

Per prompt:

```text
7 -> 6  eval100_040...route_action_enum_branch_recovery   (-1)
7 -> 8  eval100_071...layered_flags_cli_precedence        (+1)
6 -> 7  eval100_044...rank_players_dense_tiebreak         (+1)
1 -> 3  eval100_020...parse_records_validate_age          (+2)
6 -> 8  eval100_057...config_merge_precedence             (+2)
7 -> 8  eval100_045...daily_sales_region_summary          (+1)
6 -> 7  eval100_005...dispatch_route_mode_branch          (+1)
7 -> 7  eval100_037...weekly_region_summary               (+0)
```

This was the RLVR artifact I was looking for, but it was only a **narrow pass@8** win.
It did not invalidate the earlier diagnosis. It narrowed it: the selected-band metric
improved only after we chose the small band where the base model had latent capability and
real rollout variance.

But there was one last thing to check: does the checkpoint still hold up on the original
69-prompt formal eval that established SFT_V1's baseline? We ran the same HF/Transformers
`sft.eval_formal` harness:

```bash
python -m sft.eval_formal \
  --sft-model JayZenith/RLVR_HELDOUT69_PASSK_STEP25 \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
  --prompt-section post_eval_heldout_69 \
  --train-data synthetic_data/signal_1062.jsonl \
  --cases-root runs/rlvr1/rust_cases/eval_heldout_69 \
  --output results/RLVR_HELDOUT69_FORMAL_STEP25/eval_formal_heldout_69_step25.json \
  --max-new-tokens 4000 \
  --max-tool-rounds 15 \
  --tool-timeout 30
```

It failed the robustness check:

```text
SFT_V1 baseline: valid 52/69, terminal_tool_success 68/69
step_25:         valid 19/69, terminal_tool_success 47/69

step_25 failure buckets:
missing_final / dirty_final / final_before_tool_completion: 48
task_failure: 22
truncated: 7
terminal success but invalid trace: 28
```

The failure mode was not subtle Rust capability loss alone. It was protocol/text
degeneration under multi-turn tool-use pressure. Many traces reached a successful tool
result and then never emitted `FINAL`; others kept calling tools, produced malformed
paths/CALLs, repeated failed patches, or fell into garbage token loops such as
`.invokeLater`, `.nanoTime`, `.readyState`, and similar non-task text.

So the final checkpoint is **not a deployable improvement over SFT_V1**. It is evidence
for a narrower claim: pass@k targeting can find prompts where RLVR increases sampled
solve-rate, but full-parameter GRPO on only eight prompts can still shift the model away
from SFT's broad protocol prior. That distinction is the whole project.

---

## 7. Bugs that would have faked a result

An evals project lives or dies on whether the numbers are real. Four bugs in this run
would each have produced a *confidently wrong* number:

- **vLLM silently zeroed pass@k.** The model emits `<|im_end|>` as a *special token*, but
  vLLM's default `skip_special_tokens=True` strips it from the output text — so a
  string-based stop on `"<|im_end|>"` never matched, generation ran straight past every
  turn boundary, no tools ever executed, and the scanner reported **0/8 on prompts the
  model actually solves 8/8.** Fix: stop on the token *id*, and re-append `<|im_end|>` so
  the protocol parser can still segment turns. A string-vs-token-id detail that, uncaught,
  reads as "RL destroyed the model."
- **Teacher/trainer GPU collision.** The trainer's FSDP process bound to `cuda:0`, where
  the frozen teacher already sat — OOM at the first forward. The earlier run hid it because
  rollouts were failing before the trainer ever stepped.
- **Disk exhaustion.** Every rollout copies a crate and compiles a `target/` dir; nothing
  cleaned them. 22 GB of cargo sandboxes filled the disk mid-run and the trainer died
  *saving a checkpoint* (`No space left on device`). The fix was a janitor deleting
  completed sandboxes during training.
- **Long-context trainer OOM.** The successful step-25 run only worked after raising
  vLLM/teacher context to 12,288 and enabling trainer activation checkpointing plus fused
  LM-head chunking. Before that, the failure looked like "RL is broken" when it was just
  the trainer trying to materialize long-sequence logits.

None of these are deep, but each one *looks like a model result* if you don't chase it.
"Is this number real?" is the actual job.

---

## 8. What this project is

Not "a general Rust agent." It's the **full SFT → RLVR → serve loop with a faithful
harness and a measured map of where each stage breaks**:

- **SFT** installs the protocol and the skill, and it works at the verifier level
  (terminal 0.99). Its weakest part is clean protocol termination under the HF/Transformers
  formal eval; the same prompts showed much more verifier success under vLLM pass@8.
- **RL cannot install a behavior absent from its own rollouts.** The original stop-focused
  RL runs trained on prompts where SFT_V1 showed ~0 churn, so the reward had no reliable
  stop-after-success contrast to reinforce. That is narrower than saying the held-out
  churn was a missing-capability problem.
- **RL cannot lift capability the policy has already saturated** (the 39-prompt pass@k
  band). The scan predicted the broad failure before we spent the GPU-hours.
- **RL can lift reliability on this narrow, mixed band** (the 8 held-out-failure targets):
  47/64 → 54/64 at step 25, measured with the same vLLM pass@8 harness.
- **That lift did not survive the broad formal eval.** The same checkpoint regressed the
  original held-out 69 from 52/69 valid traces to 19/69, mostly by damaging clean protocol
  completion and multi-turn stability.
- **`pass@k` banding is the cheap diagnostic** for "can RL help here at all?" If the band
  is empty or jammed at the ceiling, the answer is no — and you should believe it.

The honest deliverable is not "RL magically makes a 4B Rust agent." It is the targeting
rule plus the failure boundary: **in these experiments, RLVR helped where the base policy
already had partial capability and verifier variance; it failed or drifted where the RL
dataset lacked the failure mode, where the policy was saturated, or where full-parameter
updates overpowered the SFT protocol prior.**

### What a real lift would need

Not a magic knob. **Better target bands** — prompts with genuine, consistent partial
capability (baseline 1–6/8 from real difficulty, not just 7/8 decoding noise), where
within-group variance reflects something learnable. The final run was small because the
dataset only had 8 such prompts. Scaling the win requires generating more prompts with
that same property, then holding back a matched eval set.

Full-parameter GRPO may also have been the wrong adaptation mechanism for an 8-prompt
target set. A natural follow-up is LoRA-based RLVR, or an auxiliary SFT/protocol loss
during RL, so the update can specialize the narrow pass@8 band without moving the whole
model away from the broader tool-use distribution SFT_V1 learned.

---

## Assets

- **Models** (Hugging Face): `JayZenith/SFT_V1` (the ceiling for this data), `SFT_V2`,
  `SFT_V3`; `RLVR_V1` (broken-reward collapse, kept as evidence),
  `RLVR_PASSK_25` (39-prompt capability-lift attempt, regressed), and
  `JayZenith/RLVR_HELDOUT69_PASSK_STEP25` (8-target pass@8 lift, but failed the full
  formal eval).
- **Data**: `signal_1062` → `signal_v2_1323` → `signal_v3`; RL band
  `synthetic_data/rl_prompts_passk_target.jsonl`; pass@k candidate set
  `runs/rlvr_passk_train150/`.
- **Code**: `rl/task_trace.py` (the `verifiers` env + reward), `sft/passk_scan.py` /
  `sft/passk_scan_vllm.py` (the banding scan), `agent_runtime/` (real cargo execution),
  `reward_golden_tests.py` (reward unit tests).
- **Final-run artifacts**: `results/RLVR_HELDOUT69_PASSK_STEP25/passk8_step25_8targets.json`,
  `passk8_step25_comparison.csv`, `rlvr_step25_training_metrics.csv`, plus synced configs,
  logs, rollout JSONLs, and W&B offline files under `training_artifacts/`.
- **Formal robustness check**:
  `results/RLVR_HELDOUT69_FORMAL_STEP25/eval_formal_heldout_69_step25.json` and
  `eval_heldout69_step25.log`.
- **Figures**: regenerate with `blog/make_figures.py` from `results/` (tfevents, eval
  JSONs, rollouts).
- **Deeper technical notes**: `rl/RLVR_NOTES.md`.
