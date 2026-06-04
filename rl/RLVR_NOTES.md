# RLVR — technical lab notes

Raw, honest, reproducible. This is the file to study from: the GRPO mechanics, the exact
reward algebra, every run's config + numbers, the failure mechanisms, and the bugs that
would have faked results. The headline: **every RL run came in below SFT_V1, and a single
`pass@k` scan predicted it.** That is the finding, not a footnote.

---

## 0. Mental model: GRPO + the zero-advantage filter

PRIME-RL trains with **GRPO** (Group Relative Policy Optimization). No value network. For
prompt `p` you sample a group of `G` rollouts, score each with the rubric to a scalar
`r_i`, and form advantages by normalizing **within the group**:

```
A_i = (r_i − mean(r_1..r_G)) / (std(r_1..r_G) + eps)
```

The policy-gradient step pushes up tokens of above-average rollouts and down below-average
ones. The consequence that governs this entire project:

```
std(r_group) == 0   ⇒   A_i == 0 for all i   ⇒   zero gradient from that prompt
```

A prompt the model **always solves** (all `r_i = +8`) or **never solves** (all `r_i = 0`)
produces no learning signal. PRIME-RL makes this a first-class filter:

```toml
# rl/configs/task_trace/orchestrator.toml
[[filters]]
type = "zero_advantage"
enforce = true          # drop all-identical-reward groups before the trainer sees them
```

**Therefore RL only learns from prompts with within-group reward variance** (some rollouts
pass, some fail). Everything downstream — why stopping can't be taught, why the saturated
band regresses — is a corollary of this one fact. In `RLVR_PASSK_25` ~36% of groups were
filtered on average (often much more per step); see `fig_passk25_train.png`.

### The async loop (PRIME-RL processes)

- **orchestrator** — runs the `verifiers` env (the tool loop), scores with the `Rubric`,
  applies filters, builds batches. `rl/configs/task_trace/orchestrator.toml`.
- **trainer** — FSDP GRPO update; KL term toward the frozen **teacher**; broadcasts new
  weights to inference each step. `rl/configs/task_trace/trainer.toml`.
- **inference** — vLLM serving the live policy. `inference.toml`.
- **teacher** — frozen vLLM (here SFT_V1 itself); `teacher_tau` weights the KL anchor.

Launched through `rl/train.py`, which composes the three TOMLs, places GPUs
(`--teacher-device`, `--prime-rl-gpu-ids`), and forwards CLI overrides.

---

## 1. The reward (`rl/task_trace.py`)

One `Rubric` reward func, `_rust_tool_reward`, weight 1.0, **one scalar per full rollout**
(not per turn — GRPO compares whole rollouts, so end-of-rollout credit is correct). The
verifier outcome is recovered by **parsing the env's own `RESULT` blocks** from the
transcript — `_find_result_for(call_id)` regexes `status: success` etc. A `cargo_run` only
counts if the executor already enforced exact-stdout match upstream; the reward just reads
the status the real tool produced.

### Current config — capability-lift (`DEFAULT_REWARD_CONFIG`)

```python
verifier_success_bonus        = +8.0    # the whole signal: a real cargo pass
structure_valid_bonus         = +0.5    # format floor
no_call_penalty               = -2.0    # emitted zero tool calls
malformed_call_penalty        = -1.0    # per "CALLX" parser-breaking typo, capped at 4
# termination tails — ZEROED for this run (it optimizes solving, not stopping):
final_once_bonus              =  0.0
missing_final_penalty         =  0.0
verifier_success_clean_final  =  0.0
tool_after_success_penalty    =  0.0
tool_budget_exhausted_penalty =  0.0
```

Scoring path (`_rust_tool_reward`):
1. `structure` floor (`+0.5` if the trace is structurally valid).
2. No executed calls → `no_call_penalty (-2) + structure`. Done.
3. `malformed = count(/\bCALL[A-Z]/)` → `min(malformed,4) * -1`.
4. `+ _finalization_reward` (zeroed now).
5. `+ _outcome_reward`: scan executed `cargo_*` calls; on the **first** one whose `RESULT`
   is `success`, add `+8`. (Tails — churn-after-success, clean-final bonus — are zeroed.)
6. `+ tool_budget_exhausted_penalty` (zeroed now).

