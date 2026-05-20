# GLYPH-SFT-V2

This project was the SFT foundation for RLVR.

The goal was not just to make a model answer Rust questions. The goal was to teach `Qwen/Qwen3-4B-Base` a rigid task-trace format with:
- `plan`
- `act`
- optional tool turns
- final `response`
- explicit references and todo satisfaction

The final output of this stage is `JayZenith/GLYPH-SFT-V2`, a reproduced supervised checkpoint that is strong enough to carry forward into RLVR.

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
- Published model: `JayZenith/GLYPH-SFT-V2`
- Published dataset: `JayZenith/GLYPH_SFT_DATASET`

Held-out loss:
- weighted loss: `2.2446 -> 0.3300`
- perplexity: `9.44 -> 1.39`

Held-out formal eval:
- clean rust-skewed 100-prompt suite
- `0` exact user-prompt overlaps with the 2500-trace training set
- final score: `97/100`

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

That comparison was not run on a plain chat prompt. It used the real eval-style constructed prefix produced by `build_prompt(...)` in [sft/evals/prompt_loader.py](/home/jay-zenith/Desktop/TASK/sft/evals/prompt_loader.py:18):

```text
<|im_start|>system
system「You are a Rust language assistant who gives compact conceptual explanations.」
<|im_end|>

<|im_start|>user
user「In Rust, what does a `'static` lifetime usually mean in practice? Keep it concise.」🏷 usr1
<|im_end|>

<|im_start|>assistant
```

That matters because the base model could already imitate parts of the surface syntax when forced into this context. The difference was rollout discipline. The base model kept free-running into invalid extra turns, while the SFT model stayed inside the GLYPH protocol and terminated cleanly.

More result artifacts live in:
- [glyph_sft_v2_results/eval_test_loss.json](/home/jay-zenith/Desktop/TASK/glyph_sft_v2_results/eval_test_loss.json:1)
- [glyph_sft_v2_results/eval_formal_100.json](/home/jay-zenith/Desktop/TASK/glyph_sft_v2_results/eval_formal_100.json:1)
- [glyph_sft_v2_results/trainer_state_checkpoint_250.json](/home/jay-zenith/Desktop/TASK/glyph_sft_v2_results/trainer_state_checkpoint_250.json:1)
- [glyph_sft_v2_results/events.out.tfevents.1779298883.4216cac405e6.1858.0](/home/jay-zenith/Desktop/TASK/glyph_sft_v2_results/events.out.tfevents.1779298883.4216cac405e6.1858.0:1)

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
- start from `JayZenith/GLYPH-SFT-V2`
- keep the same held-out benchmark discipline
- show which of the remaining failures disappear
- compare pre-RLVR vs post-RLVR on the same clean suite

That is the cleanest way to show real improvement from this exact checkpoint.

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
