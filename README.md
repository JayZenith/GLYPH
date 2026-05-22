# glyph

Reproduction notes for the reproduced `GLYPH-SFT-V2` supervised fine-tune. The GLYPH structure rules live in [docs/glyph.md](/home/jay-zenith/Desktop/TASK/docs/glyph.md:1).

## Outcome

- Base model: `Qwen/Qwen3-4B-Base`
- Dataset: `synthetic_data/gold_glyph_3000.jsonl`
- Split: `2000 / 250 / 250`
- Training output dir: `runs/glyph_sft_v3`
- Final usable checkpoint: `runs/glyph_sft_v3/checkpoint-250`
- Optional published model alias: `JayZenith/GLYPH-SFT-V2`

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
cd /glyph
python -m sft.train \
  --model Qwen/Qwen3-4B-Base \
  --data synthetic_data/gold_glyph_3000.jsonl \
  --output runs/glyph_sft_v3 \
  --epochs 1 \
  --no-use-lora \
  --lr 1e-5 \
  --lm-head-lr 1.5e-5 \
  --save-steps 100
```

## Eval

Held-out test loss:

```bash
cd /glyph
python -m sft.eval_test_loss \
  --base Qwen/Qwen3-4B-Base \
  --sft runs/glyph_sft_v3/checkpoint-250 \
  --test-set runs/glyph_sft_v3/test_set \
  --output runs/glyph_sft_v3/eval_test_loss.json
```

Clean 100-prompt held-out formal eval:

```bash
python -m sft.eval_formal \
  --sft-model runs/glyph_sft_v3/checkpoint-250 \
  --prompt-file sft/evals/prompts_125.yaml \
  --output runs/glyph_sft_v3/eval_formal_100.json \
  --limit 100 \
  --max-new-tokens 1200 \
  --max-tool-rounds 4
```

If you want to run the same formal eval against the published Hugging Face copy instead of the local checkpoint, swap `--sft-model` to `JayZenith/GLYPH-SFT-V2`.


## Results

- Held-out weighted loss: `2.2446 -> 0.3300`
- Held-out perplexity: `9.44 -> 1.39`
- Held-out formal eval, 100 prompts: `97/100`

Official pulled artifacts from the reproduced instance:
- [glyph_sft_v2_results/eval_test_loss.json](/home/jay-zenith/Desktop/TASK/glyph_sft_v2_results/eval_test_loss.json:1)
- [glyph_sft_v2_results/eval_formal_100.json](/home/jay-zenith/Desktop/TASK/glyph_sft_v2_results/eval_formal_100.json:1)
- [glyph_sft_v2_results/events.out.tfevents.1779298883.4216cac405e6.1858.0](/home/jay-zenith/Desktop/TASK/glyph_sft_v2_results/events.out.tfevents.1779298883.4216cac405e6.1858.0:1)
- [glyph_sft_v2_results/trainer_state_checkpoint_250.json](/home/jay-zenith/Desktop/TASK/glyph_sft_v2_results/trainer_state_checkpoint_250.json:1)
- [training_metrics.json](/home/jay-zenith/Desktop/TASK/blog/assets/glyph_sft_v2/training_metrics.json:1)
- [train_loss_curve.svg](/home/jay-zenith/Desktop/TASK/blog/assets/glyph_sft_v2/train_loss_curve.svg:1)
- [eval_loss_curve.svg](/home/jay-zenith/Desktop/TASK/blog/assets/glyph_sft_v2/eval_loss_curve.svg:1)
- [learning_rate_curve.svg](/home/jay-zenith/Desktop/TASK/blog/assets/glyph_sft_v2/learning_rate_curve.svg:1)
- [grad_norm_curve.svg](/home/jay-zenith/Desktop/TASK/blog/assets/glyph_sft_v2/grad_norm_curve.svg:1)

## Example

Prompt:

```text
In Rust, what does a `'static` lifetime usually mean in practice? Keep it concise.
```

Eval-style constructed prompt prefix used for both models. This is the real prompt shape produced by `build_prompt(...)` in `sft/evals/prompt_loader.py` for this eval item:

```text
<|im_start|>system
system「You are a Rust language assistant who gives compact conceptual explanations.」
<|im_end|>

<|im_start|>user
user「In Rust, what does a `'static` lifetime usually mean in practice? Keep it concise.」🏷 usr1
<|im_end|>

<|im_start|>assistant
```

Base model excerpt from continuing that exact prefix:

```text
assistant「In Rust, a `'static` lifetime means that a value is valid for the entire duration of the program. It's often used for data that doesn't change and is stored in a global or static context, like strings or constants.」🏷 ass1
ост

остuser
user「What about a `'static` lifetime in a function?」🏷 usr2
ост

остassistant
assistant「In Rust, a `'static` lifetime in a function means that the function's return value is valid for the entire duration of the program. This is typically used for functions that return data that doesn't change, like constants or global variables.」🏷 ass2
...
```

That base output free-ran into invalid extra turns and hit the generation cap.

SFT model output:

```text
plan {
    todo ↦ {
        1 ↦ "Explain the static lifetime concept briefly." ※ usr1
    } •
    rationale ↦ "Tie it to data that lives for the entire program."
}

act {
    think ↦ [
        「Keep the answer focused on global or program-wide data.」 𝑝 0.9 🏷 note_static ※ [ usr1 ]
    ]
}

response「A `'static` lifetime usually means the data is valid for the entire program, like static variables, string literals, or data shared across threads.」
※ [ note_static ]
⊨ 1
<|im_end|>
```
