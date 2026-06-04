# SFT → RLVR for a Rust tool-use agent

Teaching `Qwen3-4B-Base` a coding-agent protocol on real Rust tasks, then running the
honest experiment: **does RLVR add anything on top of a strong SFT model, and can you
predict the answer before spending the GPUs?**

Tools execute for real against sandboxed crates. `cargo_run` counts as success only if
stdout exactly matches the oracle; `cargo_test` only if tests pass. The reward is a
compiler, not a learned preference model — the model cannot fake outcomes.

```text
assistant -> CALL read_file(id="c1", file_path="src/main.rs")
tool      -> RESULT c1: status: success  stdout: fn main() { ... }
assistant -> CALL apply_patch(id="c2", file_path="src/main.rs", find="...", replace="...")
tool      -> RESULT c2: status: success  stdout: patch applied
assistant -> CALL cargo_run(id="c3", project_path=".")
tool      -> RESULT c3: status: success  stdout: ada:4,bob:2,cy:8     # exact oracle match
assistant -> FINAL: patched the filter pipeline; stdout now matches.
```

## TL;DR (the honest result)

- **SFT works.** SFT_V1 solves 68/69 held-out tasks (`terminal_tool_success 0.986`). The
  skill — read, patch, verify against the real compiler — is installed and solid.
- **The first RL runs regressed; the final targeted pass@8 run won, then failed the full
  formal eval.** Not from vibes — from two
  structural facts that a single `pass@k` scan exposed:
  1. **RL can't install a behavior absent from its own rollouts.** The one SFT gap
     (stopping after success) did not appear on the original RL training prompts: the
     model never churned there, so GRPO had no useful stop/churn contrast. Stop-targeted
     runs collapsed (`RLVR_V1` 52→20 valid).
  2. **RL can't lift capability the policy has already saturated.** The pass@k scan found
     **0 capability-gap prompts and 95/134 already solved**; the "addressable" band is
     jammed at 7–8/8 (failures are decoding noise, not skill). RL on it *churned* the band
     and drifted the solved prompts down (`RLVR_PASSK_25` pass@k 0.907→0.875).
  3. **RL can lift a deliberately mixed band.** Re-scanning the original held-out failures
     found 8 prompts where SFT_V1 already had latent capability (`0<pass@8<8`). Training
     only on those with the corrected reward/anchor moved **47/64 → 54/64** solves at
     step 25, but the same checkpoint regressed the original 69-prompt HF/Transformers
     formal eval to **19/69 valid traces** and **47/69 terminal successes**.
- **The deliverable is the targeting rule and the failure boundary**, measured and
  reproducible: RLVR can improve a narrow mixed band, but full-model GRPO can still damage
  the broader tool-protocol distribution unless the protocol prior is preserved much more
  strongly.

For the full narrative + a from-scratch primer on PRIME-RL / `verifiers` / GRPO:
[`blog/blog_copy_copy.md`](blog/blog_copy_copy.md). For the raw technical lab notes:
[`rl/RLVR_NOTES.md`](rl/RLVR_NOTES.md).

## The stack

