# Baseline

Reference, no ablation. `OUTPUT_DIR=/workspace/glyph/rl/rl_ablations/baseline bash setup/run_task_trace_2xa100.sh`

| metric | value |
|---|---|
| Avg reward per trajectory (14 orch steps) | **−1.515** |
| % trajectories truncated (`[TRUNCATION_RISK]` events / rollouts) | **743 / 672 = 110.6%** |
| % rollouts filtered by zero_advantage | **0%** (monitor mode) |
| Avg trainer loss (13 steps) | **0.0126** |

Loss curve: 0.0130, 0.0162, 0.0151, 0.0117, 0.0165, 0.0085, 0.0125, 0.0100, 0.0169, 0.0144, 0.0109, 0.0082, 0.0101
