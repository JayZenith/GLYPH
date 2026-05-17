# 2x A100 80GB RL Setup

Reproducible bring-up for the task-trace RL run (trainer on GPU 1, vLLM rollout on GPU 0, rollout starts from `JayZenith/glyph-sft-v1`, trainer trains `Qwen/Qwen3-4B-Base` + LoRA + `lm_head` from `JayZenith/glyph-sft-v1-adapter`).

## Layout
- Glyph repo: `/workspace/glyph`
- PRIME-RL checkout (separate, uv-managed Python 3.12 env): `/workspace/prime-rl-src`

## 1. Install PRIME-RL + patches

```bash
cd /workspace/glyph
bash setup/install_prime_rl.sh
```

This:
- installs `uv`, Python 3.12, clones `prime-rl` at `/workspace/prime-rl-src`, syncs submodules
- installs flash-attn (pinned wheel for torch 2.11 / cu128 / cp312 / abi=TRUE)
- runs `setup/patch_install.py` against the installed `prime_rl` package and the installed `vllm` package

The patches (idempotent):
- `prime_rl`: bootstrap trainer LoRA + `lm_head` from `PRIME_RL_INIT_ADAPTER`, forward that env to subprocesses, full-weights inference path (`PRIME_RL_INFERENCE_FULL_WEIGHTS=1`), filesystem broadcast that merges LoRA into base weights, custom vLLM `FileSystemWeightUpdateWorker` that calls the model's own `load_weights`, orchestrator `compute_teacher_logprobs` via raw httpx, ckpt save tolerant of missing `revert_weight_conversion`
- `vllm/model_executor/models/qwen3.py`: replaces the thin `load_weights` with the qkv/gate_up packed-weight loader from `qwen2.py`, plus the required imports (`default_weight_loader`, `maybe_remap_kv_scale_name`, `is_pp_missing_parameter`). Required for inference hot-reload after trainer checkpoint 1 (otherwise: `KeyError: 'layers.0.mlp.gate_up_proj.weight'`).

## 2. Smoke test (dry-run config validation)

```bash
bash setup/smoke_test_2xa100.sh
```

Exits non-zero if the dry-run config is wrong; otherwise prints `smoke test passed`.

## 3. Run RL

```bash
OUTPUT_DIR=/workspace/glyph/outputs/task_trace_rl_runN \
  bash setup/run_task_trace_2xa100.sh
```

Defaults: `SEQ_LEN=2048`, `MAX_MODEL_LEN=2048`, `MAX_COMPLETION_TOKENS=512`, `gpu-memory-utilization=0.7`, GPUs `0,1`.

Logs land in `$OUTPUT_DIR/logs/{orchestrator,trainer,inference}.log`.

## 4. Verifying the run

- `Step 0` / `Step 1` SUCCESS in orchestrator + trainer logs
- `Orchestrator resumed: checkpoint 1 ready` (inference hot-reload survived)
- Successive `checkpoint 2 ready`, `checkpoint 3 ready`, ... show stable reload

## Known benign noise
- vLLM `VLLMValidationError: The prompt is 2049 tokens, ... maximum context length of 2048` lines in `inference.log` are per-request rejections; they don't kill the engine. If they become a quality issue, raise `MAX_MODEL_LEN` (e.g. `MAX_MODEL_LEN=2560`) and keep `SEQ_LEN=2048`.

## Re-running just the patch

```bash
/workspace/prime-rl-src/.venv/bin/python \
  /workspace/glyph/setup/patch_install.py /workspace/prime-rl-src
```

The patcher is idempotent and locates `vllm/qwen3.py` via the running Python's import system if a non-repo target is passed.