Net effect for this run: **+8 on a real solve, a small format floor, nothing else.** That
is deliberately the *correct* reward for capability lift — sparse, verifier-dominant, no
off-target stop-pressure. It is locked by `reward_golden_tests.py` (6 tests: solving
dominates by exactly `+8`, termination neutral, format floor applies, worst case bounded
> −4).

### Prior config — stopping (used by RLVR_A/B; restore by un-zeroing the tails)

```text
verifier_success_bonus        +8      verifier_success_clean_final  +3
final_once_bonus              +1      missing_final_penalty         −2
tool_after_success_penalty    −3      tool_budget_exhausted         −2
```

Reward algebra for canonical trajectories under the stopping config (this is the shape we
*wanted* for stopping):

```
solve → one FINAL, no tools after   = +8 +1 +3            = 12   (max)
solve → no FINAL                     = +8 −2               =  6
solve → churn to round cap           = +8 −2(final) −3 −2  =  1   ← the actual failure
graceful give-up (unsolved, 1 FINAL) =  +1                 =  1
loop (unsolved, no FINAL)            =  −2                 = −2
```

The ~11-pt gap between solve+stop (12) and churn-to-budget (1) is the stop signal — *if the
policy ever samples churn-then-stop*. It doesn't (§3). So this shape was never the problem.

---

## 2. SFT baseline (the thing RL has to beat)

`results/SFT_V1/eval_formal_heldout_69.json`, 69 held-out prompts:

```
valid_traces 52   clean_end 0.7536   terminal_tool_success 0.9855   avg_score 12.71
failure buckets:  dirty_final 17 · missing_final 17 · task_failure 1
```

So: solves 68/69, but 16–17 of those solves never emit `FINAL` (churn to the 15-round cap,
trace ends on a bare `<|im_start|>assistant`). SFT_V2/V3 push *more/deeper* recovery data;
`clean_end` plateaus 0.72–0.75 and deeper data makes the model **over-recover** (more
failed attempts before it stops). Stopping is not a simple data-volume fix.

---

## 3. Stopping was absent from the original RL train rollouts

**RLVR_V1** (stopping reward, but the *broken* early version: penalties stacked to
−13..−23, `teacher-tau 0.01`, temp 0.8→0.6, rollouts 8→4) collapsed:

```
valid 52→20   clean_end 0.75→0.33   terminal 0.99→0.70   task_failure 1→21   truncated 0→5
```

