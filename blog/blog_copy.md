# SFT to RLVR

Teaching `Qwen3-4B-Base` a coding-agent protocol on real Rust tasks:

```text
assistant -> CALL ...      (read_file, apply_patch, cargo_test, cargo_run)
tool      -> RESULT ...    (real tool output, executed in a sandbox)
assistant -> FINAL: ...    (stop)
```

Tools run for real against sandboxed crates. `cargo_run` only counts as success if stdout exactly matches expected; `cargo_test` if tests pass. The model can't fake it.

Eval = 69 held-out prompts (`eval_prompts_heldout_69.yaml`). Key metrics: **valid_traces** (solved + clean stop), **clean_end_rate**, **terminal_tool_success** (solved, ignoring stop).

## SFT worked; the gap is stopping

```text
            valid  clean_end  terminal   notes
SFT_V1      52/69    0.75       0.99     baseline (signal_1062, all recovery depth-1)
SFT_V2      48/69    0.70       0.96     +variable-depth recovery (signal_v2)
SFT_V3      50/69    0.725      0.99     +deep coverage, oversample clean PASS->FINAL (signal_v3)
```

The model solves almost everything (terminal ~0.99). **The only persistent failure is termination**: it reaches a passing verifier, then keeps patching to the tool-round cap (15) and never emits `FINAL`. The trace ends on a bare `<|im_start|>assistant` opener — the round cap fires before it spends a turn on FINAL.

Three data variants, stopping plateaued at **0.72–0.75**. So it's **not a data-coverage gap** — the model has thousands of `success -> FINAL` examples and still won't stop on its *own* messy trajectories. SFT only ever shows it the teacher's clean states.

Important detail from the data: SFT_V2/V3 recover *deeper* but **over-recover** — they make 5 failed attempts where SFT_V1 fixes it in 1 and stops. V1→V3 just trades which deep cases stop (fixed 5 shallow, broke 7 depth-5). More recovery data makes stopping *worse* on the hardest cases.

## Why RLVR_V1 collapsed (and what we fixed)

First RL run regressed everything: valid 52→20, clean_end 0.75→0.33, terminal 0.99→0.70. Causes:

- **Stacked penalties** to −13..−23 vs +12 for a solve → one bad rollout dominated its GRPO group.
- **No positive path** — clean FINAL only paid after a passing verifier, so unsolved cases were all-negative.
- **No SFT anchor** (`teacher-tau 0.01`) → the policy drifted and collapsed.
- **~56% zero-advantage groups** → almost no usable gradient.

That was a broken reward/recipe, not proof RL can't do this.

## The reward now (minimal, success-anchored)

One scalar, computed **once at the end of the full rollout** (not per turn). GRPO compares rollouts in a group; the good (success→FINAL) and bad (success→another CALL) rollouts diverge at one token, so credit lands on the stop decision.

```text
format floor
  structure_valid            +0.5
  no_call_penalty            -2.0    emitted no tool call
  malformed_call_penalty     -1.0    per "CALLX" parser-breaking typo (cap 4)
finalize
  final_once_bonus           +1.0    exactly one FINAL
  missing_final_penalty      -2.0    zero (or >1) FINAL
the target: solve, then stop
  verifier_success_bonus     +8.0    a verifier actually passed (real correctness)
  verifier_success_clean_final +3.0  passed AND one FINAL after it AND no tools after
  tool_after_success_penalty -3.0    any tool ran after the pass (churn = the failure)
  tool_budget_exhausted      -2.0    hit max_tool_rounds
```

```text
solve + stop              = 12.0   <- maximum
solve, no FINAL (stops)   =  6.0
solve, churn to round cap =  1.0   <- the actual failure (-3 churn, -2 budget)
graceful exit (unsolved)  =  1.0   <- unsolved but one FINAL
loop (unsolved, no stop)  = -2.0
```

The +8/+3 dominate and only fire on real success. The ~11-point gap between solve+stop (12) and the real churn-to-budget failure (1) is what teaches stopping, while solving stays net-positive so the model never abandons it. Removed all the old shaping (recovery bonuses, stacked penalties, first-call alignment) — 9 terms, nothing else.

## Where we are

- **Diagnosis is settled:** the only gap is stopping after a self-made deep success. It's in the data, plateaus under SFT → it's a distribution-shift problem on the model's own states = **RL's job**, not more SFT.
- **RL base = SFT_V1** (not V2/V3): it solves efficiently and its residual is *pure stopping*. V2/V3 over-recover, which RL would have to unteach first.
- **Recipe** (`rl/scripts/launch_rlvr_v2.sh`): base+teacher SFT_V1, `teacher-tau 0.2`, temp 0.8, 8 rollouts/example, zero-advantage filter on, lr 5e-7, minimal reward above, early-stop on the 69, gate each checkpoint on a 12-prompt smoke set.
- **Cheaper-credit option** (no reward complexity): end the episode at first success so the next turn is forced terminal — tightest possible credit on the stop decision.

## Kill conditions
- clean_end or terminal_tool_success drops below the SFT_V1 baseline for 2 checkpoints → stop, it's collapsing.
- Success bar: beat SFT_V1's 52/69. If RL can't, the problem is harder than stopping and we re-diagnose.

## Then RLVR-to-stop regressed too — and that was the real finding

We wired the cheaper-credit option: `terminal_on_success` (`rl/task_trace.py`, `--terminal-on-success` in `rl/train.py`) — end the episode one turn after the first verifier pass, forcing the next turn to be terminal so credit lands exactly on the stop decision. Ran it as RLVR_B.

