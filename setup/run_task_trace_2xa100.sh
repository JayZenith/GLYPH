#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRIME_RL_DIR="${PRIME_RL_DIR:-/workspace/prime-rl-src}"
ADAPTER="${ADAPTER:-JayZenith/glyph-sft-v1-adapter}"
ROLLOUT_MODEL="${ROLLOUT_MODEL:-JayZenith/glyph-sft-v1}"
DATA_PATH="${DATA_PATH:-$ROOT_DIR/runs/rl1/rust_tool_prompts_8.jsonl}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/outputs/task_trace_rl}"
PORT="${PORT:-8000}"
SEQ_LEN="${SEQ_LEN:-2048}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-2048}"
MAX_COMPLETION_TOKENS="${MAX_COMPLETION_TOKENS:-512}"

source "$PRIME_RL_DIR/.venv/bin/activate"

export PYTHONPATH="$ROOT_DIR:$ROOT_DIR/rl${PYTHONPATH:+:$PYTHONPATH}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1}"

exec python3 "$ROOT_DIR/rl/train.py" \
  --adapter "$ADAPTER" \
  --rollout-init-model "$ROLLOUT_MODEL" \
  --port "$PORT" \
  --data "$DATA_PATH" \
  --output "$OUTPUT_DIR" \
  --gpu-memory-utilization 0.7 \
  --seq-len "$SEQ_LEN" \
  --max-model-len "$MAX_MODEL_LEN" \
  --max-completion-tokens "$MAX_COMPLETION_TOKENS"
