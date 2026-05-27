# 1093

SFT and RLVR prep for Rust/tool-use traces. The structure rules live in [docs/agent_trace.md](/home/jay-zenith/Desktop/TASK/docs/glyph.md:1).

## Setup on Ampere or Blackwell
```bash
git clone https://github.com/JayZenith/glyph.git
cd glyph
bash sft/setup/install_sft_env.sh
source .venv/bin/activate
hf auth login
```

# Training run on 259

# Eval run on 9


## Real Training Run
```bash
cd /workspace/glyph
source .venv/bin/activate
python -m sft.train \
    --model Qwen/Qwen3-4B-Base \
    --tokenizer Qwen/Qwen3-4B-Base \
    --data synthetic_data/signal_259.jsonl \
    --output runs/SIGNAL_259_SFT \
    --epochs 3 \
    --batch-size 1 \
    --grad-accum 8 \
    --lr 5e-6 \
    --max-seq-length 2048 \
    --save-total-limit 1 \
    --no-train-split
```

Defaults:
```bash
masking_mode: str = "assistant_only"

warmup_ratio: float = 0.03
weight_decay: float = 0.01
lr_scheduler_type: str = "cosine"

bf16: bool = True
tf32: bool = True
gradient_checkpointing: bool = False

save_strategy: str = "steps"
save_steps: int = 500

logging_steps: int = 10
logging_first_step: bool = True
report_to: str = "tensorboard"
```


## Real Eval Runs
<!--
```bash
python -m sft.eval_test_loss \
  --base Qwen/Qwen3-4B-Base \
  --sft runs/GLYPH_SFT_FINAL/final \
  --test-set runs/GLYPH_SFT_FINAL/test_set \
  --output runs/GLYPH_SFT_FINAL/eval_test_loss.json
```-->

```bash
python -m sft.eval_formal \
    --sft-model runs/SIGNAL_259_SFT/final \
    --train-data synthetic_data/signal_259.jsonl \
    --prompt-section post_eval \
    --output runs/SIGNAL_259_SFT/eval_formal_post_eval.json \
    --max-new-tokens 6000 \
    --max-tool-rounds 8 \
    --cases-root runs/rlvr1/rust_cases/eval \
    --token-stream
```

## Key Results


Remaining failure's:

## Notes

- reported repo commit: ``
- dataset hf: `synthetic_data/signal_259.jsonl`
