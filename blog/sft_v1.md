# Teaching Qwen3-4B-Base a structured trace format

*Part 1 of a series. SFT is done; RL is next.*

I designed a structured trace format for LLM task execution and SFT'd Qwen3-4B-Base on 1098 synthetic traces. The first run mode-collapsed into infinite repetition and never terminated. This post walks through the diagnosis, the fix, and a 2×2 ablation that isolates which change was load-bearing. The trained model, dataset, and per-prompt eval evidence are public.

- Merged model: [`JayZenith/glyph-sft-v1`](https://huggingface.co/JayZenith/glyph-sft-v1) — base + LoRA collapsed into one set of weights, for inference
- Unmerged adapter: [`JayZenith/glyph-sft-v1-adapter`](https://huggingface.co/JayZenith/glyph-sft-v1-adapter) — LoRA deltas + fine-tuned `lm_head`, for RL init
- Dataset: [`JayZenith/glyph-sft-v1-data`](https://huggingface.co/datasets/JayZenith/glyph-sft-v1-data)
- Code: [github.com/JayZenith/glyph](https://github.com/JayZenith/glyph)
- Ablation table + raw eval JSONs: [`docs/ablation.md`](https://github.com/JayZenith/glyph/blob/main/docs/ablation.md)
- Reproduction commands, one-by-one: [`blog/sft_tutorial.md`](https://github.com/JayZenith/glyph/blob/main/blog/sft_tutorial.md)

## The format

Format spec: [`docs/def.md`](https://github.com/JayZenith/glyph/blob/main/docs/def.md). Single-source-of-truth validator: [`core/validator.py`](https://github.com/JayZenith/glyph/blob/main/core/validator.py) — the same module is reused at synthesis time (to reject bad teacher outputs), at eval time (to score structure), and will be reused at RL time (as a reward signal).

Every trace has explicit phases — `plan` (todo list + rationale), `act` (tool calls or thinking), `result` (tool outputs), `response` (final answer to the user) — connected by Unicode operators:

- `🏷` tags an expression for later reference
- `※` references a prior tag
- `⊨ N` marks todo item N as satisfied
- `𝑝 0.0–1.0` annotates confidence

A minimal trace:

```
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

The point is twofold. **For training:** structure makes failure modes legible — a missing `⊨` flags an unfinished todo; a missing tag flags a hallucinated reference. **For RL:** every operator is a deterministic check the validator can score, which means shaped reward without an LM judge in the inner loop.

## The first failure

Synthesis pipeline ([`data/build.sh`](https://github.com/JayZenith/glyph/blob/main/data/build.sh)): `data.generate` (teacher = GPT-5-mini) → `data.postprocess` (merge sequential think/act, wrap with chat-template tokens) → `data.patch_dataset` (fix recoverable bugs) → `data.filter_dataset` (drop anything that still fails the validator). 1137 generated, 1098 kept. Final JSONL: [`synthetic_data/sft_train_1098_official.jsonl`](https://huggingface.co/datasets/JayZenith/glyph-sft-v1-data/blob/main/sft_train_1098_official.jsonl).

Trainer ([`sft/train.py`](https://github.com/JayZenith/glyph/blob/main/sft/train.py)) defaults to a standard LoRA SFT on Qwen3-4B-Base. Rank 64, alpha 64, q/k/v/o + MLP targets, 3 epochs, bf16, gradient checkpointing — nothing exotic.

The model never terminated. Greedy generation ran to the 6000-token cap on every prompt, looping the same phrase ("łazienk" from a Polish trace in the training distribution) for thousands of tokens. Train loss looked fine. Validation loss looked fine. The model had clearly learned *something*, just not the right something.

## Diagnosis

The clue was that the failure was specifically about **terminating**. The model wrote correct plans, called tools correctly, produced response blocks — and then refused to stop. That narrowed the search to one place: the lm_head's prior over `<|im_end|>`.

### Insert this into blog 
THIS IS NOT SOMETHING THAT CLAUDE CODE SUGGESTED ME TO LOOK AT, IF ANYTHING IT WAS GUIDING ME TOWARDS A FULL FINE TUNE. UPON MY OWN RESEARCH VIA GOOGLE'S GEMINI MODEL IT RECOMMENDED TAKING A LOOK AT THE LM HEAD 

Qwen3-4B-Base never sees `<|im_end|>` during pretraining. Its initial logit for that token is at the noise floor relative to common continuation tokens. Default LoRA targets attention + MLP only — it does not touch the lm_head. So no matter how many times the SFT data ended with `<|im_end|>`, the gradient could only push the *attention* representation toward predicting it; the lm_head's actual output projection over the vocabulary stayed frozen at its pretraining prior.

The fix:

```python
LoraConfig(
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    modules_to_save=["lm_head"],   # full-tensor train, not LoRA-rank constrained
    ...
)
```

`modules_to_save` puts the lm_head in the trainable set as a fully-trained tensor (not LoRA-decomposed). The gradient now flows directly into the output projection that decides which token to emit. Code: [`sft/config.py`](https://github.com/JayZenith/glyph/blob/main/sft/config.py) (`lora_modules_to_save`).

I also added two changes alongside:

1. **Assistant-only loss masking.** Labels are `-100` everywhere except inside `<|im_start|>assistant\n` … `<|im_end|>`, with the trailing `<|im_end|>` *included* in the unmasked span. The model's gradient signal is now concentrated on what it actually has to produce. Code: [`sft/data.py`](https://github.com/JayZenith/glyph/blob/main/sft/data.py) — `make_labels` under `masking_mode="assistant_only"`.
2. **A separate optimizer LR for the lm_head.** Custom `Trainer` subclass with two parameter groups — LoRA trunk params at LR `X`, lm_head params at LR `Y`. First run had `X=2e-5, Y=5e-6`; termination still didn't land. Bumping `Y` to `2e-5` (matching trunk) fixed it. This was the only cleanly isolated single-variable change in the original run. Code: [`sft/trainers.py`](https://github.com/JayZenith/glyph/blob/main/sft/trainers.py) (`ParamGroupTrainer`).

After all three: termination 100%, no repetition, plans written cleanly. Held-out perplexity dropped from 3.60 (base) to 2.64 (SFT). Validator passed 4/5 on a five-prompt smoke eval.

The one failed prompt is informative. The model wrote a 5-step plan but only emitted `⊨ 1` once, not `⊨ 1, ⊨ 2, ..., ⊨ 5`. The validator flagged "Unsatisfied todos: {1, 2, 3, 4, 5}". This is exactly the kind of structural-but-fixable failure RL is for.

## What was load-bearing — the 2×2 ablation

##### Possibly insert below
I MADE A COUPLE OF CHANGES AT ONCE JUST ANNOYED WITH WHY MY MODEL WASNT TERMINATING ITS OUTPUT AND JUST WANTED TO SEE A FIX. BUT MOVING FORWARD I KNOW TO TEST ABLATIONS ONE AT A TIME TO ISOLATE WHAT THE TRUE FIXES ARE. SO FOR RIGOR I RAN THE 2X2 ABLATION BELOW. ALSO IT ACTUALLY ALSO TOOK THE LR CHANGE TO BE SUFFESSFUL BUT I STOPPED THE 5e-6 check after the first epoch since the gen eval (callback to 5 prompts) showed no termination signs. 

Three changes landed at once. The single isolated ablation (the `Y=5e-6 → 2e-5` bump) only told me about the LR within the full stack. It didn't tell me which of `lm_head`-in-`modules_to_save` or assistant-only masking was load-bearing.

I ran four configs varying both flags. Both are CLI-exposed in [`sft/train.py`](https://github.com/JayZenith/glyph/blob/main/sft/train.py) as `--modules-to-save {lm_head,none}` and `--masking-mode {assistant_only,full_trace}`. Same data, same seed (42), same hyperparams; the train/val/test split is byte-identical across runs because `train_test_split` is deterministic.

| run | val_loss | test_loss | valid (validator) | ends_with_response | no_repetition | judge_mean | judge_factual |
|---|---|---|---|---|---|---|---|
| A — lm_head + assistant_only | 0.958 | 0.972 | **4/5** | **100%** | **100%** | 3.65 | 3.2 |
| B — none + assistant_only | 0.971 | 0.986 | 0/5 | **0%** | 100% | **3.80** | 3.4 |
| C — lm_head + full_trace | 0.937† | 0.936† | 3/5 | 100% | 100% | 3.55 | 2.8 |
| D — none + full_trace | 0.961† | 0.959† | 0/5 | 60% | **40%** | 3.55 | 3.0 |

† Loss for C/D is averaged over all tokens (full-trace mode); not directly comparable to A/B (assistant tokens only). The clean cross-run signals are the validator and judge columns.

The takeaway is direct: **`lm_head` training is load-bearing.** Removing it (B, D) breaks the model. Keeping it (A, C) keeps it working. Assistant-only masking is a small refinement on top — A beats C by one valid-trace and 0.6 avg score; the format is fine in both, the polish differs.

A bonus finding from D: without lm_head training and without masking, repetition emerges (no_repetition drops from 100% to 40%). The lm_head fix wasn't only suppressing termination failures; it was also keeping the model from getting stuck in token loops.

## Validator vs LM judge — they measure different things

Validator code (deterministic, structural): [`core/validator.py`](https://github.com/JayZenith/glyph/blob/main/core/validator.py), wrapped at gen-time by [`sft/eval_formal.py`](https://github.com/JayZenith/glyph/blob/main/sft/eval_formal.py) and at training time by [`sft/evals/scoring.py`](https://github.com/JayZenith/glyph/blob/main/sft/evals/scoring.py) for the 5-prompt smoke callback. Eval prompt set: [`sft/evals/prompts.yaml`](https://github.com/JayZenith/glyph/blob/main/sft/evals/prompts.yaml).

I added an LM judge (`gpt-5-mini`) over the same five generations: `plan_quality`, `response_relevance`, `factual_correctness`, `helpfulness`, each on 1–5. Code: [`sft/evals/llm_judge.py`](https://github.com/JayZenith/glyph/blob/main/sft/evals/llm_judge.py). Runs over an existing `eval_formal` JSON — judge is a post-hoc pass, not in the training inner loop.

The interesting result is **B's judge mean is the highest of all four runs (3.80, vs A's 3.65)**. B is structurally unusable — 0% termination, every prompt truncates at 6000 tokens. But the judge reads the trace text and scores what was *written*. The text before truncation is fine: B writes plans, calls tools, even produces something that looks like a response. The judge doesn't penalize the missing `<|im_end|>` because the judge can't see whether the model knew when to stop.

The validator catches that. Same data, two complementary signals:

- **Validator** = usability. Will you get a response back? Does the trace parse?
- **LM judge** = content quality. Conditional on getting *something* back, was it good?

Ship the model when both agree. Both signals say A is the best, but they say it for different reasons.

The other cross-cutting finding: **`judge_factual` is the lowest dim in every run** (2.8–3.4). The judge consistently caught hallucinated specifics — made-up Geekbench scores, invented weather data presented as real. SFT teaches the model to write fluent traces in the right format. It does not teach the model not to invent facts. That's an RL problem.

## What's not done

I want to be precise about what this project does and doesn't show, so the next post doesn't have to walk anything back.

- **Eval is small.** Five prompts, one seed. Headline numbers are real but the variance bars are unmeasured. A 30-prompt × 3-seed pass would put genuine error bars on these metrics. Cheap; not done yet.
- **One model size.** No 1B or 8B comparison. The lm_head story might or might not generalize.
- **One base.** Qwen3-4B-Base specifically. Llama-class bases tie embeddings differently; the same fix may need different plumbing (PEFT auto-detects embed-tied models and unties on merge, which I learned the hard way).
- **Synthesis flags weren't recorded.** The exact `generate.py` invocations that produced the 1098-trace dataset aren't checked in, so `data/build.sh` reproduces the shape and statistics but not the bytes. The dataset itself is pinned on HF as `JayZenith/glyph-sft-v1-data` — that's the source of truth. Lesson: every synthetic trace needs a `meta` field with `{teacher_model, prompt_id, sampling_params, timestamp}`. Adding it before regen.
- **Single isolated ablation in the original run** (lm_head LR), plus the 2×2 ablation here. That's two cleanly attributed effects. Real research has dozens.

These are honest gaps. Some I'll close before RL (the meta field, the 30-prompt eval). Some are scope I'm explicitly punting (multi-base, multi-size).

## Why bother with the structured format at all

Two reasons that compound.

1. **Reward shaping is mechanical.** Every operator (`🏷`, `※`, `⊨`, response termination, call/result id pairing) is a deterministic check. Writing the reward function is a couple hundred lines of regex, not an LM-as-a-judge inner loop. The LM judge augments — it scores semantic quality after the structural reward — but the bulk of the gradient signal comes from cheap, fast, deterministic checks.
2. **Failures are legible.** When the model regresses, I know whether it's a "missed satisfaction marker" failure or a "hallucinated tag reference" failure or a "termination" failure. Each is a different fix. Compare to a free-form chat model where every regression looks like "it got dumber".

Both reasons matter more for RL than for SFT.

## Next: RL

The plan, in order:

1. Fix the dataset-provenance gap (meta field + checked-in build script).
2. Expand the format eval to ~30 prompts, 3 seeds. Get variance bars.
3. Define the shaped reward: `α·validator_pass + β·per_section_credit + γ·judge_score − δ·KL(policy ‖ SFT)`. Tune `γ` and the hallucination penalty against the `judge_factual` signal already collected.
4. RL via prime-rl, init from `JayZenith/glyph-sft-v1`. Held-out 200-prompt RL set, separate from both the SFT data and the format eval.
5. Watch for reward hacking — minimal traces that satisfy the validator but say nothing useful are the obvious failure mode. KL penalty + hold-out judge prompts as the guardrails.

The headline I want from RL is "validator pass + judge factual both go up, with KL bounded". If that lands, the format-as-RL-substrate thesis works.

If it doesn't land, I want to know precisely why — which is the whole point of building the eval rigorously first.

---

## Files referenced

A reverse index so this post doubles as a code review of the SFT phase. All paths relative to repo root unless noted.

**Format & validator**
- [`docs/def.md`](https://github.com/JayZenith/glyph/blob/main/docs/def.md) — format spec
- [`core/validator.py`](https://github.com/JayZenith/glyph/blob/main/core/validator.py) — single rule book; reused at synthesis, eval, and (next) RL

**Synthesis pipeline**
- [`data/build.sh`](https://github.com/JayZenith/glyph/blob/main/data/build.sh) — full pipeline (gen → postprocess → patch → filter → audit)
- [`data/generate.py`](https://github.com/JayZenith/glyph/blob/main/data/generate.py) — teacher = `gpt-5-mini`, validator-rejects bad samples inline
- [`data/postprocess.py`](https://github.com/JayZenith/glyph/blob/main/data/postprocess.py) — merge sequential think/act, wrap chat-template tokens
- [`data/patch_dataset.py`](https://github.com/JayZenith/glyph/blob/main/data/patch_dataset.py) — fix recoverable bugs (missing 🏷, unclosed 」)
- [`data/filter_dataset.py`](https://github.com/JayZenith/glyph/blob/main/data/filter_dataset.py) — drop anything still failing the validator
- [`data/prompts.yaml`](https://github.com/JayZenith/glyph/blob/main/data/prompts.yaml) — user-prompt seeds for the teacher

**Training**
- [`sft/train.py`](https://github.com/JayZenith/glyph/blob/main/sft/train.py) — entry point (`python -m sft.train …`); `--modules-to-save`, `--masking-mode` flags for the ablation
- [`sft/config.py`](https://github.com/JayZenith/glyph/blob/main/sft/config.py) — `TrainConfig` dataclass; defaults match the run
- [`sft/data.py`](https://github.com/JayZenith/glyph/blob/main/sft/data.py) — `load_traces`, `create_dataset`, assistant-only label masking
- [`sft/trainers.py`](https://github.com/JayZenith/glyph/blob/main/sft/trainers.py) — `ParamGroupTrainer`: separate optimizer LR for `lm_head`
- [`sft/merge_adapter.py`](https://github.com/JayZenith/glyph/blob/main/sft/merge_adapter.py) — CPU-side adapter→base merge for the `glyph-sft-v1` HF push

**Evaluation**
- [`sft/eval_formal.py`](https://github.com/JayZenith/glyph/blob/main/sft/eval_formal.py) — generation eval (validator-scored)
- [`sft/eval_test_loss.py`](https://github.com/JayZenith/glyph/blob/main/sft/eval_test_loss.py) — held-out forward-loss eval (110 traces, base vs SFT)
- [`sft/evals/scoring.py`](https://github.com/JayZenith/glyph/blob/main/sft/evals/scoring.py) — validator-wrapping scoring used inside training callback
- [`sft/evals/generation.py`](https://github.com/JayZenith/glyph/blob/main/sft/evals/generation.py) — multi-round tool-call rollout used at eval time
- [`sft/evals/llm_judge.py`](https://github.com/JayZenith/glyph/blob/main/sft/evals/llm_judge.py) — post-hoc LM-judge pass (`gpt-5-mini`)
- [`sft/evals/prompts.yaml`](https://github.com/JayZenith/glyph/blob/main/sft/evals/prompts.yaml) — 32-prompt eval set (5 used for ablation; full 32 for the SFT report)
- [`sft/evals/gen_callback.py`](https://github.com/JayZenith/glyph/blob/main/sft/evals/gen_callback.py) — Trainer callback that runs the 5-prompt smoke during training

**Docs / artifacts**
- [`docs/ablation.md`](https://github.com/JayZenith/glyph/blob/main/docs/ablation.md) — 2×2 protocol + results + raw eval JSON paths
- [`docs/ablation/`](https://github.com/JayZenith/glyph/tree/main/docs/ablation) — per-run `eval_formal_*.json` and `eval_test_loss_*.json`
- [`README.md`](https://github.com/JayZenith/glyph/blob/main/README.md) — top-level reproduction commands
- [`blog/sft_tutorial.md`](https://github.com/JayZenith/glyph/blob/main/blog/sft_tutorial.md) — hands-on, command-by-command walkthrough

*Code, model, dataset, ablation evidence: [github.com/JayZenith/glyph](https://github.com/JayZenith/glyph). Comments and corrections welcome.*
