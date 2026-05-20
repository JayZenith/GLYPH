# GLYPH_SFT_OFFICIAL_V1

This project was the SFT foundation for RLVR.

The goal was not just to make a model answer Rust questions. The goal was to teach `Qwen/Qwen3-4B-Base` a rigid task-trace format with:
- `plan`
- `act`
- optional tool turns
- final `response`
- explicit references and todo satisfaction

The final output of this stage is `JayZenith/GLYPH_SFT`, a supervised checkpoint that is strong enough to carry forward into RLVR.

## Why This Work Matters

This was an end-to-end post-training project:
- build the trace format
- build and expand the dataset
- tune the SFT recipe
- run held-out loss evals
- build a stricter formal eval
- catch benchmark contamination
- fix the eval harness
- decide whether the checkpoint is good enough for RLVR

That is the real unit of work. The interesting part is not “I fine-tuned a model.” The interesting part is getting to a checkpoint that survives harder evaluation and is worth using as the RL starting point.

## Final Outcome

- Base model: `Qwen/Qwen3-4B-Base`
- Training dataset: `synthetic_data/gold_glyph_2500.jsonl`
- Split: `2000 / 250 / 250`
- Final checkpoint: `runs/sft_toolturn_v1_fullft1/checkpoint-250`
- Published model: `JayZenith/GLYPH_SFT`
- Published dataset: `JayZenith/GLYPH_SFT_DATASET`

Held-out loss:
- weighted loss: `2.2446 -> 0.3284`
- perplexity: `9.44 -> 1.39`

Held-out formal eval:
- clean rust-skewed 100-prompt suite
- `0` exact user-prompt overlaps with the 2500-trace training set
- raw score: `86/100`
- CI-only eval: `10/10`
- main interpretation: `96/100`

That is the checkpoint being taken into RLVR.

## Pipeline

```text
Define GLYPH trace language
        ↓
Build gold seed traces
        ↓
Expand to 2500-trace supervised dataset
        ↓
Train Qwen3-4B-Base with full FT SFT
        ↓
Run held-out loss eval
        ↓
Run strict formal trace eval
        ↓
Fix eval contamination and harness issues
        ↓
Freeze SFT checkpoint
        ↓
Move to RLVR
```

## Training Recipe

The successful run was a light full fine-tune, not a LoRA run.

Important knobs:
- full fine-tune: `--no-use-lora`
- epochs: `1`
- trunk LR: `1e-5`
- `lm_head` LR: `1.5e-5`
- masking: `assistant_only`
- max seq length: `1024`
- batch size: `1`
- grad accumulation: `8`
- save steps: `100`
- bf16: on
- gradient checkpointing: on

Exact command:

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

## What Failed vs What Worked

| Stage | Outcome |
|---|---|
| Small SFT runs on narrow data | Good held-out loss, poor free-generation control |
| LoRA runs | Better content fit, still unstable protocol behavior |
| EOS experiment | Did not fix the real problem |
| Early formal evals | Looked better than they should have because of contamination |
| Initial 100-prompt formal eval | Exposed remaining narrow failures and eval issues |
| Light full fine-tune, 1 epoch | Produced the checkpoint that is good enough for RLVR |

The main lesson was that a flattering eval is not the same thing as a trustworthy eval.

## Sample Trace

One short valid example from the clean held-out eval:

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

More result artifacts live in:
- [results/GLYPH_SFT_OFFICIAL_V1/eval_test_loss.json](/home/jay-zenith/Desktop/TASK/results/GLYPH_SFT_OFFICIAL_V1/eval_test_loss.json:1)
- [results/GLYPH_SFT_OFFICIAL_V1/eval_formal_100.json](/home/jay-zenith/Desktop/TASK/results/GLYPH_SFT_OFFICIAL_V1/eval_formal_100.json:1)
- [results/GLYPH_SFT_OFFICIAL_V1/eval_formal_ci10_fixed.json](/home/jay-zenith/Desktop/TASK/results/GLYPH_SFT_OFFICIAL_V1/eval_formal_ci10_fixed.json:1)

## What Makes This Stronger Than “I Fine-Tuned a Model”

This is stronger than a generic SFT story because the hard parts were not hidden:
- dataset design mattered
- optimizer choices mattered
- eval contamination had to be caught
- harness bugs had to be distinguished from model bugs
- the decision to stop SFT and move to RLVR had to be justified

That makes the project legible as real LLM engineering work.

## Why RLVR Comes Next

SFT got the model most of the way there, but the remaining misses are narrow and structural:
- reference hygiene
- perfect termination discipline
- planning-trace cleanup

That is exactly where RLVR should help.

So the right framing is:
- SFT created a strong prior
- the prior survived hard held-out checks
- RLVR now starts from a checkpoint that already knows the trace language

This is the point of the project. The SFT stage is not the finish line. It is the launch point for RLVR.

## Follow-Up

The follow-up post should be the RLVR continuation:
- start from `JayZenith/GLYPH_SFT`
- keep the same held-out benchmark discipline
- show which of the remaining failures disappear
- compare pre-RLVR vs post-RLVR on the same clean suite

That is the cleanest way to show real improvement from this exact checkpoint.
