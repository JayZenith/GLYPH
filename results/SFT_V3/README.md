# SFT_V3 results

- data: signal_v3 (deep recovery x1 + clean PASS->FINAL oversampled x2), 2083 rows
- run: SIGNAL_v3_SFT_E3_LR2E5 (3 epochs, lr 2e-5, max_seq_length 12000)

## Held-out 69
valid 50/69 | clean_end 0.725 | final_after_last_tool 0.725 | terminal 0.986 | avg 12.57
failure_buckets: {'dirty_final': 19, 'final_before_tool_completion': 19, 'missing_final': 19, 'task_failure': 1}

## vs prior
SFT_V1 0.75 | SFT_V2 0.70 | SFT_V3 0.725 clean_end. Stopping plateaued ~0.72-0.75 -> data-coverage exhausted, termination is the RL target.

## Training
steps 573 | final loss 0.0355 | epochs 3.0
