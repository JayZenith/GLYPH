# RLVR — lessons and the current recipe

Two RL runs aimed at *teaching the model to stop* (emit FINAL after a passing
verifier, instead of churning to the round cap). Both regressed. The lessons
below are why the project pivoted to **capability lift** (raise solve-rate on
the partial-solve band) instead.

## What we tried, what we learned

**RLVR_V1** — stacked-penalty reward to force stopping. Collapsed: held-out
52→20 valid, clean_end 0.75→0.33, terminal 0.99→0.70, task_failure 1→21. Got
worse at things the reward never touched → capability collapse, not a
finalization bug. Causes: penalties stacked to −13..−23 vs +12 for a solve (one
bad rollout dominated its GRPO group); no positive path on unsolved tasks (every
option scored negative → optimizer fled the working SFT behaviors); SFT anchor
off (`teacher-tau 0.01`); ~56% zero-advantage groups; exploration cut (temp
0.8→0.6, rollouts 8→4). **Lesson: bounded, success-anchored reward + a hard SFT
anchor + enough rollout variance, or GRPO collapses.**

**RLVR_B** — corrected bounded reward **+** `--terminal-on-success` (end the
episode one turn after the first pass, forcing the next turn terminal — tightest
possible credit on the stop decision). Still collapsed: full eval 52→19, terminal
68→46 at step 25. A 12-prompt smoke set hid it (only 3 churn cases). Exactly one
case improved. **Caveat — don't oversell B:** it changes *two* things vs V1
(reward and horizon truncation), so it is **not** a clean isolation of the reward.
What it shows is narrow but real: even the most aggressive credit-assignment trick
for stopping still regresses. The clean "corrected reward, normal episodes,
full-69" run was never taken past smoke, so it doesn't exist as evidence.

**The load-bearing evidence is the measurement, not the A/B.** Train prompts emit
~0 churn (temp-0 = 0 churn, 72 clean / 24 unsolved of 96; temp-0.8 depth≥3 =
0/16). RL only reinforces variance present in its rollouts; if the policy never
churns-then-recovers-then-stops on train prompts there is no gradient — regardless
of reward or truncation. The runs *corroborate* (every stop-targeted variant
regressed); the measurement *explains*. **You cannot RL a behavior the policy
doesn't sample.** Closing the termination gap is an **SFT-coverage** job (put the
hard held-out shapes in training so the model samples them), not an RL one.

## The pivot — what RLVR is actually for here

Lift solve-rate where the policy *partially* solves, because that's where reward
variance (some rollouts pass, some don't) gives GRPO a gradient.

- **pass@k scan** (`sft/passk_scan.py`) bands each train prompt by
  `terminal_tool_success`: `0<solves<k` = **rlvr-target** (gradient),
  `==k` = solved (no variance), `==0` = capability-gap (RL can't cross).
- **RL only on the rlvr-target band.** See `rl/setup/rl_setup_training.md`.

## Current reward (`rl/task_trace.py`, `DEFAULT_REWARD_CONFIG`)

Verifier-dominant, bounded, **termination tails zeroed** for the capability run:

```text
verifier_success_bonus       +8.0   <- the whole signal
structure_valid_bonus        +0.5   } format floor
no_call_penalty              -2.0   }
malformed_call_penalty       -1.0   } per typo, cap 4
final_once / missing_final    0.0   } termination tails -- ZEROED
verifier_success_clean_final  0.0   } (this run optimizes solving, not stopping)
tool_after_success (churn)    0.0   }
tool_budget_exhausted         0.0   }
```

One scalar per rollout. Properties locked by `reward_golden_tests.py` (solving
dominates by +8, termination neutral, format floor applies, bounded). To restore
the stopping reward (e.g. after SFT covers the OOD tail), un-zero the tails.

## Recipe knobs that matter

- `teacher-tau 0.2` — hard SFT anchor (`0.01` collapsed RLVR_V1).
- `rollouts-per-example 8`, `temperature 0.8` — within-group variance is the
  gradient on a partial-solve prompt; `4 / 0.6` starved it.
- `zero_advantage` filter enforced (`rl/configs/task_trace/orchestrator.toml`).
- Do NOT pass `--terminal-on-success` (that was the RLVR_B stopping experiment).

## Procedure

1. pass@k scan → freeze rlvr-target band → RL prompt subset.
2. RLVR from SFT_V1 on that band, corrected reward + knobs above.
3. Gate each checkpoint with pass@k on the SAME band, on a separate 1-GPU box.
4. Early-stop (winner ~step 25); kill if pass@k drops below SFT_V1 for 2 checkpoints.
5. Artifact = in-set pass@1/pass@k lift, SFT_V1 vs best checkpoint.

## Still open
- `max_completion_tokens=1536` did not hard-cap prior rollouts (~4500 tokens / 16
  turns). Confirm per-turn vs per-rollout and that deep cases fit `seq_len=5120`.
