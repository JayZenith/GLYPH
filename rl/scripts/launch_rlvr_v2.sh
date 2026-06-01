#!/usr/bin/env bash
# RLVR v2 — corrected recipe. See rl/RLVR_NOTES.md for why each value changed.
# Prereqs: SFT_V2 trained+pushed (signal_v2), and it must beat SFT_V1's 52/69 on
# the held-out 69 BEFORE running this. RL is a nudge, not a fix for weak SFT.
set -euo pipefail

MODEL="${MODEL:-JayZenith/SFT_V2}"          # base + teacher (anchor target)
OUTPUT="${OUTPUT:-outputs/rlvr_v2}"
DATA="${DATA:-synthetic_data/rl_prompts_v2_1323.jsonl}"

python rl/train.py \
  --model "$MODEL" \
  --teacher-model "$MODEL" \
  --teacher-device 0 \
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
  --teacher-max-model-len 12288 \
  --max-completion-tokens 1536 \
  --learning-rate 5e-7 \
  --weight-decay 0.01 \
  --checkpoint-interval 25 \
  --temperature 0.8 \
  --gpu-memory-utilization 0.70 \
  --teacher-gpu-memory-utilization 0.50 \
  --max-tool-rounds 15 \
  --tool-timeout 30 \
  --port 8010 \
  --teacher-port 8011

# Gating (run on a SEPARATE 1-GPU box, async, so this multi-GPU box never blocks):
#   fast, per checkpoint  -> sft/evals/eval_prompts_smoke_12.yaml  (post_eval_smoke_12)
#   full, on 2-3 best     -> sft/evals/eval_prompts_heldout_69.yaml (post_eval_heldout_69)
# Early-stop on held-out; the best checkpoint is usually early (~step 25).
