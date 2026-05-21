#!/usr/bin/env bash
# Full-finetune RLVR launcher for 2x A100 80GB.
# Trainer on GPU 1, rollout vLLM + teacher anchor vLLM on GPU 0.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_RL_DIR="${PRIME_RL_DIR:-/workspace/prime-rl-src}"
MODEL="${MODEL:-JayZenith/GLYPH-SFT-V2}"
TEACHER_MODEL="${TEACHER_MODEL:-$MODEL}"
TEACHER_TAU="${TEACHER_TAU:-0.0}"
TEACHER_ANCHOR="${TEACHER_ANCHOR:-0}"
DATA_PATH="${DATA_PATH:-$ROOT_DIR/runs/rlvr1/prompts.jsonl}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/outputs/rlvr1}"
PORT="${PORT:-8000}"
TEACHER_PORT="${TEACHER_PORT:-8001}"
SEQ_LEN="${SEQ_LEN:-4096}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-4096}"
MAX_COMPLETION_TOKENS="${MAX_COMPLETION_TOKENS:-1536}"
MAX_TOOL_ROUNDS="${MAX_TOOL_ROUNDS:-3}"

source "$PRIME_RL_DIR/.venv/bin/activate"

export PYTHONPATH="$ROOT_DIR:$ROOT_DIR/rl${PYTHONPATH:+:$PYTHONPATH}"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1}"
export CARGO_HOME="${CARGO_HOME:-$HOME/.cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-$HOME/.rustup}"
export PATH="$CARGO_HOME/bin:$PATH"

ARGS=(
  python3 "$ROOT_DIR/rl/train.py"
  --model "$MODEL"
  --port "$PORT"
  --data "$DATA_PATH"
  --output "$OUTPUT_DIR"
  --gpu-memory-utilization 0.7
  --seq-len "$SEQ_LEN"
  --max-model-len "$MAX_MODEL_LEN"
  --max-completion-tokens "$MAX_COMPLETION_TOKENS"
  --max-tool-rounds "$MAX_TOOL_ROUNDS"
)

if [[ "$TEACHER_ANCHOR" == "1" ]]; then
  ARGS+=(--teacher-anchor --teacher-model "$TEACHER_MODEL" --teacher-tau "$TEACHER_TAU" --teacher-port "$TEACHER_PORT")
fi

exec "${ARGS[@]}"
