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
solve + stop   = 12.0   <- maximum
solve + churn  =  6.0   <- solved but won't stop  (the +6 gap is the whole signal)
graceful exit  =  1.0   <- unsolved but one FINAL
loop           = -2.0   <- unsolved, no stop
```

The +8/+3 dominate and only fire on real success. The +6 solve-vs-churn gap is what teaches stopping. Removed all the old shaping (recovery bonuses, stacked penalties, first-call alignment) — 9 terms, nothing else.

## Where we are

- **Diagnosis is settled:** the only gap is stopping after a self-made deep success. It's in the data, plateaus under SFT → it's a distribution-shift problem on the model's own states = **RL's job**, not more SFT.
- **RL base = SFT_V1** (not V2/V3): it solves efficiently and its residual is *pure stopping*. V2/V3 over-recover, which RL would have to unteach first.
- **Recipe** (`rl/scripts/launch_rlvr_v2.sh`): base+teacher SFT_V1, `teacher-tau 0.2`, temp 0.8, 8 rollouts/example, zero-advantage filter on, lr 5e-7, minimal reward above, early-stop on the 69, gate each checkpoint on a 12-prompt smoke set.
- **Cheaper-credit option** (no reward complexity): end the episode at first success so the next turn is forced terminal — tightest possible credit on the stop decision.

## Kill conditions
- clean_end or terminal_tool_success drops below the SFT_V1 baseline for 2 checkpoints → stop, it's collapsing.
- Success bar: beat SFT_V1's 52/69. If RL can't, the problem is harder than stopping and we re-diagnose.

## Assets
- Models: `JayZenith/SFT_V1` (RL base), `SFT_V2`, `SFT_V3`, `RLVR_V1` (regressed, do not use).
- Data: `signal_1062` → `signal_v2_1323` → `signal_v3` (HF: `SFT_V1_DATASET`, `SFT_V2_DATASET`).
- Results: `results/SFT_V1|V2|V3`, `results/RLVR_V1` (eval json, tensorboard).