It got worse at *solving*, which the reward never mentions → capability collapse, not a
finalization tweak. Four GRPO failure modes stacked (study these — they're general):
1. **Unbounded penalties** → one −23 rollout dominates its group's advantage.
2. **No positive path on failures** → every action on an unsolved task scores negative →
   optimizer flees the working SFT behavior.
3. **No anchor** (`tau 0.01`) → policy drifts off the SFT manifold, nothing pulls back.
4. **Starved gradient** → ~56% zero-advantage groups; survivors noisy.

**RLVR_B** (corrected bounded reward **+** `--terminal-on-success`, which ends the episode
one turn after the first pass to force a stop/churn decision) *also* regressed: 52→19,
terminal 68→46 @ step 25. Caveat: B changes two things vs V1 (reward **and** horizon
truncation) → **not a clean reward control**. It only shows the most aggressive credit
trick for stopping still collapses.

The A/B is corroboration. **The explanation starts with a direct measurement of the
policy on the original RL training distribution:**

```
churn rate on TRAIN prompts (SFT_V1):
  temp-0:               0 churn   (72 clean / 24 unsolved of 96)
  temp-0.8, depth≥3:    0 / 16 churn
```

The model did not churn on those train prompts, so the original stop-focused RL runs had
no reliable solved-but-no-`FINAL` contrast to reinforce. The later held-out pass@8 scan
made the interpretation more precise: the 17 SFT_V1 formal failures were not missing Rust
capability. In the HF/Transformers formal eval, 16/17 already reached
`terminal_tool_success=True` but lacked a clean `FINAL`; with the same prompts/cases under
the vLLM pass@8 diagnostic, 9 were 8/8 and 8 were mixed, with 0 capability gaps.

> **Lesson:** do not assume a reward can fix a failure just because that failure appears in
> one eval. First verify that the same failure mode appears under the RL rollout harness
> and scoring rule. In our stop-focused runs, it did not.

---

## 4. The pivot — pass@k banding, and what it revealed

Point RL at its actual job: lift solve-rate where the policy *partially* solves (the only
place within-group variance, hence gradient, exists). Band each train prompt by terminal
success over `k=8` samples at T=0.8:

```
solves == k   → solved        (no variance → no gradient)
0 < solves < k→ rlvr-target   (gradient → RL might help)
solves == 0   → capability-gap(RL can't cross a wall the policy never clears)
```

Scan of 134 train prompts (`synthetic_data/passk_train134.json`), solves histogram 0..8:

```
[0, 0, 0, 0, 1, 4, 7, 27, 95]
 0  1  2  3  4  5  6  7   8        → capability-gap 0 · rlvr-target 39 · solved 95
```

This **is** the verdict, before any RL: 95/134 fully solved; the 39 addressable prompts are
jammed at the ceiling (27 at 7/8 — failing 1/8 to decoding noise); **0 capability-gap.** The
model is at its ceiling for this distribution. There's almost no exploitable gradient. We
ran RL anyway to confirm.

---

## 5. RLVR_PASSK_25 — the capability-lift run

**Config** (`rl/train.py` CLI; base+teacher SFT_V1):

```
--data rl_prompts_passk_target.jsonl   (39 rlvr-target prompts)
--teacher-tau 0.2  --learning-rate 5e-7  --temperature 0.8
--rollouts-per-example 8  --batch-size 24  --max-steps 200  --checkpoint-interval 25
reward = capability-lift config (§1): +8 verifier, format floor, tails zeroed
zero_advantage filter enforced
```

**Training dynamics** (`results/RLVR_PASSK_25/run_default/rollouts/step_*`, 66 steps;
`fig_passk25_train.png`): mean reward is **noisy and trendless** (bounces 0–7, no
convergence); ~36% of groups filtered as zero-advantage. Signature of a band with no
stable gradient — a few high-variance prompts shove the weights one way each step, the next
step shoves back.

**Eval** — measured this session, **vLLM-vs-vLLM on the same 39** (before = SFT_V1 rescanned
on the identical engine; this matters, see §7):

```
mean pass@k on 39:   SFT_V1 0.9071 (283/312)  →  step_25 0.8750 (273/312)  →  step_50 0.8718
per-prompt moves (step_25 − SFT_V1):   6 up · 13 down · 20 flat
Δ histogram:   −3:2  −2:3  −1:8  0:20  +1:4  +2:1  +4:1
```

**It regressed −3.2 pts.** Wins (one 4→8, a couple 7→8) are matched by losses (7→5, 6→4,
two 8→6). RL **churned** the band — reshuffled which prompts the dice favor — and **drifted
the saturated prompts down**. step_50 < step_25 ⇒ drift accumulates, not signal.

### Why (mechanism, not vibe)

1. **No reward variance to learn from.** The 39-band's vLLM baseline buckets: `4/8:3,
   5/8:1, 6/8:2, 7/8:10, 8/8:23`. Two-thirds ≥7/8. A 7/8 failing 1/8 is *sampling noise*,
   not a consistent error → no stable descent direction → RL trades one random slip for
   another.
2. **Drift on saturated prompts.** While the optimizer chases the ~6 genuinely-partial
   prompts, shared weights move; the 23 already-8/8 prompts (no countervailing gradient)
   slide down. The `tau 0.2` anchor is too loose to hold them.
3. **Sparse binary reward + 4B full fine-tune.** +8-or-nothing → small noisy gradients; net
   movement on a ceiling'd distribution is downward (more to lose than gain).

### Confirmation run (tighter anchor, cleaner band) — still regressed

To test "is it the band or the anchor," a follow-up: **train only the 16 non-8/8 prompts**
(cut the 23 zero-gradient drifters), `teacher-tau 0.3`, `rollouts-per-example 16`. Baseline
on that 16-band = **0.7734**.

```
step_20:  16-band 0.789 → 0.750  (4 up · 5 down)
          23 untrained 8/8:  1.000 → 0.964   (still drifting, even at tau 0.3)
          full 39:           0.919 → 0.882
```

Same signature. Removing the dead prompts and tightening the anchor did **not** flip the
sign. Killed it. **Conclusion: it's not the band or the anchor — there is no capability for
RL to add on this pool. SFT_V1 is the ceiling.**

---

## 6. The reward-design rules (generalize these)

For verifier-grounded GRPO on top of a strong SFT model:
- **Bounded.** No unbounded stacked penalties; one bad rollout must not dominate its group.
- **Always a positive path.** Even on failure, the best action must score ≥ the worst — or
  the optimizer flees working behavior (RLVR_V1 mode 2).
- **Verifier-dominant + sparse is correct** for capability lift; don't smear it with
  off-target shaping (we zeroed stop tails for the lift run).
- **Hard KL anchor.** `tau 0.2–0.3`; `0.01` drifts and collapses.
- **Enough rollouts for variance.** 8 is the floor; 4 gave ~56% zero-advantage.
- **None of it matters if the band has no variance.** Run the pass@k scan *first*.

---

## 7. Bugs that would have faked a result (measurement correctness)

- **vLLM `skip_special_tokens=True` zeroed pass@k.** The model ends turns with the
  `<|im_end|>` *special token*; vLLM strips it from output text, so a **string** stop on
  `"<|im_end|>"` never fires → generation runs past every turn boundary → no tools execute
  → scanner reports **0/8 on prompts the model solves 8/8**. Fix in `sft/passk_scan_vllm.py`:
  stop on the token **id** (`tokenizer.convert_tokens_to_ids("<|im_end|>")`) and re-append
  `"<|im_end|>"` to the chunk so the `SEG_RE` protocol parser can segment turns. Verified
  on one prompt (read→patch→cargo_test pass→`terminal_tool_success: True`) before trusting
  any number. **Always compare before/after on the same inference engine** — the SFT_V1
  "before" was re-scanned with the *same* vLLM script, not the HF eval.
- **Teacher/trainer GPU collision.** Trainer FSDP bound to `cuda:0` where the frozen teacher
  (`--teacher-device 0`, ~52 GB) already sat → OOM at first forward. Hidden in an earlier
  run because rollouts were failing before the trainer ever stepped. Fix: teacher to GPU1.
- **`FileNotFoundError` every rollout.** `runs/` is git-ignored → the case crates never
  reached a fresh box → every rollout's sandbox copy failed. Copy the cases up explicitly.
- **Disk exhaustion mid-run.** Each rollout copies a crate and compiles a `target/`;
  nothing cleaned them → 22 GB of sandboxes filled the disk → trainer died **saving a
  checkpoint** (`No space left on device (os error 28)`). Fix: a janitor deleting completed
  sandboxes (`find runs/rlvr1/sandboxes -mmin +3 -delete`) + pruning rollout `.bin` dumps.

Each of these *looks like a model result* if unchased. "Is this number real?" is the job.

---

## 8. Verdict + how to read it

- SFT installs the protocol and the skill; it works at the verifier level (terminal 0.99).
  Its weakest part is clean `FINAL` termination under the HF/Transformers formal eval;
  the same prompts showed much more verifier success under vLLM pass@8.
- **RL can't install an unsampled behavior** (stopping) and **can't lift a saturated band**
  (capability). Both are *measured*, both are scale-independent.
- **`pass@k` banding is the cheap pre-flight**: empty / ceiling'd band ⇒ RL won't help ⇒
  believe it. This pool: 0 capability-gap, 95/134 solved ⇒ SFT_V1 is the deliverable.
- A real lift needs **harder data** (genuine skill gap, baseline 1–3/8 from difficulty not
  noise), not a knob.

## 9. Still open

- `max_completion_tokens=1536` did not hard-cap prior rollouts (~4500 tok / 16 turns);
  confirm per-turn vs per-rollout semantics and that deep cases fit `seq_len=5120`.
- The stopping reward (§1 prior config) was never run *clean* (corrected reward, normal
  episodes, full-69) — only V1 (broken) and B (with horizon truncation). It would not beat
  SFT_V1 (the measurement says so), but the clean negative is technically unrecorded.
- Generate a true capability-gap set (baseline 1–3/8) and re-band; that's the only path to
  a positive RLVR result on this agent.

Figures: `blog/make_figures.py` regenerates all five from `results/` (tfevents, eval JSONs,
rollouts). Narrative + PRIME-RL/`verifiers` primer: `blog/blog_copy.md`.
