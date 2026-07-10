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

Strict `valid_trace` = terminal cargo success + one clean `FINAL` after it +
exact `CALL` syntax + no tool use after success.

**Headline numbers use only trace-retained runs** — runs whose full
per-rollout traces are saved and inspectable. Two additional repetitions exist
for SFT (97, 100) and dense (102, 99), but only as per-prompt aggregate counts
(raw traces not retained): they cannot be audited for trace validity or reward
gaming, so they carry no evidentiary weight here. They remain in the public
eval dataset under that label; their direction is consistent with the retained
runs.

| valid@8 / 150 | trace-retained run(s) |
| --- | --- |
| SFT_HALF_A_V8 | **95** |
| + sparse RLVR (RLVR_POOL_B_V8_STEP10) | **98 / 96 / 98** |
| + dense-reward RLVR (RLVR_VFINAL_STEP10) | **102** |
| + compiler-aware RLVR (RLVR_VFINAL2_STEP10) | **95 / 96 / 94** |

Paired prompt-level sign-flip permutation on the retained runs: dense vs SFT
**+7** (11 prompts up, 4 down, p ≈ 0.12); sparse vs SFT +3 (p ≈ 0.55);
compiler-aware vs SFT ±0 (p = 1.0); compiler-aware vs dense −7 (p ≈ 0.14).
**Nothing is significant.** Repeated evaluation of a single model moves
valid@8 by ±2–3 prompts on its own (sparse: 98/96/98) — the size of every
observed difference.

Two caveats bound every number above:

- **Eval repetitions are not independent seeded samples.** The harness exposes
  no sampling seed (vLLM default seed applies); repetitions differ only
  through runtime nondeterminism — batching, scheduling, tool timing.
  Sampling config: temperature 0.8, top-p 1.0 (default), max 4000 new tokens,
  k = 8, max 20 tool rounds.
- **Each reward arm is one training run.** Training-seed variance was never
  measured, and evaluation variability alone is comparable to the observed
  effect. Causal attribution of any difference to the reward shape would
  require multiple training seeds per arm.

**Why the sparse arm couldn't move: zero-advantage filtering.** The sparse
baseline rewards +10 only for a clean pass, with fixed failure penalties —
sparse, but not binary. All-fail rollout groups whose 8 rollouts share the
same failure profile get identical rewards → zero group-relative advantage →
the zero-advantage filter drops them, so those prompts contribute no
verifier-driven signal (at step 0 the filter dropped 64/96 rollouts; 8–67% per
batch across the 30-batch run, verified from the raw orchestrator log). A
dense partial-credit reward (compile + test-pass fraction) was built to break
those ties.

