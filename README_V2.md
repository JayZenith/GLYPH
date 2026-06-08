# Clean SFT_HALF_A -> RL_POOL_B RLVR Runbook

This is the runbook for the current clean experiment. The goal is not to revive
old RLVR runs. The goal is one fair LoRA RLVR attempt from `SFT_HALF_A` on the
non-overlapping `RL_POOL_B` prompts, then a strict held-out-69 eval.

## Data

Created split files:

- `synthetic_data/signal_v3_sft_half_a.jsonl`: 1,042 rows, 762 unique cases.
- `synthetic_data/signal_v3_rl_pool_b.jsonl`: 1,041 rows, 760 unique cases.
- `synthetic_data/rl_prompts_signal_v3_pool_b.jsonl`: RL-compatible prompt manifest, 760 rows.
- `synthetic_data/signal_v3_rl_pool_b_prompts.yaml`: pass@k-compatible prompt manifest, 760 rows.
- `synthetic_data/signal_v3_split_summary.json`
- `synthetic_data/signal_v3_split_summary.md`

The split is deterministic and stratified by family, difficulty, expected
tool-sequence length, and run/test verifier family. It is grouped by `case_id`,
so duplicate/oversampled traces cannot leak across SFT and RL.

Leakage checks:

```text
case_id_overlap = 0
trace_overlap = 0
```

Important: do not pass `synthetic_data/signal_v3_rl_pool_b.jsonl` directly to
`rl/train.py`. That is SFT trace JSONL. RL training needs prompt rows with
`prompt`, `expected_tool`, `blueprint_root`, `trace_prefix`, etc. Use:

```text
synthetic_data/rl_prompts_signal_v3_pool_b.jsonl
```

Also note that `sft/train.py` deduplicates exact traces before training, so
`SFT_HALF_A`'s 1,042 rows become 762 unique traces in practice.

## SFT Training

```bash
git clone https://github.com/JayZenith/glyph.git
cd glyph
git pull --ff-only

bash sft/setup/install_sft_env.sh
source .venv/bin/activate

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

## SFT Held-Out Eval

Use this as the baseline command. For RLVR evals, change only `--sft-model`,
`--cases-root`, and `--output`.

```bash
mkdir -p results/SFT_HALF_A

python -m sft.eval_formal \
  --sft-model runs/SIGNAL_v3_HALF_A_SFT_E3_LR2E5/final \
  --train-data synthetic_data/signal_v3_sft_half_a.jsonl \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
  --prompt-section post_eval_heldout_69 \
  --cases-root runs/heldout69_sft_half_a \
  --output results/SFT_HALF_A/eval_formal_heldout_69.json \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --prompt-batch-size 4 \
  --tool-workers 8
```

Final claim metric is strict held-out `valid_trace`, not RL training reward.
If VRAM is tight, drop `--prompt-batch-size` to `2` or omit it to recover the
legacy serial path.

## Optional Pass@4 Diagnostics

RL pool pass@4:

```bash
python -m sft.passk_scan_vllm \
  --sft-model runs/SIGNAL_v3_HALF_A_SFT_E3_LR2E5/final \
  --prompt-file synthetic_data/signal_v3_rl_pool_b_prompts.yaml \
  --prompt-section rl_pool_b \
  --cases-root runs/passk_signal_v3_rl_pool_b_sft_half_a \
  -k 4 \
  --temperature 0.8 \
  --max-new-tokens 4000 \
  --max-tool-rounds 15 \
  --output results/SFT_HALF_A/passk_rl_pool_b_k4.json \
  --save-rollouts
```

Held-out-69 pass@4:

```bash
python -m sft.passk_scan_vllm \
  --sft-model runs/SIGNAL_v3_HALF_A_SFT_E3_LR2E5/final \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
  --prompt-section post_eval_heldout_69 \
  --cases-root runs/passk_heldout69_sft_half_a \
  -k 4 \
  --temperature 0.8 \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --output results/SFT_HALF_A/passk_heldout69_k4.json \
  --save-rollouts
```

## RLVR LoRA Training

Run from latest `main`. Keep the Glyph chat template enabled. Do not add
`--disable-glyph-chat-template`. Do not override reward flags unless you are
intentionally changing the experiment; current reward defaults make exact
held-out-style success the only positive reward.

```bash
git clone https://github.com/JayZenith/glyph.git
cd glyph
git pull --ff-only

PRIME_RL_ENABLE_LORA=1 bash rl/setup/install_prime_rl.sh
source /workspace/prime-rl-src/.venv/bin/activate

python rl/train.py \
  --model JayZenith/SFT_HALF_A \
  --teacher-model JayZenith/SFT_HALF_A \
  --lora-rank 16 \
  --lora-alpha 32 \
  --lora-dropout 0.0 \
  --lora-name glyph-signal-v3-pool-b-r16-a32 \
  --data synthetic_data/rl_prompts_signal_v3_pool_b.jsonl \
  --output outputs/RLVR_SIGNAL_V3_POOL_B_LORA_R16_A32 \
  --max-steps 50 \
  --batch-size 48 \
  --rollouts-per-example 8 \
  --seq-len 8192 \
  --max-model-len 16384 \
  --teacher-max-model-len 16384 \
  --max-completion-tokens 4000 \
  --learning-rate 5e-7 \
  --weight-decay 0.01 \
  --checkpoint-interval 25 \
  --temperature 0.8 \
  --teacher-tau 0.5 \
  --max-tool-rounds 15 \
  --tool-timeout 30 \
  --activation-checkpointing \
  --fused-lm-head-token-chunk-size auto \
  --gpu-memory-utilization 0.70 \
  --teacher-gpu-memory-utilization 0.50 \
  --prime-rl-gpu-ids 0,1,2 \
  --num-infer-gpus 1 \
  --num-train-gpus 2 \
  --gpus-per-node 3 \
  --port 8000 \
  --teacher-port 8001 \
  --teacher-device 3 \
  --enforce-gibberish-filter \
  --enforce-repetition-filter
```

Expected log sanity checks near startup:

```text
Enforcing gibberish filter
Enforcing repetition filter
Enforcing zero_advantage filter
```

If W&B samples show anything other than literal
`<|im_start|>assistant` / `CALL ...` / `<|im_start|>tool` / `RESULT ...`
structure, stop the run.

## RLVR Held-Out Eval

After uploading a merged checkpoint, evaluate it exactly like the SFT baseline.
This example assumes the step-25 merged model was pushed to
`JayZenith/RLVR_POOL_B_STEP25_NEXT`.

```bash
mkdir -p results/RLVR_POOL_B_STEP25_NEXT

python -m sft.eval_formal \
  --sft-model JayZenith/RLVR_POOL_B_STEP25_NEXT \
  --train-data synthetic_data/signal_v3_sft_half_a.jsonl \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
  --prompt-section post_eval_heldout_69 \
  --cases-root runs/heldout69_rlvr_pool_b_step25_next \
  --output results/RLVR_POOL_B_STEP25_NEXT/eval_formal_heldout_69.json \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --prompt-batch-size 4 \
  --tool-workers 8
```

Compare only against the SFT_HALF_A baseline:

```text
SFT_HALF_A strict held-out-69 valid_trace = 51/69
```

A valid RLVR win means the RLVR checkpoint is strictly above `51/69` on the
same held-out-69 `valid_trace` metric.
