# glyph

A message format and training pipeline for teaching LLMs structured, long-horizon task execution.

Models emit traces with explicit `plan` / `act` / `response` phases, an internal `todo` list, and Unicode operators for tagging (`🏷`), referencing (`※`), confidence (`𝑝`), and todo satisfaction (`⊨`).

## Format

See [`def.md`](def.md) for the full spec. Example:

```js
plan {
    todo ↦ {
        1 ↦ "Fetch the weather." •
        2 ↦ "Recommend clothing." ※ usr1
    }
}

act {
    call ↦ { tool ↦ get_weather • zip_code ↦ "94103" • id ↦ "w1" } ⊨ 1
}

response「68°F and overcast — light sweater works.」※ "w1" ⊨ 2
```

## Pipeline

- `generate.py` / `generate_prompts.py` — synthesize traces
- `postprocess.py`, `validator.py`, `schema.py` — clean/validate
- `train.py` — SFT (LoRA on Qwen3-4B)
- `rl_train.py` — RL stage
- `eval_rewards.py`, `scripts/eval_sft_formal.py` — eval

## Data

Traces live in `synthetic_data/` (gitignored); model artifacts in `artifacts/` (gitignored).
