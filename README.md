# glyph

Reproduction notes for the successful `GLYPH_SFT_OFFICIAL_V1` supervised fine-tune.

## Outcome

- Base model: `Qwen/Qwen3-4B-Base`
- Dataset: `synthetic_data/glyph_gold50/gold_glyph_2500.jsonl`
- Split: `2000 / 250 / 250`
- Final usable checkpoint: `runs/sft_toolturn_v1_fullft1/checkpoint-250`
- HF model: `JayZenith/GLYPH_SFT`

## Important Knobs

- Full fine-tune, not LoRA: `--no-use-lora`
- Epochs: `1`
- Trunk LR: `1e-5`
- `lm_head` LR: `1.5e-5`
- Loss masking: `assistant_only`
- Max sequence length: `1024`
- Batch size: `1`
- Gradient accumulation: `8`
- Save steps: `100`
- Gradient checkpointing: on
- BF16: on

## Train

```bash
cd /workspace/glyph
git pull --ff-only
source .venv/bin/activate
python -m sft.train \
  --model Qwen/Qwen3-4B-Base \
  --data synthetic_data/glyph_gold50/gold_glyph_2500.jsonl \
  --output runs/sft_toolturn_v1_fullft1 \
  --epochs 1 \
  --no-use-lora \
  --lr 1e-5 \
  --lm-head-lr 1.5e-5 \
  --save-steps 100 2>&1 | tee runs/sft_toolturn_v1_fullft1.log
```

## Eval

Held-out test loss:

```bash
cd /workspace/glyph
source .venv/bin/activate
python -m sft.eval_test_loss \
  --base Qwen/Qwen3-4B-Base \
  --sft runs/sft_toolturn_v1_fullft1/checkpoint-250 \
  --test-set runs/sft_toolturn_v1_fullft1/test_set \
  --output runs/sft_toolturn_v1_fullft1/eval_test_loss.json
```

Formal eval, 2 prompts:

```bash
python -m sft.eval_formal \
  --sft-model runs/sft_toolturn_v1_fullft1/checkpoint-250 \
  --output runs/sft_toolturn_v1_fullft1/eval_formal_limit2.json \
  --limit 2 \
  --max-new-tokens 1200 \
  --max-tool-rounds 4
```

Formal eval, 8 prompts:

```bash
python -m sft.eval_formal \
  --sft-model runs/sft_toolturn_v1_fullft1/checkpoint-250 \
  --output runs/sft_toolturn_v1_fullft1/eval_formal_limit8.json \
  --limit 8 \
  --max-new-tokens 1200 \
  --max-tool-rounds 4
```

Formal eval, 18 prompts:

```bash
python -m sft.eval_formal \
  --sft-model runs/sft_toolturn_v1_fullft1/checkpoint-250 \
  --output runs/sft_toolturn_v1_fullft1/eval_formal_limit18.json \
  --limit 18 \
  --max-new-tokens 1200 \
  --max-tool-rounds 4
```

Clean 100-prompt held-out formal eval:

```bash
python -m sft.eval_formal \
  --sft-model JayZenith/GLYPH_SFT \
  --prompt-file sft/evals/prompts_100.yaml \
  --output results/GLYPH_SFT_OFFICIAL_V1/eval_formal_100.json \
  --limit 100 \
  --max-new-tokens 1200 \
  --max-tool-rounds 4
```

## Results

- Held-out weighted loss: `2.2446 -> 0.3284`
- Held-out perplexity: `9.44 -> 1.39`
- Clean held-out formal eval, 100 prompts: `86/100` raw
- CI-only eval: `10/10`
- Main interpretation of the 100-prompt eval: `96/100`

## Example

Prompt:

```text
In Rust, what does a `'static` lifetime usually mean in practice? Keep it concise.
```

Model output:

```text
plan {
    todo ↦ {
        1 ↦ "Explain the static lifetime concept briefly." ※ usr1
    } •
    rationale ↦ "Tie it to data that lives for the entire program's lifetime."
}

act {
    think ↦ [
        「Keep the answer focused on global or program-wide data.」 𝑝 0.9 🏷 note_static ※ [ usr1 ]
    ]
}

response「A `'static` lifetime usually means the data is valid for the entire duration of the program, like static global variables or string literals.」
※ [ note_static ]
⊨ 1
```

## Notes

- `sft/evals/prompts_100.yaml` is the main held-out benchmark.
- It was built to have `0` exact user-prompt overlaps with `gold_glyph_2500.jsonl`.
- The remaining misses were narrow planning/reference issues, not broad trace collapse.
- This checkpoint is the one to carry forward into RLVR.
