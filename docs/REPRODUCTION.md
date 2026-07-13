# Reproducing GLYPH

This document holds the command-heavy setup that would otherwise overwhelm the
project README. Published-run provenance and known unknowns are recorded in
[`PROVENANCE.md`](PROVENANCE.md).

## Hardware used

- SFT and pass@8 evaluation: one NVIDIA RTX PRO 6000 Blackwell (96 GB).
- RLVR: four GPUs — two trainer, one student inference, one frozen teacher.
- A 150-case pass@8 run creates roughly 20 GB of disposable Cargo sandboxes.

Equivalent hardware may work. These are the configurations used for the
published artifacts, not minimum requirements.

## Checkout and environments

```bash
git clone https://github.com/JayZenith/GLYPH.git
cd GLYPH
```

SFT and evaluation:

```bash
bash sft/setup/install_sft_env.sh
source .venv/bin/activate
```

PRIME-RL training:

```bash
PRIME_RL_ENABLE_LORA=1 bash rl/setup/install_prime_rl.sh
source /workspace/prime-rl-src/.venv/bin/activate
```

## Full SFT

This produces the checkpoint published as
[`JayZenith/SFT_HALF_A_V8`](https://huggingface.co/JayZenith/SFT_HALF_A_V8).

```bash
python -m sft.train \
  --model Qwen/Qwen3-4B-Base \
  --tokenizer Qwen/Qwen3-4B-Base \
  --data synthetic_data/signal_v3_sft_half_a.jsonl \
  --output runs/SIGNAL_v3_HALF_A_SFT_E3_LR2E5 \
  --epochs 3 \
  --batch-size 1 \
  --grad-accum 8 \
  --lr 2e-5 \
  --max-seq-length 12000 \
  --no-train-split \
  --gradient-checkpointing
```

## RLVR reward arms

All arms start from the same SFT model and use the same data and training
configuration. Only the reward flags change:

- Sparse: no `--progress-*` flags.
- Dense: `--progress-compile-bonus 0.5 --progress-test-frac-bonus 2.0`.
- Compiler-aware: `--progress-error-ladder-bonus 2.5`.

Choose one arm:

```bash
# Dense
REWARD_FLAGS="--progress-compile-bonus 0.5 --progress-test-frac-bonus 2.0"
NAME=glyph-pool-b-dense-r64-a128
OUT=outputs/RLVR_POOL_B_DENSE_R64_A128

# Compiler-aware alternative
# REWARD_FLAGS="--progress-error-ladder-bonus 2.5"
# NAME=glyph-pool-b-compiler-aware-r64-a128
# OUT=outputs/RLVR_POOL_B_COMPILER_AWARE_R64_A128
```

```bash
python rl/train.py \
  --model JayZenith/SFT_HALF_A_V8 \
  --teacher-model JayZenith/SFT_HALF_A_V8 \
  --lora-rank 64 \
  --lora-alpha 128 \
  --lora-dropout 0.0 \
  --lora-name "$NAME" \
  --data synthetic_data/rl_prompts_signal_v3_pool_b_mixed_oversampled.jsonl \
  --output "$OUT" \
  --max-steps 30 \
  --batch-size 96 \
  --max-inflight-rollouts 96 \
  --rollouts-per-example 8 \
  --seq-len 16384 \
  --max-model-len 16384 \
  --max-completion-tokens 4000 \
  --learning-rate 1e-6 \
  --weight-decay 0.01 \
  --checkpoint-interval 5 \
  --temperature 0.8 \
  --teacher-tau 0.2 \
  --max-tool-rounds 15 \
  --tool-timeout 30 \
  --activation-checkpointing \
  --fused-lm-head-token-chunk-size auto \
  --gpu-memory-utilization 0.70 \
  --prime-rl-gpu-ids 0,1,2,3 \
  --num-infer-gpus 1 \
  --num-train-gpus 2 \
  --num-teacher-gpus 1 \
  --gpus-per-node 4 \
  --port 8000 \
  --enforce-gibberish-filter \
  --enforce-repetition-filter \
  $REWARD_FLAGS
```

The trainer and sampling path did not expose complete seed controls. Each arm
in the published comparison is one training run; do not treat the comparison
as causal reward-shape attribution.

## Export an RL LoRA

Export the served broadcast, not the trainer checkpoint:

```bash
python rl/scripts/export_prime_lora_adapter.py \
  --base-model JayZenith/SFT_HALF_A_V8 \
  --adapter-dir "$OUT/run_default/broadcasts/step_10" \
  --output "$OUT/hf_adapter_step10"
```

## Pass@8 evaluation

`valid@8` counts a prompt when at least one of eight sampled rollouts reaches
terminal Cargo success and ends with one clean `FINAL`. Published evaluations
used temperature 0.8, top-p 1.0, 4,000 new tokens, and 20 tool rounds.

SFT:

```bash
CUDA_VISIBLE_DEVICES=0 python -m sft.passk_scan_vllm \
  --sft-model JayZenith/SFT_HALF_A_V8 \
  --prompt-file sft/evals/eval_prompts_heldout_150.yaml \
  --prompt-section post_eval_heldout_150 \
  --cases-root runs/passk8_heldout150_sft \
  -k 8 \
  --temperature 0.8 \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --output results/SFT_HALF_A_V8/passk8_heldout150.json \
  --gpu-memory-utilization 0.90 \
  --max-model-len 24576 \
  --prompt-batch-size 8 \
  --save-rollouts
```

RL adapter:

```bash
CUDA_VISIBLE_DEVICES=0 python -m sft.passk_scan_vllm \
  --sft-model JayZenith/SFT_HALF_A_V8 \
  --sft-adapter JayZenith/RLVR_VFINAL_STEP10 \
  --max-lora-rank 64 \
  --prompt-file sft/evals/eval_prompts_heldout_150.yaml \
  --prompt-section post_eval_heldout_150 \
  --cases-root runs/passk8_heldout150_dense \
  -k 8 \
  --temperature 0.8 \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --output results/RLVR_VFINAL_STEP10/passk8_heldout150.json \
  --gpu-memory-utilization 0.90 \
  --max-model-len 24576 \
  --prompt-batch-size 8 \
  --save-rollouts
```

Use distinct output and sandbox paths for repetitions. Always retain rollouts.
The original harness did not expose an evaluation seed, so its repetitions
differ through runtime nondeterminism rather than controlled independent seeds.

## Reproduce the analyses

```bash
python3 analysis/retained_run_stats.py
python3 analysis/pooled_band_analysis.py
python3 analysis/never_solved_taxonomy.py
python3 analysis/training_group_stats.py
python3 analysis/test_tamper_audit.py
python3 synthetic_data/audit_blueprint_similarity.py \
  --train-data synthetic_data/rl_prompts_signal_v3_pool_b_mixed_oversampled.jsonl \
  --train-blueprints synthetic_data/blueprints \
  --eval-data synthetic_data/eval_heldout_150.jsonl \
  --eval-blueprints synthetic_data/eval_blueprints
```

The headline statistics intentionally use trace-retained evaluations only.
Count-only SFT and dense repetitions remain published as labeled context.
