## GPU Setup

```bash
git clone https://github.com/JayZenith/glyph.git
cd glyph
git pull --ff-only
```

SFT / eval environment:

```bash
bash sft/setup/install_sft_env.sh
source .venv/bin/activate
```

PRIME-RL environment:

```bash
PRIME_RL_ENABLE_LORA=1 bash rl/setup/install_prime_rl.sh
source /workspace/prime-rl-src/.venv/bin/activate
```

## SFT_HALF_A_V8 Train

Produces `runs/SIGNAL_v3_HALF_A_SFT_E3_LR2E5/final`, uploaded as `JayZenith/SFT_HALF_A_V8`.

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

## RLVR Train

Run RLVR on GPUs 0,1,2,3. PRIME-RL launches the frozen teacher itself
(`--num-teacher-gpus 1`) and wires `orchestrator.teacher` to it, so no separate
teacher server needs to be started manually:

```bash
python rl/train.py \
  --model JayZenith/SFT_HALF_A_V8 \
  --teacher-model JayZenith/SFT_HALF_A_V8 \
  --lora-rank 64 \
  --lora-alpha 128 \
  --lora-dropout 0.0 \
  --lora-name glyph-signal-v4001-pool-b-oversampled-r64-a128 \
  --data synthetic_data/rl_prompts_signal_v3_pool_b_mixed_oversampled.jsonl \
  --output outputs/RLVR_SIGNAL_V4001_POOL_B_OVERSAMPLED_LORA_R64_A128 \
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
  --enforce-repetition-filter
```

> To use an existing external teacher instead of the auto-launched one, drop
> `--num-teacher-gpus` and pass `--teacher-base-url`/`--teacher-port`.

## Export RL LoRA

```bash
python rl/scripts/export_prime_lora_adapter.py \
  --adapter-dir outputs/RLVR_SIGNAL_V4001_POOL_B_OVERSAMPLED_LORA_R64_A128/broadcasts/step_10 \
  --base-model JayZenith/SFT_HALF_A_V8 \
  --output outputs/RLVR_SIGNAL_V4001_POOL_B_OVERSAMPLED_LORA_R64_A128/hf_adapter_step10
```

## Strict Pass@1 Eval

SFT_HALF_A_V8:

```bash
CUDA_VISIBLE_DEVICES=0 python -m sft.eval_formal \
  --sft-model JayZenith/SFT_HALF_A_V8 \
  --train-data synthetic_data/signal_v3_sft_half_a.jsonl \
  --prompt-file sft/evals/eval_prompts_heldout_150.yaml \
  --prompt-section post_eval_heldout_150 \
  --cases-root runs/heldout150_sft_half_a \
  --output results/SFT_HALF_A_V8/eval_formal_heldout_150.json \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --prompt-batch-size 8 \
  --tool-workers 16
```

RL adapter:

```bash
CUDA_VISIBLE_DEVICES=0 python -m sft.eval_formal \
  --sft-model JayZenith/SFT_HALF_A_V8 \
  --sft-adapter outputs/RLVR_SIGNAL_V4001_POOL_B_OVERSAMPLED_LORA_R64_A128/hf_adapter_step10 \
  --train-data synthetic_data/signal_v3_sft_half_a.jsonl \
  --prompt-file sft/evals/eval_prompts_heldout_150.yaml \
  --prompt-section post_eval_heldout_150 \
  --cases-root runs/heldout150_rlvr_v4001_step10 \
  --output results/RLVR_SIGNAL_V4001_STEP10/eval_formal_heldout_150.json \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --prompt-batch-size 8 \
  --tool-workers 16
```

## Pass@4 Eval

SFT_HALF_A_V8:

```bash
CUDA_VISIBLE_DEVICES=0 python -m sft.passk_scan_vllm \
  --sft-model JayZenith/SFT_HALF_A_V8 \
  --prompt-file sft/evals/eval_prompts_heldout_150.yaml \
  --prompt-section post_eval_heldout_150 \
  --cases-root runs/passk_heldout150_sft_half_a_k4 \
  -k 4 \
  --temperature 0.8 \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --output results/passk_heldout150/SFT_HALF_A_V8_k4.json \
  --gpu-memory-utilization 0.88 \
  --max-model-len 16384 \
  --prompt-batch-size 8 \
  --save-rollouts
```

RL adapter:

```bash
CUDA_VISIBLE_DEVICES=0 python -m sft.passk_scan_vllm \
  --sft-model JayZenith/SFT_HALF_A_V8 \
  --sft-adapter outputs/RLVR_SIGNAL_V4001_POOL_B_OVERSAMPLED_LORA_R64_A128/hf_adapter_step10 \
  --prompt-file sft/evals/eval_prompts_heldout_150.yaml \
  --prompt-section post_eval_heldout_150 \
  --cases-root runs/passk_heldout150_rlvr_v4001_step10_k4 \
  -k 4 \
  --temperature 0.8 \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --output results/passk_heldout150/RLVR_SIGNAL_V4001_STEP10_k4.json \
  --gpu-memory-utilization 0.88 \
  --max-model-len 16384 \
  --max-lora-rank 64 \
  --prompt-batch-size 8 \
  --save-rollouts
```
