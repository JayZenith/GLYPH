#!/usr/bin/env bash
# RLVR — corrected recipe. See rl/RLVR_NOTES.md for why each value changed.
# Base = SFT_V1: it already solves (terminal 68/69); the only gap RL fixes is
# stopping with one FINAL after success. Minimal "solve -> stop" reward.
set -euo pipefail

MODEL="${MODEL:-JayZenith/SFT_V1}"          # base + external teacher anchor target
OUTPUT="${OUTPUT:-outputs/rlvr_signal_v3_pool_b_mixed}"
DATA="${DATA:-synthetic_data/rl_prompts_signal_v3_pool_b_mixed.jsonl}"
TEACHER_PORT="${TEACHER_PORT:-8011}"

echo "Expected external teacher inference at http://127.0.0.1:${TEACHER_PORT}"

python rl/train.py \
  --model "$MODEL" \
  --teacher-model "$MODEL" \
  --teacher-tau 0.2 \
  --prime-rl-gpu-ids 2,3 \
  --num-infer-gpus 1 \
  --num-train-gpus 1 \
  --gpus-per-node 2 \
  --data "$DATA" \
  --output "$OUTPUT" \
  --max-steps 200 \
  --batch-size 24 \
  --rollouts-per-example 8 \
  --seq-len 5120 \
  --max-model-len 12288 \
  --max-completion-tokens 1536 \
  --learning-rate 5e-7 \
  --weight-decay 0.01 \
  --checkpoint-interval 25 \
  --temperature 0.8 \
  --gpu-memory-utilization 0.70 \
  --max-tool-rounds 15 \
  --tool-timeout 30 \
  --port 8010 \
  --teacher-port "$TEACHER_PORT"

# Gating (run on a separate 1-GPU box, async, so this multi-GPU box never blocks):
#   sft/evals/eval_prompts_heldout_69.yaml (post_eval_heldout_69)
# Early-stop on held-out; the best checkpoint is usually early (~step 25).
