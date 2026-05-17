# Baseline ablation

Reference run with no ablations applied. Establishes the four headline metrics every later ablation is compared against.

## Setup
- 2x A100 80GB (GPU 0 = vLLM rollout, GPU 1 = trainer)
- Trainer: `Qwen/Qwen3-4B-Base` + LoRA (r64, α64) + `lm_head`, init from `JayZenith/glyph-sft-v1-adapter`
- Rollout: `JayZenith/glyph-sft-v1` (full SFT'd model)
- Data: `runs/rl1/rust_tool_prompts_8.jsonl` (48 rollouts/step)
- Defaults: `SEQ_LEN=2048`, `MAX_MODEL_LEN=2048`, `MAX_COMPLETION_TOKENS=512`, `gpu_memory_utilization=0.7`

## Exact command
```bash
OUTPUT_DIR=/workspace/glyph/rl/rl_ablations/baseline \
  bash setup/run_task_trace_2xa100.sh
```

## Truncation-risk markers
Added to `rl/task_trace.py`:
- `_rust_tool_reward`: prints `[TRUNCATION_RISK] len=<chars> ~<approx_tokens>` when completion >1400 chars
- `RustToolEnv.env_response`: prints `[ENV_TRUNCATION_RISK] pre-response len=<chars> ~<approx_tokens>` when incoming messages >1200 chars

## Headline metrics (snapshot @ orch step 13 / trainer step 12)

| metric | value |
|---|---|
| Avg reward per trajectory (over 14 orch steps) | **−1.515** |
| Avg training loss (over 13 trainer steps) | **0.0126** |
| % rollouts filtered by zero_advantage | **0%** (filter is in monitor mode, no detections logged) |
| Gibberish filter detections (monitor only) | 7 / 672 rollouts = **1.04%** |
| `[TRUNCATION_RISK]` events (completion >1400 chars) | **743** events across ~672 trajectory scorings (≈ 110% — `_rust_tool_reward` re-scored some rollouts during off-policy replays) |
| `[ENV_TRUNCATION_RISK]` events (env_response input >1200 chars) | **83,622** (per-turn, many turns per rollout) |

### Per-step reward (orchestrator)
| step | reward | seq_len (tok/sample) |
|---|---|---|
| 0 | −1.4560 | 1338.4 |
| 1 | −1.0524 | 1310.0 |
| 2 | −1.4724 | 1284.8 |
| 3 | −1.4507 | 1347.8 |
| 4 | −1.5777 | 1327.8 |
| 5 | −1.2815 | 1311.4 |
| 6 | −1.6619 | 1403.6 |
| 7 | −1.2599 | 1262.1 |
| 8 | −1.4133 | 1315.4 |
| 9 | −1.7107 | 1378.5 |
| 10 | −1.1467 | 1206.0 |
| 11 | −1.9983 | 1445.0 |
| 12 | −1.3944 | 1305.3 |
| 13 | −2.2303 | 1454.0 |

### Per-step trainer loss
| step | loss | entropy | mismatch KL | grad norm |
|---|---|---|---|---|
| 0 | 0.0130 | 0.6114 | 0.4645 | 0.2393 |
| 1 | 0.0162 | 0.6534 | 0.5744 | 3.0156 |
| 2 | 0.0151 | 0.6168 | 0.5788 | 7.3438 |
| 3 | 0.0117 | 0.6152 | 0.4158 | 0.2773 |
| 4 | 0.0165 | 0.6362 | 0.4234 | 0.5078 |
| 5 | 0.0085 | 0.6047 | 0.3908 | 0.2207 |
| 6 | 0.0125 | 0.6060 | 0.3915 | 0.6836 |
| 7 | 0.0100 | 0.6350 | 0.4530 | 0.8789 |
| 8 | 0.0169 | 0.6091 | 0.5257 | 0.3242 |
| 9 | 0.0144 | 0.6104 | 0.4358 | 1.8750 |
| 10 | 0.0109 | 0.6319 | 0.4142 | 0.2969 |
| 11 | 0.0082 | 0.5893 | 0.3917 | 0.5039 |
| 12 | 0.0101 | 0.6480 | 0.3967 | 0.2539 |

## Re-extracting from the logs
```bash
# loss curve
grep -aE 'SUCCESS Step' logs/trainer.log | sed 's/\x1b\[[0-9;]*m//g'
# reward curve
grep -a  'SUCCESS Step' logs/orchestrator.log | sed 's/\x1b\[[0-9;]*m//g'
# filter detections (monitoring mode)
grep -aE 'Detected [0-9]+/' logs/orchestrator.log | sed 's/\x1b\[[0-9;]*m//g'
# truncation marker counts
grep -ac '\[TRUNCATION_RISK\]' launch.log
grep -ac '\[ENV_TRUNCATION_RISK\]' launch.log
```

## Contents
- `launch.log` — wrapper stdout/stderr (truncation-risk markers live here)
- `logs/{trainer,orchestrator}.log` — PRIME-RL process logs (inference.log excluded — 700M+ of per-request vLLM 2049-token validation noise; not needed for baseline metrics)
- `rollouts/step_<N>/rank_0.bin` — per-rollout transcripts + rewards
- `configs/` — resolved trainer/orchestrator/inference TOMLs for this run
- `wandb/` — offline W&B run

Remote source: `/workspace/glyph/rl/rl_ablations/baseline/` on the instance. Re-sync with:
```bash
rsync -av --exclude run_default --exclude 'checkpoints/*' --exclude 'logs/inference.log' \
  -e 'ssh -p 19634' root@162.192.107.46:/workspace/glyph/rl/rl_ablations/baseline/ \
  rl/rl_ablations/baseline/
```
