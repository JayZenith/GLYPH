# Ablation #1 — `max_chars` 1800 → 500

`rl/rust/results.py` default `max_chars=500` (was 1800). Same launcher/data/model as baseline.

Command: `OUTPUT_DIR=/workspace/glyph/rl/rl_ablations/max_chars500 bash setup/run_task_trace_2xa100.sh`

| metric | value | vs baseline |
|---|---|---|
| Avg reward per trajectory (13 orch steps) | **−1.395** | −1.515 |
| % trajectories truncated (`[TRUNCATION_RISK]` events / rollouts) | **1399 / 624 = 224.2%** | 110.6% |
| % rollouts filtered by zero_advantage | **0.16%** (1 detection over 624, monitor mode) | 0% |
| Avg trainer loss (22 steps) | **0.0107** | 0.0126 |

Loss curve: 0.0095, 0.0153, 0.0106, 0.0063, 0.0087, 0.0132, 0.0151, 0.0077, 0.0067, 0.0132, 0.0084, 0.0113, 0.0124, 0.0071, 0.0130, 0.0143, 0.0181, 0.0074, 0.0155, 0.0109, 0.0132, 0.0085
