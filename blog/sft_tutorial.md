# SFT tutorial — reproducing `glyph-sft-v1` step by step

Companion to [`blog/sft_v1.md`](sft_v1.md). Every command needed to go from a clean machine to a model pushed to the Hub. Annotated so you know *why* each step exists.

Expected costs and times for the path that was actually used:

| stage | hardware | wall time | $ |
|---|---|---|---|
| data synthesis | local CPU + GPT-5-mini API | ~30 min | ~$3 |
| SFT training | 1× A100 80GB SXM4 (vast.ai) | ~1h32m | ~$2 |
| merge | local CPU | ~13 min | $0 |
| HF upload | local | ~20 min (1 Mbit/s) | $0 |
| eval (formal + test_loss + judge) | 1× 24GB+ for eval; CPU for judge | ~40 min | ~$1 + ~$0.02 (judge) |

Total ~$10 end-to-end. Skip data synthesis (pull from HF instead) to save $3 and 30 min.

---

## 0. Prereqs

- [vast.ai](https://vast.ai) account with credit (or your own A100/H100)
- [Hugging Face](https://huggingface.co) account; create a **write** token at `huggingface.co/settings/tokens`
- OpenAI account + API key (only if you re-synthesize data)
- Local `python ≥ 3.10` for merge + push

```bash
git clone https://github.com/JayZenith/glyph.git
cd glyph
```

---

## 1. (Optional) Resynthesize data

Skip this section if you're fine pulling the official 1098-trace dataset from HF (next step). The CLI flags that built the original dataset weren't checked in — re-running will give you a *similar* dataset, not byte-identical. For byte-identical, use [`JayZenith/glyph-sft-v1-data`](https://huggingface.co/datasets/JayZenith/glyph-sft-v1-data).

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...

# Full pipeline: synthesize → postprocess → patch → filter → diversity audit.
# Writes to synthetic_data/run_$(date +...)/sft_train.jsonl
bash data/build.sh my_run 1000
```

Inspect what you got:

```bash
python -m data.analyze_dataset --data synthetic_data/my_run/sft_train.jsonl
python -m data.audit_diversity --data synthetic_data/my_run/sft_train.jsonl
```

---

## 2. Provision a training instance

vast.ai search (pick an A100 80GB SXM4 with the deep-learning template + CUDA 12.x):

```bash
pip install --user vastai
export VAST_API_KEY=...

# find an offer
vastai search offers 'gpu_name=A100_SXM4 gpu_ram>=80 cuda_max_good>=12.1 num_gpus=1 inet_down>=200' \
    -o 'dph_total' | head -10

# rent one (replace <OFFER_ID>)
vastai create instance <OFFER_ID> \
    --image pytorch/pytorch:2.5.1-cuda12.4-cudnn9-devel \
    --disk 100 --ssh

vastai show instances
# note SSH host + port from the output
```

SSH in:

```bash
ssh -p <PORT> root@<HOST>
```

---

## 3. On the instance — install + pull data

```bash
git clone https://github.com/JayZenith/glyph.git && cd glyph
pip install -r requirements-train.txt   # transformers, peft, accelerate, datasets, etc.

# auth — paste a write-scope HF token
hf auth login

# pull the official 1098-trace dataset (skip if you synthesized your own and uploaded it)
hf download JayZenith/glyph-sft-v1-data \
    sft_train_1098_official.jsonl \
    --local-dir synthetic_data
```

---

## 4. Train

The headline run — produces `glyph-sft-v1`:

```bash
python -m sft.train \
    --model Qwen/Qwen3-4B-Base \
    --data synthetic_data/sft_train_1098_official.jsonl \
    --output runs/sft1
```

Defaults (in [`sft/config.py`](../sft/config.py)) match the actual run: LoRA r=64 α=64, batch 1, grad-accum 8, LR 2e-5, max-seq 8192, 3 epochs, bf16, `modules_to_save=["lm_head"]`, `masking_mode="assistant_only"`, separate `lm_head_lr=2e-5`.

Wall time on 1× A100 80GB SXM4: ~1h32m. Train loss hits ~0.65; val loss bottoms around 0.96.

To run any of the ablation variants:

```bash
# B — no lm_head training (expect termination collapse)
python -m sft.train --output runs/sft1_B \
    --modules-to-save none --masking-mode assistant_only

# C — full_trace masking
python -m sft.train --output runs/sft1_C \
    --modules-to-save lm_head --masking-mode full_trace

# D — neither
python -m sft.train --output runs/sft1_D \
    --modules-to-save none --masking-mode full_trace
```

Optional flags worth knowing:
- `--enable-gen-eval` — runs the 5-prompt validator-scored generation every eval step. Adds ~3 min per step. Useful for the first run.
- `--enable-merge` — merge LoRA into base in-process at end of training. Off by default (disk savings); merge on local CPU instead (step 6).
- `--resume` — pick up from latest checkpoint after an OOM.

---

## 5. Pull artifacts off the instance

The `runs/sft1/final/` dir contains the unmerged adapter (`adapter_model.safetensors`, 1.3 GB) and `runs/sft1/test_set/` is the tokenized held-out 110-trace split — both needed for eval and HF push.

```bash
# from your local machine
scp -P <PORT> -r root@<HOST>:/root/glyph/runs/sft1/{final,test_set} \
    sft_artifacts/official_glyph_sft_v1/

# destroy the GPU instance — stop the meter
vastai destroy instance <ID>
```

---

## 6. Merge locally (CPU, ~13 min)

LoRA + lm_head → one self-contained set of weights for inference:

```bash
python -m sft.merge_adapter \
    --base Qwen/Qwen3-4B-Base \
    --adapter sft_artifacts/official_glyph_sft_v1/final \
    --output sft_artifacts/official_glyph_sft_v1/merged
```

The merged dir is ~8 GB (full Qwen3-4B weights in bf16 split into 3 safetensors shards).

---

## 7. Push to HF

Two repos, two purposes. **Merged → for inference. Unmerged adapter → for RL init** (you need the LoRA layers and the saved `lm_head` as separately addressable trainable params).

The `env -u HF_TOKEN` prefix is needed if your shell has a read-only HF token in the environment — it lets the CLI fall back to the write token in `~/.cache/huggingface/token`:

```bash
# merged model (for `transformers.AutoModelForCausalLM.from_pretrained`)
env -u HF_TOKEN hf upload JayZenith/glyph-sft-v1 \
    sft_artifacts/official_glyph_sft_v1/merged --repo-type model

# unmerged adapter (for `peft.PeftModel.from_pretrained` on top of Qwen/Qwen3-4B-Base)
env -u HF_TOKEN hf upload JayZenith/glyph-sft-v1-adapter \
    sft_artifacts/official_glyph_sft_v1/final --repo-type model
```

The adapter file contains both the LoRA deltas (`...lora_A.weight`, `...lora_B.weight`) and the fully fine-tuned `lm_head.weight` — PEFT bundles anything in `modules_to_save` into the same `adapter_model.safetensors`. No separate lm_head file.

---

## 8. Eval

Three signals, complementary:

```bash
# (a) format quality — 32 prompts, validator-scored, real tool execution
python -m sft.eval_formal \
    --base-model Qwen/Qwen3-4B-Base \
    --sft-model JayZenith/glyph-sft-v1 \
    --output docs/ablation/eval_formal_A.json \
    --max-new-tokens 6000 \
    --max-tool-rounds 4
# add --include-base to re-score the base model (skipped by default — base output
# is fixed across ablations, so re-running it is wasted compute)

# (b) held-out test loss — 110 unseen traces, forward-only, fast on any 24GB+
python -m sft.eval_test_loss \
    --base Qwen/Qwen3-4B-Base \
    --sft JayZenith/glyph-sft-v1 \
    --test-set sft_artifacts/official_glyph_sft_v1/test_set \
    --output docs/ablation/eval_test_loss_A.json

# (c) LM judge — semantic quality of the existing generations (gpt-5-mini)
export OPENAI_API_KEY=sk-...
python -m sft.evals.llm_judge \
    docs/ablation/eval_formal_A.json \
    docs/ablation/eval_formal_A_judged.json
```

Expected headline numbers:

| | base | sft |
|---|---|---|
| mean held-out loss | 1.280 | **0.972** |
| perplexity | 3.60 | **2.64** |
| valid trace (5-prompt smoke) | 0/5 | **4/5** |
| ends with `<|im_end|>` | 0% | **100%** |
| judge mean (1–5) | n/a | **3.65** |
| judge factual | n/a | **3.2** (lowest dim — RL target) |

---

## 9. Common pitfalls

- **Termination collapse / infinite repetition.** Means `lm_head` wasn't trainable. Check `config.lora_modules_to_save == ["lm_head"]` and re-run.
- **`flash_attn` ImportError.** The trainer falls back to SDPA automatically with a warning — fine. If you want flash, `pip install flash-attn --no-build-isolation`.
- **OOM mid-training.** Usually a leftover eval process holding GPU memory. `nvidia-smi`, `kill -9 <PID>`, restart from `--resume`. The trainer's checkpoint cadence is every 500 steps.
- **`hf upload` 401 with what you swear is a write token.** Your `HF_TOKEN` env var is likely shadowing the stored token. Use `env -u HF_TOKEN hf upload ...` or set the env var to the write token. `python -c "from huggingface_hub import HfApi; print(HfApi().whoami()['auth']['accessToken']['role'])"` to verify scope.
- **LM judge returns empty responses.** GPT-5 family uses `max_completion_tokens` (not `max_tokens`) and consumes ~64 reasoning tokens before output. Default in [`sft/evals/llm_judge.py`](../sft/evals/llm_judge.py) is 2000.

---

## 10. What "done" looks like

You should end with:

- 2 HF repos (`glyph-sft-v1` merged, `glyph-sft-v1-adapter` unmerged)
- 1 HF dataset (`glyph-sft-v1-data`)
- `docs/ablation/eval_formal_A.json` and `eval_test_loss_A.json` committed to the repo
- `docs/ablation.md` table populated (rerun steps 4 + 8 for B/C/D if you want the full 2×2)

That's the SFT phase shipped. The RL phase ([`rl/`](../rl/)) initializes from `JayZenith/glyph-sft-v1-adapter` — covered in part 2.
