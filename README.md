# glyph

Reproduction notes for the successful `GLYPH_SFT_OFFICIAL_V1` supervised fine-tune.

## Outcome

- Base model: `Qwen/Qwen3-4B-Base`
- Dataset: `synthetic_data/gold_glyph_2500.jsonl`
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
- Dataset token stats with the Qwen tokenizer: median `345`, p95 `795`, p99 `830`, max `850`
- Why `1024` worked: it stayed safely above the longest trace, so the training dataset did not require truncation
- Formal eval generation cap: `max_new_tokens=1200`
- Formal eval tool-round cap: `max_tool_rounds=4`
- Why those eval caps worked: they were high enough for full traces but low enough to surface runaway behavior early; the final clean 100-prompt run had `not_truncated_rate=1.0`
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
  --data synthetic_data/gold_glyph_2500.jsonl \
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

CI-only eval:

```bash
python -m sft.eval_formal \
  --sft-model JayZenith/GLYPH_SFT \
  --prompt-file sft/evals/prompts_ci10.yaml \
  --output results/GLYPH_SFT_OFFICIAL_V1/eval_formal_ci10_fixed.json \
  --limit 10 \
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

## Remaining Failure Types

The remaining real failures were narrow and structural, not broad trace collapse.

1. Reference hygiene in planning traces.
Example:
```text
act {
    think ↦ [
        「Availability confirms the requested window is feasible.」 𝑝 avail1 ※ [ 1 ]
    ]
}
```
Problem:
- the model referenced todo ids like `1` and `2` instead of real tags like `avail1` or `plan1`

2. Malformed tail after a valid response.
Example:
```text
response「...」
}
※ [ avail1 • plan1 • note2 ]
⊨ 3
```
Problem:
- the answer content was mostly fine, but an extra `}` corrupted the final trace

3. Todo satisfaction / validator-edge formatting.
Example:
```text
⊨ 1 • 2 • 3
```
Problem:
- this should likely be accepted by the format, but currently exposes a strictness mismatch around todo satisfaction notation

## RLVR Focus

RLVR should be rust-focused, but not rust-only.

The reward mix should:
- keep rewarding global GLYPH structure on prompts the model already gets right
- overweight the remaining failure modes above
- penalize bad refs, unsatisfied todos, malformed tails, extra braces, and garbage after final response
- preserve correct tool-turn behavior and clean final stopping

The point of RLVR is not to teach the whole trace language from scratch. SFT already did that. RLVR should tighten the last narrow structural errors while preserving the strong existing prior.

## Notes

- `sft/evals/prompts_100.yaml` is the main held-out benchmark.
- The benchmark was run from the published HF model, not just a local training directory, to verify the released artifact directly.
- It was built to have `0` exact user-prompt overlaps with `gold_glyph_2500.jsonl`.
- The remaining misses were narrow planning/reference issues, not broad trace collapse.
- This checkpoint is the one to carry forward into RLVR.
