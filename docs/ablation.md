# 2×2 Ablation: `modules_to_save` × loss masking

The original SFT used `modules_to_save=["lm_head"]` + assistant-only loss masking. Both fixes landed at once. This doc isolates which one mattered.

## Setup

All four configs share:
- Base: `Qwen/Qwen3-4B-Base`
- Data: `JayZenith/glyph-sft-v1-data` (1098 traces, same 80/10/10 split, seed=42)
- LoRA r=64, α=64, dropout 0.05, targets q,k,v,o,gate,up,down
- LR 2e-5 (trunk + lm_head when present)
- 3 epochs, batch 1, grad-accum 8, max-seq 8192
- Same A100 instance, sequential runs

Vary one of two flags per run:

| run | `--modules-to-save` | `--masking-mode` |
|---|---|---|
| A (current best) | `lm_head` | `assistant_only` |
| B | `none` | `assistant_only` |
| C | `lm_head` | `full_trace` |
| D | `none` | `full_trace` |

## Eval

Three signals collected per run:

1. **Validation loss** (in-loop) — Trainer evaluates on the val split every 25 steps (`load_best_model_at_end=True`, `metric=eval_loss`). Final value is the `eval_loss` at epoch 3 in the training log.
2. **Held-out test loss** (forward-only, post-hoc) — `python -m sft.eval_test_loss --test-set runs/abl_X/test_set --output runs/abl_X/test_loss.json`.
3. **Format quality** (greedy generation) — `python -m sft.eval_formal --sft-model runs/abl_X/merged --output runs/abl_X/eval.json --max-new-tokens 6000 --limit 5`.

**Splits are identical across A/B/C/D.** All four runs use the same seed=42 `train_test_split` on the same 1098 traces, so the train/val/test partition is the same. Comparisons are like-for-like.

## Commands

```bash
# A — current best (matches glyph-sft-v1)
python -m sft.train --output runs/abl_A_lmhead_asst \
    --modules-to-save lm_head --masking-mode assistant_only

# B — drop modules_to_save (does lm_head matter?)
python -m sft.train --output runs/abl_B_none_asst \
    --modules-to-save none --masking-mode assistant_only

# C — drop masking (does loss masking matter?)
python -m sft.train --output runs/abl_C_lmhead_full \
    --modules-to-save lm_head --masking-mode full_trace

# D — drop both (old-style baseline)
python -m sft.train --output runs/abl_D_none_full \
    --modules-to-save none --masking-mode full_trace
```

After each run, merge locally and eval:

```bash
python -m sft.merge_adapter --base Qwen/Qwen3-4B-Base \
    --adapter runs/abl_X/final --output runs/abl_X/merged

python -m sft.eval_formal --sft-model runs/abl_X/merged \
    --output runs/abl_X/eval.json --max-new-tokens 6000 --limit 5
```

## Results

_(fill in after each run completes)_

| run | val_loss (final) | test_loss | valid_traces | ends_with_response | no_repetition | has_plan | avg_score |
|---|---|---|---|---|---|---|---|
| A — lm_head + assistant_only | **0.958** | **0.972** | **4/5** | **100%** | **100%** | **100%** | **6.4** |
| B — none + assistant_only    | 0.971 | 0.986 | 0/5 | **0%** | 100% | 100% | 2.0 |
| C — lm_head + full_trace     | _ | _ | _/5 | _% | _% | _% | _ |
| D — none + full_trace        | _ | _ | _/5 | _% | _% | _% | _ |

**A vs B isolates `lm_head` in `modules_to_save`.** Loss/perplexity barely move (0.958 → 0.971), the model still writes plans and tool calls, but it never emits `<|im_end|>` (0% termination, every prompt truncates at 6000 tokens). Confirms the lm_head fix is what taught termination.

A is the live `JayZenith/glyph-sft-v1` re-evaluated with `--limit 5`. Reproduces the original eval exactly. val_loss from `artifacts/sft_run_v2/sft1.log` (epoch 3); test_loss from `artifacts/sft_run_v2/eval_test_loss.json`.

## Interpretation

Fill in once data is available. Read across rows for marginal effect of each flag:
- **A vs B** (rows differ only in modules_to_save): isolates lm_head's contribution.
- **A vs C** (rows differ only in masking): isolates masking's contribution.
- **A vs D**: combined effect.
- **B vs D** and **C vs D**: each fix alone vs neither.
