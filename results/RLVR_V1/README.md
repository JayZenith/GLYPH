# RLVR_V1 results

Artifacts for plotting the RLVR_V1 run.

- **model**: JayZenith/RLVR_V1 (= rlvr_final_penaltyv7 weights/step_25)
- **base**: JayZenith/SFT_V1
- **data**: JayZenith/RLVR_V1_DATASET (rl_prompts_hard_recover.jsonl, 1042 rows)
- **git commit**: b194f7e
- **hyperparams**: lr 1e-6, temp 0.6, rollouts/example 4, batch 24, max_tool_rounds 15, max_completion_tokens 1536, max_steps 200

## Files
- `training_metrics.csv` — per-step reward / seq-length / wall-time (steps 0-50)
- `canary_summary.csv` — per-checkpoint 6-prompt heldout canary metrics
- `canary_eval/step_*.json` — full per-case canary traces + metrics
- `wandb/run-*.wandb` — raw W&B offline history (full metric set)

## Checkpoint selection
Canary valid_traces: {25: 3, 50: 2}. step_25 chosen (3/6 vs 2/6 at step_50;
25->50 regression consistent with prior runs) and published as JayZenith/RLVR_V1.
