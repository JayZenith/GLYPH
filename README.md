# GLYPH

A verifiable-reward **RL environment + eval suite** for a Rust tool-use coding
agent (Qwen3-4B). The model emits `CALL tool {...}` blocks, tools execute against
real Rust crates via cargo, and it must finish with a clean `FINAL`. Built on
`verifiers` / PRIME-RL — `rl/task_trace.py` exposes
`load_environment() -> vf.Environment`.

Full write-up (deployed): <https://jayzenith.github.io/GLYPH/> (source:
[`blog/index.html`](blog/index.html)).
Honest experiment history (every era, including invalidated runs):
[`docs/EXPERIMENT_HISTORY.md`](docs/EXPERIMENT_HISTORY.md). Adversarial audit
+ corrections: [`docs/AUDIT_2026-07.md`](docs/AUDIT_2026-07.md). Provenance:
[`docs/PROVENANCE.md`](docs/PROVENANCE.md). First claims audit (historical):
[`review/CLAIMS_AUDIT.md`](review/CLAIMS_AUDIT.md).


Published as a standalone [`verifiers`](https://github.com/PrimeIntellect-ai/verifiers)
environment on the [Prime Intellect Environments Hub](https://app.primeintellect.ai/dashboard/environments/jayzenith/glyph)
(`environments/glyph/`, crate data on the companion
[`JayZenith/glyph-crates`](https://huggingface.co/datasets/JayZenith/glyph-crates)
dataset) — install with `prime env install jayzenith/glyph`.

## Results (held-out 150 unseen crates)

`valid_trace` = terminal cargo success + one clean `FINAL` + exact `CALL`
syntax + no tool use after success.

Headline numbers use **trace-retained runs only** (full per-rollout traces
saved and auditable). SFT and dense have 2 extra repetitions that survive only
as counts (SFT 97, 100 · dense 102, 99) — unauditable, excluded, kept on HF
under that label.

| valid@8 / 150 | trace-retained run(s) |
| --- | --- |
| SFT_HALF_A_V8 | **95** |
| + sparse RLVR (RLVR_POOL_B_V8_STEP10) | **98 / 96 / 98** |
| + dense RLVR (RLVR_VFINAL_STEP10) | **102** |
| + compiler-aware RLVR (RLVR_VFINAL2_STEP10) | **95 / 96 / 94** |

Paired prompt-level sign-flip permutation (`analysis/retained_run_stats.py`):

- dense vs SFT: **+7** (11 prompts up / 4 down), p ≈ 0.12
- sparse vs SFT: +3, p ≈ 0.55
- compiler vs SFT: ±0 (p = 1.0) · compiler vs dense: −7, p ≈ 0.14

**Nothing is significant.** Re-evaluating one model moves valid@8 by ±2–3 on
its own (sparse: 98/96/98) — the size of every gap above. Two hard caveats:

- Repetitions share vLLM's default seed (no seed flag in the harness); they
  differ only through runtime nondeterminism. T=0.8, top-p 1.0, k=8, 4000 max
  new tokens, 20 tool rounds.
- One training run per arm — training-seed variance unmeasured, so no
  difference is causally attributable to the reward shape.

**Why sparse was flat:** 8 rollouts that fail identically score identically →
zero group-relative advantage → group dropped. Step 0: 64/96 dropped; 8–67%
per batch (`glyph_results/RLVR_POOL_B_V8_STEP10/logs/orchestrator.log`).
Dense partial credit (compile bonus + test-pass fraction) was built to break
those ties.

**The compiler-aware A/B lost anyway.** Identical command except reward flags;
grades failed rollouts by furthest rustc phase reached. Result: level with
SFT, −7 vs dense. Goodhart is a plausible story, not an established one.

**Training rollouts (direct evidence):** shaped rewards broke reward ties in
7/8 (dense) and 15/15 (compiler) all-fail groups — the mechanism worked — but
all-fail groups were only 3–22% of batches, and 25–47% of all groups were
dropped whole (`glyph_results/*/rollouts_step_*/train_rollouts.jsonl`).

**Exploratory — where movement sits** (pools the unauditable reps;
`analysis/pooled_band_analysis.py`). Δpass@1 vs SFT:

| band (SFT solves/8) | n | sparse | dense | compiler |
| --- | ---: | ---: | ---: | ---: |
| never solved (0) | 55 | −0.015 | −0.004 | −0.023 |
| sometimes (1–3) | 27 | +0.003 | **+0.031** | +0.022 |
| sometimes (4–6) | 28 | −0.039 | +0.011 | −0.004 |
| usually (7–8) | 40 | −0.008 | −0.007 | −0.013 |

Only the shaped arms move positive, only on sometimes-solved prompts — the
pattern the gradient mechanism predicts — but every positive CI includes zero.
Hypothesis, not finding.

Artifacts: `JayZenith/SFT_HALF_A_V8` · dense adapters
`JayZenith/RLVR_VFINAL_STEP{10,20,30}` · compiler-aware adapters
`JayZenith/RLVR_VFINAL2_STEP{5,10}` · sparse baseline
`JayZenith/RLVR_POOL_B_V8_STEP{10,20,30}`.

Raw per-rollout eval data (every trace behind every number above, not just
aggregates): [`JayZenith/Glyph-RLVR-Eval-Results`](https://huggingface.co/datasets/JayZenith/Glyph-RLVR-Eval-Results)
on the Hub.

### Known limitations of the eval

- ~Half the 150 cases fall into 3 template families → effective n < 150.
- Leakage: zero exact matches after normalizing comments/whitespace/literals
  (703×150, `synthetic_data/audit_blueprint_similarity.py`; nearest pair 0.92);
  soft template overlap not ruled out.
- The "sandbox" is path rewriting, not containment. No traversal in ~135k
  saved calls; real containment is future work.
- Grading tests are model-editable. 52,696 patch calls audited
  (`analysis/test_tamper_audit.py`): one SFT-baseline assertion flip (no count
  changed), zero counted RLVR tampering. Immutable tests are future work.
- Provenance per run (recovered / inferred / unknown):
  [`docs/PROVENANCE.md`](docs/PROVENANCE.md).

## Design decisions that mattered

- **One execution runtime, three stages.** `agent_runtime/` serves SFT data
  generation, the RL environment, and the eval harness — byte-identical trace
  formatting everywhere. Format drift had made the model hallucinate whole
  tool RESULTs.
- **SFT traces materialized, not written.** The generator produced specs;
  every step ran through real cargo; planned failures that didn't fail (or
  fixes that didn't pass) rejected the case (`synthetic_data/materialize_specs.py`).
  Error recovery was learned from real rustc output.
- **Assistant-only masking, zero truncation** (`sft/data.py:73,53`) — unmasked
  RESULT tokens teach a model to invent tool outputs; truncated traces teach
  truncated protocol.
- **RLVR anchored:** on-policy distillation toward the frozen SFT model
  (`--teacher-tau 0.2`), small KL to the rollout policy, gibberish/repetition/
  zero-advantage filters enforced.

## What this demonstrates

Data → SFT → RLVR → pass@8 eval → trace-level verification, run end to end and
then adversarially audited twice ([`docs/AUDIT_2026-07.md`](docs/AUDIT_2026-07.md)).
Defensible conclusion: dense +7 (not significant), sparse flat, compiler-aware
beat neither; training-seed variance unmeasured; frontier story exploratory.
The contribution is the audited infrastructure, the negative-result diagnosis,
and the documented verifier weaknesses.

## Hardware

Run on vast.ai (NVIDIA RTX PRO 6000 Blackwell, 96 GB each):

- **RLVR:** 4 GPUs — 2 trainer, 1 student inference, 1 auto-launched teacher.
- **Eval:** 1 GPU (vLLM).
- **Disk:** the per-rollout cargo sandboxes are large — a pass@8 run over 150
  crates writes ~20 GB, and they accumulate across runs (I filled a 200 GB disk).
  Clear `runs/` between eval runs.

## GPU Setup

```bash
git clone https://github.com/JayZenith/GLYPH.git
cd GLYPH
git pull --ff-only
```

SFT / eval environment:

```bash
bash sft/setup/install_sft_env.sh
source .venv/bin/activate
```

PRIME-RL environment (RL training):

```bash
PRIME_RL_ENABLE_LORA=1 bash rl/setup/install_prime_rl.sh
source /workspace/prime-rl-src/.venv/bin/activate
```

## SFT Train

Produces `runs/SIGNAL_v3_HALF_A_SFT_E3_LR2E5/final`, uploaded as
`JayZenith/SFT_HALF_A_V8`.

```bash
python -m sft.train \
  --model Qwen/Qwen3-4B-Base \
  --tokenizer Qwen/Qwen3-4B-Base \
  --data synthetic_data/signal_v3_sft_half_a.jsonl \
  --output runs/SIGNAL_v3_HALF_A_SFT_E3_LR2E5 \
  --epochs 3 \
  --batch-size 1 \
  --grad-accum 8 \
  --lr 2e-5 \
  --max-seq-length 12000 \
  --no-train-split \
  --gradient-checkpointing
```

## RLVR Train — reward-shape A/B

Runs on 4 GPUs. PRIME-RL launches the frozen teacher itself
(`--num-teacher-gpus 1`) and wires `orchestrator.teacher` to it — no manual
teacher server.

The reward shape is the **only** thing that changes between arms — a controlled
A/B to test whether a Rust-compiler-aware verifier extracts more signal than a
generic dense one:

- **Sparse baseline:** omit all `--progress-*` flags.
- **Arm A — generic dense:** `--progress-compile-bonus 0.5
  --progress-test-frac-bonus 2.0` (compile bonus + test-pass fraction).
- **Arm B — compiler-aware:** `--progress-error-ladder-bonus 2.5` (and dense
  flags off). Scores failed rollouts by the furthest rustc phase reached —
  `parse → type → borrow → compiles`, scaled `stage/4`. A borrow error proves
  the code type-checked, so the ladder is monotone in real progress and isn't
  gamed by churning error counts (see `rl/tests/test_reward_progress.py`).

Both arms run the **identical** command below — same base model
(`SFT_HALF_A_V8`), same `--data`, same `--max-steps`, same hyperparameters and
GPU layout. Only `$REWARD_FLAGS` (and `--lora-name` / `--output`, so artifacts
don't collide) differ. Neither `train.py` nor the eval harness exposes a seed
flag, so each arm is one training run, compared by evaluating each adapter
under the same pass@8 harness with repeated evaluations (no sampling seed;
differences arise from runtime nondeterminism) — not from a single greedy
number.

```bash
# Arm A — generic dense:
REWARD_FLAGS="--progress-compile-bonus 0.5 --progress-test-frac-bonus 2.0"
NAME=glyph-pool-b-dense-r64-a128;          OUT=outputs/RLVR_POOL_B_DENSE_R64_A128

# Arm B — compiler-aware (run this block instead for the other arm):
REWARD_FLAGS="--progress-error-ladder-bonus 2.5"
NAME=glyph-pool-b-compiler-aware-r64-a128; OUT=outputs/RLVR_POOL_B_COMPILER_AWARE_R64_A128

python rl/train.py \
  --model JayZenith/SFT_HALF_A_V8 \
  --teacher-model JayZenith/SFT_HALF_A_V8 \
  --lora-rank 64 \
  --lora-alpha 128 \
  --lora-dropout 0.0 \
  --lora-name "$NAME" \
  --data synthetic_data/rl_prompts_signal_v3_pool_b_mixed_oversampled.jsonl \
  --output "$OUT" \
  --max-steps 30 \
  --batch-size 96 \
  --max-inflight-rollouts 96 \
  --rollouts-per-example 8 \
  --seq-len 16384 \
  --max-model-len 16384 \
  --max-completion-tokens 4000 \
  --learning-rate 1e-6 \
  --weight-decay 0.01 \
  --checkpoint-interval 5 \
  --temperature 0.8 \
  --teacher-tau 0.2 \
  --max-tool-rounds 15 \
  --tool-timeout 30 \
  --activation-checkpointing \
  --fused-lm-head-token-chunk-size auto \
  --gpu-memory-utilization 0.70 \
  --prime-rl-gpu-ids 0,1,2,3 \
  --num-infer-gpus 1 \
  --num-train-gpus 2 \
  --num-teacher-gpus 1 \
  --gpus-per-node 4 \
  --port 8000 \
  --enforce-gibberish-filter \
  --enforce-repetition-filter \
  $REWARD_FLAGS
```

> External teacher instead of the auto-launched one: drop `--num-teacher-gpus`
> and pass `--teacher-base-url` / `--teacher-port`.

## Export RL LoRA

Export the *served* policy from `run_default/broadcasts/step_N` (not
`weights/step_N`) as a PEFT adapter:

```bash
python rl/scripts/export_prime_lora_adapter.py \
  --base-model JayZenith/SFT_HALF_A_V8 \
  --adapter-dir outputs/RLVR_SIGNAL_V4002_POOL_B_DENSE_LORA_R64_A128/run_default/broadcasts/step_10 \
  --output outputs/RLVR_SIGNAL_V4002_POOL_B_DENSE_LORA_R64_A128/hf_adapter_step10
```

The export contains `adapter_config.json`, `adapter_model.safetensors`, and
`prime_lora_adapter_export.json`.

## Pass@8 Eval (vLLM, the headline metric)

Greedy pass@1 is too noisy for a small effect; pass@8 with repeated
evaluations is the honest bar. The harness exposes no sampling-seed flag, so
repetitions all run under vLLM's default seed and are **not** independent
seeded samples — differences come from runtime nondeterminism (batching,
scheduling, tool timing). Config: temperature 0.8, top-p 1.0 (default),
max 4000 new tokens, k=8. If you extend the harness, set and record an
explicit distinct seed per repetition.
`--max-model-len 24576` gives headroom for tool-accumulated context at T=0.8
(16384 overflows on long recovery rollouts).

SFT base:

```bash
CUDA_VISIBLE_DEVICES=0 python -m sft.passk_scan_vllm \
  --sft-model JayZenith/SFT_HALF_A_V8 \
  --prompt-file sft/evals/eval_prompts_heldout_150.yaml \
  --prompt-section post_eval_heldout_150 \
  --cases-root runs/passk8_heldout150_sft_half_a_v8 \
  -k 8 \
  --temperature 0.8 \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --output results/SFT_HALF_A_V8/passk8_heldout150.json \
  --gpu-memory-utilization 0.90 \
  --max-model-len 24576 \
  --prompt-batch-size 8 \
  --save-rollouts
```

RL adapter:

```bash
CUDA_VISIBLE_DEVICES=0 python -m sft.passk_scan_vllm \
  --sft-model JayZenith/SFT_HALF_A_V8 \
  --sft-adapter JayZenith/RLVR_VFINAL_STEP10 \
  --max-lora-rank 64 \
  --prompt-file sft/evals/eval_prompts_heldout_150.yaml \
  --prompt-section post_eval_heldout_150 \
  --cases-root runs/passk8_heldout150_rlvr_vfinal_step10 \
  -k 8 \
  --temperature 0.8 \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --output results/RLVR_VFINAL_STEP10/passk8_heldout150.json \
  --gpu-memory-utilization 0.90 \
  --max-model-len 24576 \
  --prompt-batch-size 8 \
  --save-rollouts
```

For replication, rerun the same command 3× with a different `--cases-root` /
`--output` per run and keep `--save-rollouts` — repetitions without retained
traces cannot be audited and shouldn't carry claims (see the note above).
