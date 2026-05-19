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

Four signals collected per run:

1. **Validation loss** (in-loop) — Trainer evaluates on the val split every 25 steps (`load_best_model_at_end=True`, `metric=eval_loss`). Final value is the `eval_loss` at epoch 3 in the training log.
2. **Held-out test loss** (forward-only, post-hoc) — `python -m sft.eval_test_loss --test-set runs/abl_X/test_set --output runs/abl_X/test_loss.json`.
3. **Format quality** (greedy generation, validator-scored) — `python -m sft.eval_formal --sft-model runs/abl_X/merged --output runs/abl_X/eval.json --max-new-tokens 6000 --limit 5`. Measures **usability** (does the trace terminate, parse, satisfy todos).
4. **Content quality** (LLM-as-judge over the same 5 generations) — `python -m sft.evals.llm_judge runs/abl_X/eval.json runs/abl_X/eval_judged.json`. The judge is **OpenAI `gpt-5-mini`** called via the OpenAI API ([`sft/evals/llm_judge.py`](../sft/evals/llm_judge.py)); the script reads the formal-eval JSON, sends each generation to the judge with a fixed rubric prompt, and writes per-prompt + aggregate scores back to a `*_judged.json` file. Scores four dimensions on 1–5 (plan_quality, response_relevance, factual_correctness, helpfulness) and reports `judge_mean` (avg of the 4). Measures **what was written**, ignores whether the trace terminates. No human review and no Claude in the loop — `gpt-5-mini` is the sole judge for every number in the table below.

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

| run | val_loss | test_loss | valid_traces | ends_with_response | no_repetition | avg_score | judge_mean | judge_factual |
|---|---|---|---|---|---|---|---|---|
| A — lm_head + assistant_only | **0.958** | **0.972** | **4/5** | **100%** | **100%** | **6.4** | 3.65 | 3.2 |
| B — none + assistant_only    | 0.971 | 0.986 | 0/5 | **0%** | 100% | 2.0 | **3.80** | 3.4 |
| C — lm_head + full_trace     | 0.937† | 0.936† | 3/5 | **100%** | 100% | 5.8 | 3.55 | 2.8 |
| D — none + full_trace        | 0.961† | 0.959† | 0/5 | 60% | **40%** | 2.6 | 3.55 | 3.0 |

### A vs B — isolates `lm_head` in `modules_to_save`
Loss/perplexity barely move (0.958 → 0.971). The model still writes plans and tool calls — judge_mean is even *higher* for B (3.80 vs 3.65) — but it never emits `<|im_end|>` (0% termination, every prompt truncates at 6000 tokens). Confirms `lm_head` is what taught termination, not what taught the format.

### A vs C — isolates assistant-only masking
With `lm_head` trained, `full_trace` masking still terminates (100%). Validator quality drops slightly (3/5 vs 4/5, 5.8 vs 6.4 score). Judge slightly favors A on factual (3.2 vs 2.8). Masking is a real but marginal refinement.

### D (no lm_head + full_trace) — different failure mode than B
D terminates 60% (gradient on every `<|im_end|>` in the trace partially fixes termination) but introduces a new failure: **repetition jumps up (no_rep drops 100% → 40%)**. `lm_head` was also suppressing repetition.

### Validator vs LM judge — they measure different things
B's judge_mean (3.80) is the highest of all four runs even though B is **structurally unusable** (0% termination). The judge reads the trace text and scores **content quality**; it doesn't penalize the model for failing to emit `<|im_end|>`. The validator catches that. **Both signals are needed:** judge says "B writes well", validator says "B can't be used". Same conclusion: lm_head is load-bearing.

### Common signal across runs — hallucination
`judge_factual` is the lowest dim in every run (2.8–3.4). The judge consistently caught hallucinated specifics (made-up benchmark numbers, weather data presented as real). This is a real finding for RL: the SFT'd model writes fluent traces but invents facts. Reward shaping in RL should penalize hallucination explicitly.

### Summary
**`lm_head` training is the load-bearing fix.** Without it (B, D), the model breaks structurally even when its content is fine. With it (A, C), the model works. Assistant-only masking is a small refinement on top.

† C and D val/test loss are computed over **all tokens** (full_trace mode), not just assistant tokens. They are not directly comparable with A and B's numbers (which average over assistant tokens only). The clean apples-to-apples signals are the formal-eval columns and the judge columns.

A is the live `JayZenith/glyph-sft-v1` re-evaluated with `--limit 5`. Reproduces the original eval exactly. val_loss from `sft_artifacts/official_glyph_sft_v1/logs/sft1.log` (epoch 3); test_loss from `sft_artifacts/official_glyph_sft_v1/eval_results/eval_test_loss.json`. Judged JSONs (per-prompt judge breakdowns) live in `docs/ablation/abl_*_eval_formal_judged.json`.

