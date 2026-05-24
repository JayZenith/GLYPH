#!/usr/bin/env bash
set -euo pipefail

# Kill PRIME-RL launcher, trainer, helper tails, and common child helpers.
# Optionally delete an old RL output directory after cleanup.
# Usage:
#   bash rl/setup/cleanup_rl_processes.sh
#   bash rl/setup/cleanup_rl_processes.sh /workspace/glyph/outputs/ /workspace/glyph/outputs/rlvr1_runY

ROOT_MATCH="${1:-/workspace/glyph/outputs/}"
OLD_OUTPUT_DIR="${2:-}"

echo "Before:"
ps -eo pid,ppid,cmd \
  | grep -E 'python rl/train.py|prime_rl|torchrun|vllm|inference|PRIME-RL::Infer|PRIME-RL::Trainer|PRIME-RL::Orchestrator|wandb-core|wandb-xpu|resource_tracker|tail -F' \
  | grep -v grep || true
echo
nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader || true
echo

pkill -TERM -f 'python rl/train.py' || true
pkill -TERM -f 'prime_rl.trainer.rl.train' || true
pkill -TERM -f 'torchrun --role=trainer' || true
pkill -TERM -f 'PRIME-RL::Inference' || true
pkill -TERM -f 'PRIME-RL::Infer' || true
pkill -TERM -f 'PRIME-RL::Trainer' || true
pkill -TERM -f 'PRIME-RL::Orchestrator' || true
pkill -TERM -f '/workspace/prime-rl-src/.venv/bin/inference @' || true
pkill -TERM -f "tail -F ${ROOT_MATCH}" || true
pkill -TERM -f 'wandb-core' || true
pkill -TERM -f 'wandb-xpu' || true
pkill -TERM -f 'multiprocessing.resource_tracker' || true

sleep 5

pkill -KILL -f 'python rl/train.py' || true
pkill -KILL -f 'prime_rl.trainer.rl.train' || true
pkill -KILL -f 'torchrun --role=trainer' || true
pkill -KILL -f 'PRIME-RL::Inference' || true
pkill -KILL -f 'PRIME-RL::Infer' || true
pkill -KILL -f 'PRIME-RL::Trainer' || true
pkill -KILL -f 'PRIME-RL::Orchestrator' || true
pkill -KILL -f '/workspace/prime-rl-src/.venv/bin/inference @' || true
pkill -KILL -f "tail -F ${ROOT_MATCH}" || true
pkill -KILL -f 'wandb-core' || true
pkill -KILL -f 'wandb-xpu' || true
pkill -KILL -f 'multiprocessing.resource_tracker' || true

sleep 2

echo "After:"
ps -eo pid,ppid,cmd \
  | grep -E 'python rl/train.py|prime_rl|torchrun|vllm|inference|PRIME-RL::Infer|PRIME-RL::Trainer|PRIME-RL::Orchestrator|wandb-core|wandb-xpu|resource_tracker|tail -F' \
  | grep -v grep || true
echo
nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader || true

if [ -n "$OLD_OUTPUT_DIR" ]; then
  echo
  echo "Removing old output dir: $OLD_OUTPUT_DIR"
  rm -rf -- "$OLD_OUTPUT_DIR"
  echo "Removed: $OLD_OUTPUT_DIR"
fi