| layer | what it is | in this repo |
|---|---|---|
| [`verifiers`](https://github.com/willccbb/verifiers) | environment + reward library. `MultiTurnEnv` (the tool loop), `Rubric` (weighted reward funcs) | `rl/task_trace.py::RustToolEnv`, reward `_rust_tool_reward` |
| [PRIME-RL](https://github.com/PrimeIntellect-ai/prime-rl) | async GRPO: decoupled **trainer** / **orchestrator** / **inference** + frozen **teacher** for KL anchoring | `rl/configs/task_trace/*.toml`, launched via `rl/train.py` |
| RLVR | RL with **verifiable** rewards — signal from a real verifier (cargo), not a reward model | `agent_runtime/rust/` runs real `cargo` in per-rollout sandboxes |

**GRPO in one line:** sample `G` rollouts per prompt, advantage `A_i = (r_i − mean(r)) /
std(r)` within the group (no critic). If all `G` rewards are equal, `std=0` → advantage 0 →
**no gradient**. PRIME-RL's `zero_advantage` filter drops those groups — so *only
prompts with within-group reward variance teach anything*. This single fact explains every
result below.

## Results

### SFT — held-out 69 (`sft/eval_formal.py`)

| model | base | train data | valid_traces | clean_end | terminal_tool_success |
|---|---|---|---|---|---|
| `JayZenith/SFT_V1` | Qwen3-4B-Base | `signal_1062` (depth-1 recovery) | **52/69** | 0.754 | **0.986** |
| `JayZenith/SFT_V2` | Qwen3-4B-Base | `signal_v2_1323` (variable depth) | 48/69 | 0.70 | 0.96 |
| `JayZenith/SFT_V3` | Qwen3-4B-Base | `signal_v3` (deep + clean endings) | 50/69 | 0.725 | 0.99 |

`terminal_tool_success` ≈ solves; `clean_end` ≈ stops cleanly. The gap between them is the
**stopping** problem, and it plateaus at 0.72–0.75 across these three data variants, so
naively adding more of that SFT data did not fix it.

![RLVR_V1 collapse](blog/assets/fig_collapse.png)

### RLVR — failures first, then a narrow win

| model | from | what changed | outcome |
|---|---|---|---|
| `JayZenith/RLVR_V1` | SFT_V1 | stacked-penalty stopping reward, `teacher-tau 0.01` | **collapse**: valid 52→20, clean_end 0.75→0.33, terminal 0.99→0.70 |
| `RLVR_B` | SFT_V1 | corrected bounded reward **+** `--terminal-on-success` | regressed 52→19 (changes two things; not a clean control) |
| `JayZenith/RLVR_PASSK_25` | SFT_V1 | capability lift on 39-prompt band, verifier `+8` reward, `tau 0.2` | **regressed**: pass@k 0.907→0.875 on the 39 (6 up / 13 down / 20 flat) |
| local step-25 final run | SFT_V1 | 8 held-out-failure mixed prompts, corrected reward, `teacher-tau 0.4`, activation checkpointing | **targeted pass@8 win**: 47/64→54/64 on the 8 |
| `JayZenith/RLVR_HELDOUT69_PASSK_STEP25` | final step-25 checkpoint | same model, original HF formal eval on all 69 | **not robust**: valid 52→19, terminal 68→47 |

![pass@k band](blog/assets/fig_passk_band.png)
![RLVR_PASSK_25 eval](blog/assets/fig_passk25_eval.png)

## Reproduce

```bash
git clone https://github.com/JayZenith/glyph.git && cd glyph
bash sft/setup/install_sft_env.sh && source /workspace/.venv/bin/activate
```

**SFT (SFT_V1 recipe):**
```bash
python -m sft.train \
  --model Qwen/Qwen3-4B-Base --tokenizer Qwen/Qwen3-4B-Base \
  --data synthetic_data/signal_1062.jsonl \
  --output runs/SIGNAL_1062_SFT_E3_LR2E5 \
  --epochs 3 --batch-size 1 --grad-accum 8 --lr 2e-5 \
  --max-seq-length 4096 --no-train-split
# deep data (v2/v3): --max-seq-length 11000 --gradient-checkpointing  (traces reach ~10.4k tok)
```

**Held-out eval (any SFT or RLVR checkpoint):**
```bash
python -m sft.eval_formal --sft-model <model-or-path> \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml --prompt-section post_eval_heldout_69 \
  --cases-root runs/rlvr1/rust_cases/eval_heldout_69 \
  --output out.json --max-new-tokens 4000 --max-tool-rounds 15
```

**pass@k scan (the diagnostic — run this before any RLVR):**
```bash
python sft/passk_scan_vllm.py --sft-model JayZenith/SFT_V1 \
  --prompt-file runs/rlvr_passk_train150/prompts.yaml --prompt-section train_passk_scan_134 \
  --cases-root runs/rlvr_passk_train150/cases -k 8 --temperature 0.8 \
  --output results/passk_train134.json
# band: 0<solves<k = rlvr-target (gradient) | ==k = solved | ==0 = capability-gap
```

> **vLLM scan gotcha (cost us a day):** vLLM defaults to `skip_special_tokens=True`, which
> strips `<|im_end|>` from the output text. A *string* stop on `"<|im_end|>"` then never
> matches, generation runs past every turn boundary, no tools execute, and the scan reports
> **0/8 on prompts the model actually solves**. Stop on the token **id**
> (`tokenizer.convert_tokens_to_ids("<|im_end|>")`) and re-append `<|im_end|>` so the
> protocol parser can segment turns. Always compare before/after on the **same** engine.

**RLVR final targeted run (the 8-prompt win):**

Dataset:
```bash
synthetic_data/rl_prompts_heldout69_passk_targets.jsonl
synthetic_data/heldout69_passk_target_names.txt
```

Training environment:
```bash
git clone https://github.com/JayZenith/glyph.git && cd glyph
bash rl/setup/install_prime_rl.sh
source /workspace/prime-rl-src/.venv/bin/activate
```

Exact successful launch:
```bash
python rl/train.py \
  --data synthetic_data/rl_prompts_heldout69_passk_targets.jsonl \
  --output outputs/rlvr_heldout69_passk8_targets_seq8192_mlen12288_train2_memfix \
  --max-steps 50 \
  --batch-size 8 \
  --rollouts-per-example 8 \
  --seq-len 8192 \
  --max-model-len 12288 \
  --teacher-max-model-len 12288 \
  --max-completion-tokens 1536 \
  --learning-rate 2e-7 \
  --checkpoint-interval 25 \
  --temperature 0.8 \
  --max-tool-rounds 15 \
  --tool-timeout 30 \
  --teacher-tau 0.4 \
  --activation-checkpointing \
  --fused-lm-head-token-chunk-size auto \
  --prime-rl-gpu-ids 0,1,2 \
  --num-infer-gpus 1 \
  --num-train-gpus 2 \
  --gpus-per-node 3 \
  --port 8000 \
  --teacher-device 3
```

This was run on a 4xA100 instance. GPUs `0,1,2` were assigned to PRIME-RL
(trainer + inference); GPU `3` was reserved for the frozen teacher via
`--teacher-device 3`, so it is intentionally outside `--prime-rl-gpu-ids`.

Why the memory flags matter: `seq_len=8192` alone crashed teacher scoring (`8192+1`
context) and full-finetune trainer backward OOMed until activation checkpointing plus
fused LM-head chunking were enabled. Successful trainer peak memory was ~21.7 GiB/GPU.

Matched pass@8 eval on checkpoint 25:
```bash
NAMES=$(paste -sd, synthetic_data/heldout69_passk_target_names.txt)
PYTHONPATH=/workspace/glyph python sft/passk_scan_vllm.py \
  --sft-model outputs/rlvr_heldout69_passk8_targets_seq8192_mlen12288_train2_memfix/weights/step_25 \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
  --prompt-section post_eval_heldout_69 \
  --cases-root synthetic_data/eval_blueprints \
  --names "$NAMES" \
  -k 8 \
  --temperature 0.8 \
  --max-new-tokens 4000 \
  --max-tool-rounds 15 \
  --tool-timeout 30 \
  --max-model-len 12288 \
  --dtype bfloat16 \
  --output results/RLVR_HELDOUT69_PASSK_STEP25/passk8_step25_8targets.json \
  --no-resume
```

Result:
```text
SFT_V1:   47/64 = 0.734
step_25:  54/64 = 0.844
delta:    +7 solves, +10.9 pts
```

Full original held-out 69 formal eval on the same checkpoint:
```bash
python -m sft.eval_formal \
  --sft-model JayZenith/RLVR_HELDOUT69_PASSK_STEP25 \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
  --prompt-section post_eval_heldout_69 \
  --train-data synthetic_data/signal_1062.jsonl \
  --cases-root runs/rlvr1/rust_cases/eval_heldout_69 \
  --output results/RLVR_HELDOUT69_FORMAL_STEP25/eval_formal_heldout_69_step25.json \
  --max-new-tokens 4000 \
  --max-tool-rounds 15 \
  --tool-timeout 30
```

Result:
```text
SFT_V1 baseline: valid 52/69, terminal_tool_success 68/69
step_25:         valid 19/69, terminal_tool_success 47/69
failure shape:   48 missing_final/dirty_final, 22 task_failure, 7 truncated
```

So the checkpoint is useful as an RLVR targeting artifact, not as a deployable model.
It improved the selected mixed band while damaging the broader tool-use/protocol prior.

Artifacts:
```text
results/RLVR_HELDOUT69_PASSK_STEP25/passk8_step25_8targets.json
results/RLVR_HELDOUT69_PASSK_STEP25/passk8_step25_comparison.csv
results/RLVR_HELDOUT69_PASSK_STEP25/rlvr_step25_training_metrics.csv
results/RLVR_HELDOUT69_PASSK_STEP25/training_artifacts/
results/RLVR_HELDOUT69_FORMAL_STEP25/eval_formal_heldout_69_step25.json
```

The earlier 39-prompt RLVR procedure remains documented in
[`rl/setup/rl_setup_training.md`](rl/setup/rl_setup_training.md). Reward lives in
`rl/task_trace.py`; properties are locked by `reward_golden_tests.py`.

## Repo map

```
synthetic_data/   data generation + datasets (data_lineage.md), pass@k band, RL prompts
sft/              SFT train (train.py), eval (eval_formal.py), pass@k scan (passk_scan*.py)
rl/               PRIME-RL env + reward (task_trace.py), configs/, train.py wrapper, RLVR_NOTES.md
agent_runtime/    protocol parser + real cargo execution / per-rollout sandboxing
results/          eval JSON + tensorboard/W&B/logs/rollouts, including final step-25 artifact
blog/             blog_copy_copy.md (current narrative + primer), make_figures.py, assets/*.png
reward_golden_tests.py   reward unit tests (solving dominates, bounded, format floor)
```

## Datasets (`synthetic_data/`)

GPT-authored task specs → materialized into **real crates** → kept only if real tool
execution matched the intended trajectory (`data_lineage.md`).

- `signal_1062.jsonl` — 1062 traces; all recovery is depth-1 (one fail, one fix).
- `signal_v2_1323.jsonl` — + 261 variable-depth (1–5) recovery cases.
- `signal_v3.jsonl` — + 199 depth-3..5 cases, oversampling clean `PASS→FINAL` (2083 rows / 1522 unique).
- `rl_prompts_passk_target.jsonl` — the 39 rlvr-target prompts (the RLVR_PASSK band).
- `rl_prompts_heldout69_passk_targets.jsonl` — the final 8 mixed held-out-failure prompts.

Train↔eval audited at 0.92 source similarity, 0 near-duplicates
(`synthetic_data/audit_blueprint_similarity.py`).
