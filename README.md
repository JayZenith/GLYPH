# glyph

GLYPH SFT and RLVR prep for Rust/tool-use traces. The GLYPH structure rules live in [docs/glyph.md](/home/jay-zenith/Desktop/TASK/docs/glyph.md:1).


## Setup on 1xA100 or 1xRTX PRO 6000 WS
```bash
git clone https://github.com/JayZenith/glyph.git
cd glyph
bash sft/setup/install_sft_env.sh
source .venv/bin/activate
hf auth login
```

```bash
====================================================
Starting training...
  Model: Qwen/Qwen3-4B-Base
  Data: synthetic_data/final_glyph_sft_dataset.jsonl (2431 samples)
  Epochs: 1
  Batch size per device: 1
  Gradient accumulation: 8
  Learning rate: 1e-05
  Max seq length: 1536
  LoRA: False
  Output: runs/GLYPH_SFT_FINAL
====================================================
```

## Train

```bash
cd /workspace/glyph
source .venv/bin/activate
python -m sft.train \
  --model Qwen/Qwen3-4B-Base \
  --data synthetic_data/final_glyph_sft_dataset_rlvr_term_v1.jsonl \
  --output runs/GLYPH_SFT_RLREADY_V1 \
  --epochs 1 \
  --no-use-lora \
  --lr 1e-5 \
  --lm-head-lr 1e-5 \
  --save-total-limit 1
```

## Eval

```bash
python -m sft.eval_test_loss \
  --base Qwen/Qwen3-4B-Base \
  --sft runs/GLYPH_SFT_FINAL/final \
  --test-set runs/GLYPH_SFT_FINAL/test_set \
  --output runs/GLYPH_SFT_FINAL/eval_test_loss.json
```

```bash
python -m sft.eval_formal \
  --sft-model runs/GLYPH_SFT_FINAL/final \
  --prompt-file sft/evals/prompts_125.yaml \
  --output runs/GLYPH_SFT_FINAL/eval_formal_125.json \
  --max-new-tokens 6000 \
  --max-tool-rounds 4
```

## Key Results


Remaining failure's:

## Repro Notes

- reported repo commit: `7d726ae31532df934d64714404b0f3c845941d3a`
- dataset hf: `JayZenith/GLYPH_SFT_DATASET`
