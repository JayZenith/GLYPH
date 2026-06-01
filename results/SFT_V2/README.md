# SFT_V2 results

- model: JayZenith/SFT_V2  (Qwen3-4B-Base, 3 epochs, lr 2e-5, max_seq_length 11000, grad ckpt on)
- data: JayZenith/SFT_V2_DATASET (signal_v2_1323, variable-depth recovery)
- run: SIGNAL_1323_SFT_E3_LR2E5

## Held-out 69
valid_traces 48/69 | clean_end 0.696 | terminal_tool_success 0.957 | avg_score 12.30
failure_buckets: {'dirty_final': 21, 'final_before_tool_completion': 21, 'missing_final': 21, 'task_failure': 3}

## Training
steps: 498 | final train loss: 0.0332 | epochs: 3.0

## Files
- eval_formal_heldout_69.json  full per-case eval
- trainer_state.json           full loss history
- tensorboard/                 raw tfevents