It collapsed on full eval: valid **52→19**, terminal 68→46 at step 25. A 12-prompt smoke set hid it (only 3 churn cases in the smoke). Exactly one case improved (`eval100_020`). What fixed shallow stopping broke depth (`eval100_087`). Same signature as RLVR_V1.

One caveat before the conclusion: B isn't a clean control. It changed *two* things vs RLVR_V1 — the corrected reward **and** the `terminal_on_success` horizon truncation — so it doesn't isolate "the reward was fine." It only shows that even the most aggressive credit trick for stopping still collapses. The clean "corrected reward, normal episodes" full-69 run was never taken past smoke, so it isn't evidence. The real proof isn't the run comparison at all — it's the measurement:

**Churn is an out-of-distribution tail. The training prompts don't elicit it.** We measured the model's own behavior on the *train* set:
- temp-0 train: **0 churn** (72 clean / 24 unsolved of 96)
- temp-0.8, depth≥3 train: **0/16 churn**

In-distribution the model terminates cleanly. It only churns on the held-out 69 — prompts whose difficulty/shape the train set never produced. So RL was being asked to install a stop behavior the policy *never samples* on the prompts it trains on. GRPO can only reinforce variance that exists in the rollouts; if the model never churns-then-recovers-then-stops on train prompts, there's no gradient to shape. **RL can't teach a behavior the policy doesn't emit.** That's scale-independent — true at any compute budget — and it's the actual ML insight of this project.

So the earlier "stopping is RL's job" conclusion was half-right: it's a distribution-shift problem, but the shift is between *held-out* and *train*, not between teacher-clean and model-messy. You can't RL it away on train data, and you shouldn't try to RL it on the 69 (that's the measure-only set). The termination tail is an **SFT-coverage / data problem** (cover the hard held-out shapes in training), not an RL problem.

## The pivot: RLVR for what it's actually good at

Drop the termination tail. RLVR's legitimate use on `SFT_V1` is the thing it's designed for — **lift solve-rate where the policy partially solves**:

- pass@k scan on a train slice. Band each prompt: `0 < solves < k` = **rlvr-target** (reward variance exists → gradient), `== k` = solved (no gradient), `== 0` = capability gap (RL can't cross).
- Candidate set carved: `runs/rlvr_passk_train150/prompts.yaml` (150 mixed-difficulty train prompts, metadata: kind/difficulty/depth). Trim the 16 depth-1 trivia (pass@k=k for sure) → scan the ~134 depth≥3 (`sft/passk_scan.py`, k=8, T=0.8).
- RL on the rlvr-target band only (`rl/scripts/launch_rlvr_v2.sh`). **Zero the termination tails** (−3 churn, −2 budget, ±finalize) for this run — they were shaped for the *stopping* goal, which we're explicitly not optimizing here, so carrying stop-pressure into a capability run is just off-target noise. Reward = **verifier (+8) + format floor only**. The +8 variance across the 8 rollouts of a partial-solve prompt is the whole signal; sparse verifier reward is *correct* for capability lift. (Note: the tails weren't what we were testing in RLVR_B — that run was reward + `terminal_on_success` together against an OOD target — and regardless, there's no reason to keep stop-pressure in a run that isn't about stopping.)
- Artifact = **pass@1 before vs after** on the rlvr-target band, labeled in-set lift. No held-out split for v1: a small unmatched held-out is noisier than honest in-set numbers; add a stratified (kind, depth, tool, pass@k-bucket) split only when volume makes it fair.

## Serving + honest generalization

Served via vLLM/TGI + a harness that replays the training protocol **byte-for-byte** (`agent_runtime/protocol.py`: parse `CALL tool(... id="cN")`, execute for real, format the `RESULT` block identically, loop, detect FINAL). Path generalization is fine — paths are copied from prompt to tool call, a new crate path is in-distribution as a token pattern. The real limits, predicted from what we measured:

- narrow code distribution (synthetic single-file crates with oracle tests) → degrades on multi-file real repos with no oracle;
- brittle to protocol drift — any formatting mismatch is instant OOD;
- no verifier at inference — the signal RL optimized doesn't exist when serving;
- the termination tail resurfaces the moment input looks unfamiliar.

This is **narrow by design** under solo/compute constraints — narrowness bought legible failure modes. The deliverable isn't "a general Rust agent"; it's the full SFT→RLVR→serve loop with a faithful harness and a measured map of where each stage breaks: SFT coverage gaps, RL's inability to install unsampled behavior, the OOD termination tail. Those are predictable because they were measured.

## What's next
- Run the ~134-prompt pass@k scan → freeze the rlvr-target band.
- RLVR (GRPO) on that band; report in-set pass@1 lift.
- (Separate track) close the termination tail the right way: add the hard held-out shapes to SFT coverage so the model samples them, *then* RL has something to reinforce.

## Assets
- Models: `JayZenith/SFT_V1` (RL base), `SFT_V2`, `SFT_V3`, `RLVR_V1` (regressed, do not use), `RLVR_B` (terminal_on_success, regressed — kept as the A/B evidence).
- Data: `signal_1062` → `signal_v2_1323` → `signal_v3` (HF: `SFT_V1_DATASET`, `SFT_V2_DATASET`). RL prompt pool: `synthetic_data/rl_prompts_v2_1323.jsonl`. pass@k candidate set: `runs/rlvr_passk_train150/`.
- Results: `results/SFT_V1|V2|V3`, `results/RLVR_V1`, RLVR_B eval (52→19 collapse), pass@k scan → `results/passk_train134.json`.
- Tooling: `sft/passk_scan.py` (RLVR-addressable banding), `sft/gen_churn_traces.py` (rejection-sampling harness, shelved — train doesn't churn), `reward_golden_tests.py` (6 reward unit tests).