**The compiler-aware A/B did not beat the generic dense reward.** Same
base/data/steps/hyperparameters, only the reward shape changed: the
compiler-aware arm (`RLVR_VFINAL2_STEP10`) scores progress by the furthest
`rustc` phase reached (parse → type → borrow → compiles). Like the dense
reward it breaks ties inside all-fail groups — step-0 zero-advantage filtering
barely separates the arms (sparse 64/96 filtered, dense 78/96, compiler-aware
64/96, from the raw logs) — but its retained runs scored **95 / 96 / 94:
7 below the retained dense run on the paired run-1 comparison (p ≈ 0.14) and
level with SFT**. A Goodhart story fits ("later
compiler phase" is a proxy further from tests-passing than the dense reward's
own compile/test-fraction signal), but with one training run per arm and
p ≈ 0.14 on the auditable data, this is an observation, not an established
regression. See the [write-up](https://jayzenith.github.io/GLYPH/).

**What the saved training rollouts show (direct evidence).** From the retained
training batches (36 groups each for sparse/dense, steps 10/20/29; 142 groups
for compiler-aware, steps 0–11): all-fail groups were 3% of sparse batches,
22% of dense, 11% of compiler-aware — and the shaped rewards did break reward
ties inside them (dense 7/8 all-fail groups had >1 distinct reward,
compiler-aware 15/15). So the shaping created within-group variance where it
applied, but all-fail groups were a small share of batches, and 25–47% of all
groups were still dropped whole by the zero-advantage filter. Saved steps are
a small non-random sample of training.

**Where the effect might live (exploratory).** Pooling all repetitions —
*including the aggregate-only ones* — and banding prompts by SFT difficulty
puts the dense arm's movement on sometimes-solved prompts: +0.031 pass@1 on
the 1–3/8 band (n=27), ~0 elsewhere. But the bootstrap 95% CI on that band is
**[−0.023, +0.086]** — consistent with a small frontier effect *and with
zero*. These bands group held-out eval prompts; the GRPO zero-advantage
mechanism operates on training groups. Connecting them is a plausible
hypothesis, not a finding (`analysis/pooled_band_analysis.py`).

Artifacts: `JayZenith/SFT_HALF_A_V8` · dense adapters
`JayZenith/RLVR_VFINAL_STEP{10,20,30}` · compiler-aware adapters
`JayZenith/RLVR_VFINAL2_STEP{5,10}` · sparse baseline
`JayZenith/RLVR_POOL_B_V8_STEP{10,20,30}`.

Raw per-rollout eval data (every trace behind every number above, not just
aggregates): [`JayZenith/Glyph-RLVR-Eval-Results`](https://huggingface.co/datasets/JayZenith/Glyph-RLVR-Eval-Results)
on the Hub.

### Known limitations of the eval

- **The 150 held-out cases are not 150 independent tasks.** Keyword-clustering
  the case names shows real concentration: ~18% are config-merge/precedence
  variants, ~17% enum-dispatch variants, ~11% leaderboard/ranking variants —
  roughly half the set falls into 3 recognizable template families, re-skinned
  with different field names and sample data. The effective sample size behind
  the pass@8 numbers (and the p-values) is smaller than n=150 implies.
- **Leakage is checked, not fully ruled out.** RL training data and the eval
  set share zero exact `case_id`/`blueprint_root` overlap, and zero crate
  source files match after normalizing comments, whitespace, and string/numeric
  literals (703 training crates vs. 150 eval crates,
  `synthetic_data/audit_blueprint_similarity.py`; nearest pair: a league-table
  tiebreak variant at 0.92 token similarity). What isn't ruled out:
  the same *logical* bug pattern (e.g. a precedence bug) appearing under
  different field/function names in both sets — a soft template overlap a
  hash can't catch, and plausible given the family concentration above.
- **The "sandbox" is per-rollout isolation, not containment.** Each rollout
  patches its own crate clone via path rewriting
  (`agent_runtime/rust/runtime.py`); absolute paths, `..` traversal, and
  symlink escapes are not blocked. A scan of all ~135k saved headline-eval
  tool calls found no traversal, so the published numbers are unaffected —
  but real path containment is future work, and this is not a security
  boundary.
- **Grading tests are model-editable.** `apply_patch` can modify the tests the
  reward checks. Auditing all 52,696 `apply_patch` calls in the trace-retained
  eval runs (`analysis/test_tamper_audit.py`) found exactly one counting
  rollout that altered a test: an *SFT-baseline* rollout flipped a test
  assertion and passed. The same prompt had two clean solves in that run, so
  no valid@8 count changes. No counted RLVR rollout showed tampering; the
  aggregate-only repetitions cannot be audited for this. Immutable or
  restored-before-verification tests are future work.
- **Provenance is partial.** The eval JSONs record no command, commit, model
  revision, or sampling seed; the run configuration documented above is
  reconstructed from the repo's committed commands, and anything not
  recoverable is marked unknown in
  [`docs/PROVENANCE.md`](docs/PROVENANCE.md).

## Design decisions that mattered

- **One execution runtime, three stages.** `agent_runtime/` (executor, sandbox
  path-rewriting, RESULT renderer) serves SFT data generation
  (`synthetic_data/materialize_specs.py`), the RL environment
  (`rl/environment.py`), and the eval harness — the model sees byte-identical
  trace formatting in training, RL, and eval. Format drift between stages made
  the model hallucinate whole tool RESULTs inside its own turn.
- **SFT traces were materialized, not written.** The generator produced JSON
  specs (crate files + tool steps tagged `expect_status: failed|success`);
  every step was executed through real cargo, and any case whose planned
  failure didn't fail — or whose fix didn't pass — was rejected. Recover
  families must fail at least once before succeeding, so error recovery was
  learned from real rustc output.
- **Assistant-only loss masking, zero truncation** (`sft/data.py`): loss on
  assistant tokens only (unmasked RESULT tokens teach a model to invent tool
  outputs), and tokenization asserts every trace fits in context rather than
  silently truncating.
- **RLVR is anchored, not free-running:** on-policy distillation toward the
  frozen SFT model itself (`--teacher-tau 0.2`), a small KL to the rollout
  policy, and gibberish/repetition/zero-advantage filters all enforced.

## What this demonstrates

A working, audited post-training loop — synthetic data → SFT → RLVR → pass@8
eval → trace-level verification — run end to end and then audited against its
own artifacts, including adversarially. The defensible conclusion: the
retained dense run showed a small, non-significant improvement (+7, p ≈ 0.12);
sparse showed no clear improvement; the retained compiler-aware run scored
level with SFT and below dense; training-seed variance was never measured
(one run per arm), so no difference can be causally attributed to reward
shape; and the frontier-band story is an exploratory hypothesis whose CI
includes zero. The strongest contribution is the audited infrastructure, the
negative-result diagnosis, and the documented verifier weaknesses
(spec-gaming, editable tests, path rewriting).

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

## Strict Pass@1 Eval (greedy)

SFT base:

```bash
CUDA_VISIBLE_DEVICES=0 python -m sft.eval_formal \
  --sft-model JayZenith/SFT_HALF_A_V8 \
  --train-data synthetic_data/signal_v3_sft_half_a.jsonl \
  --prompt-file sft/evals/eval_prompts_heldout_150.yaml \
  --prompt-section post_eval_heldout_150 \
  --cases-root runs/heldout150_sft_half_a_v8 \
  --output results/SFT_HALF_A_V8/eval_formal_heldout_150.json \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --prompt-batch-size 8 \
  --tool-workers 16
```

RL adapter — add `--sft-adapter` (loads the LoRA from HF onto the base):

```bash
CUDA_VISIBLE_DEVICES=0 python -m sft.eval_formal \
  --sft-model JayZenith/SFT_HALF_A_V8 \
  --sft-adapter JayZenith/RLVR_VFINAL_STEP10 \
  --train-data synthetic_data/signal_v3_sft_half_a.jsonl \
  --prompt-file sft/evals/eval_prompts_heldout_150.yaml \
  --prompt-section post_eval_heldout_150 \
  --cases-root runs/heldout150_rlvr_vfinal_step10 \
  --output results/RLVR_VFINAL_STEP10/eval_formal_heldout_150.json \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --prompt-batch-size 8 \
  --tool-workers 16
```

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
