#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRIME_RL_DIR="${PRIME_RL_DIR:-/workspace/prime-rl-src}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/outputs/smoke_2xa100}"
DATA_PATH="${DATA_PATH:-$ROOT_DIR/runs/rl1/rust_tool_prompts_8.jsonl}"
CASES_ROOT="${CASES_ROOT:-$ROOT_DIR/runs/rl1/rust_tool_cases}"
ADAPTER="${ADAPTER:-JayZenith/glyph-sft-v1-adapter}"
ROLLOUT_MODEL="${ROLLOUT_MODEL:-JayZenith/glyph-sft-v1}"

source "$PRIME_RL_DIR/.venv/bin/activate"

mkdir -p "$OUT_DIR"

export PYTHONPATH="$ROOT_DIR:$ROOT_DIR/rl${PYTHONPATH:+:$PYTHONPATH}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1}"

python3 - <<'PY'
import torch
count = torch.cuda.device_count()
if count != 2:
    raise SystemExit(f"expected exactly 2 visible GPUs, found {count}")
print(f"visible_gpus={count}")
PY

if [ ! -f "$DATA_PATH" ]; then
  python3 "$ROOT_DIR/rl/rust/prepare_cases.py" --root "$CASES_ROOT" --output "$DATA_PATH"
fi

python3 "$ROOT_DIR/rl/train.py" \
  --adapter "$ADAPTER" \
  --rollout-init-model "$ROLLOUT_MODEL" \
  --data "$DATA_PATH" \
  --output "$OUT_DIR" \
  --seq-len 1536 \
  --max-model-len 1536 \
  --max-completion-tokens 384 \
  --gpu-memory-utilization 0.7 \
  --dry-run \
  --dump-config "$OUT_DIR/config.json" \
  > "$OUT_DIR/dry_run.json"

python3 - <<'PY' "$OUT_DIR/config.json"
import json, sys
cfg = json.load(open(sys.argv[1]))
assert cfg["deployment"]["gpus_per_node"] == 2
assert cfg["deployment"]["num_train_gpus"] == 1
assert cfg["deployment"]["num_infer_gpus"] == 1
assert cfg["trainer"]["model"]["name"] == "Qwen/Qwen3-4B-Base"
assert cfg["orchestrator"]["model"]["name"] == "JayZenith/glyph-sft-v1"
assert cfg["inference"]["model"]["name"] == "JayZenith/glyph-sft-v1"
mods = cfg["trainer"]["model"]["lora"]["modules_to_save"]
assert "lm_head" in mods
print("smoke_ok=1")
PY

echo "smoke test passed"
