# glyph

Teach an LLM a structured trace format with explicit `plan` / `act` / `response` phases, todos, and Unicode operators (`🏷` tag, `※` ref, `⊨` satisfies, `𝑝` confidence). See [`docs/def.md`](docs/def.md).

**Status:** SFT shipped (Qwen3-4B-Base + LoRA). RL is next.

**HF artifacts (private):**
- Model: [`JayZenith/glyph-sft-v1`](https://huggingface.co/JayZenith/glyph-sft-v1)
- Dataset: [`JayZenith/glyph-sft-v1-data`](https://huggingface.co/datasets/JayZenith/glyph-sft-v1-data) (final + raw stages + manifest)

## Results

Held-out test loss (110 traces unseen in training):

| | base | sft |
|---|---|---|
| mean loss | 1.280 | **0.972** |
| perplexity | 3.60 | **2.64** |
| sft beats base | | **110/110** |

5-prompt generation eval, validator-scored:

| | base | sft |
|---|---|---|
| valid trace | 0/5 | **4/5** |
| ends with response | 0% | **100%** |
| has plan | 0% | **100%** |
| no repetition | 60% | **100%** |
| not truncated | 20% | **100%** |
| used tools when given | 0/4 | **4/4** |

## Why it works

Three changes coupled:
1. `lm_head` in `modules_to_save` — Qwen3-Base never saw `<|im_end|>`; LoRA-only can't shift its logit
2. Assistant-only loss masking
3. lm_head LR 2e-5 (from 5e-6 — the only cleanly isolated ablation)

## Layout

```
core/      validator (single rule book)
data/      synthesis pipeline + prompts.yaml + build.sh
sft/       train + eval + merge + evals/
rl/        prime-rl stage (WIP)
tools/     CLI utilities
```

## Reproduce `glyph-sft-v1`

1× A100 80GB SXM4, ~1h32m.

```bash
# on instance
git clone https://github.com/JayZenith/glyph.git && cd glyph
pip install -r requirements-train.txt
hf login
hf download JayZenith/glyph-sft-v1-data sft_train_1098_official.jsonl --local-dir synthetic_data

python -m sft.train \
    --model Qwen/Qwen3-4B-Base \
    --data synthetic_data/sft_train_1098_official.jsonl \
    --output runs/sft1
```

Defaults match the actual run: LoRA r64/α64, batch 1, grad-accum 8, LR 2e-5, max-seq 8192, 3 epochs. Merge and gen-eval are off by default; opt in with `--enable-merge` / `--enable-gen-eval`.

For RL, install PRIME-RL separately with:

```bash
bash rl/setup_prime_rl.sh
```

`requirements-train.txt` is intentionally only for glyph-local SFT / audit dependencies now; PRIME-RL uses its own upstream `uv` / Python 3.12 environment. The setup script also installs a pinned `flash-attn` wheel so it does not fall back to a long source build. If the PRIME-RL torch/CUDA stack changes, override with `FLASH_ATTN_WHEEL_URL=... bash rl/setup_prime_rl.sh`.

```bash
# pull adapter + tokenized test_set, destroy instance
scp -P <PORT> -r root@<HOST>:/root/glyph/runs/sft1/{final,test_set} sft_artifacts/official_glyph_sft_v1/
vastai destroy instance <ID>

# merge locally (CPU, ~13min)
python -m sft.merge_adapter \
    --base Qwen/Qwen3-4B-Base \
    --adapter sft_artifacts/official_glyph_sft_v1/final \
    --output sft_artifacts/official_glyph_sft_v1/merged

# push to HF (env -u HF_TOKEN works around read-only token in env)
env -u HF_TOKEN hf upload JayZenith/glyph-sft-v1 \
    sft_artifacts/official_glyph_sft_v1/merged --repo-type model
```

## Eval

```bash
# format quality (32 prompts in sft/evals/prompts.yaml, validator-scored)
# defaults: --base-model Qwen/Qwen3-4B-Base, --sft-model JayZenith/glyph-sft-v1, --max-tool-rounds 4
python -m sft.eval_formal --output eval_formal_32.json --max-new-tokens 6000

# held-out test loss (forward-only) — fast on any 24GB+
python -m sft.eval_test_loss \
    --base Qwen/Qwen3-4B-Base \
    --sft JayZenith/glyph-sft-v1 \
    --test-set sft_artifacts/official_glyph_sft_v1/test_set \
    --output eval_test_loss.json
```

## Caveats

- Dataset CLI flags weren't recorded — re-running `data/build.sh` gives a similar dataset, not byte-identical. For exact reproduction use [`JayZenith/glyph-sft-v1-data`](https://huggingface.co/datasets/JayZenith/glyph-sft-v1-data) directly.
- Only one ablation isolated (lm_head LR). The 2×2 over `modules_to_save` × loss-masking is run via `python -m sft.train --modules-to-save ... --masking-mode ...`; protocol + results table in [`docs/ablation.md`](docs/ablation.md).
- Eval is small (5 prompts × 1 seed). Plan: 30+ prompts × 3 seeds + LM-judge semantic eval.
