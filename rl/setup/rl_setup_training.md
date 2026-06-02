# RLVR on SFT_V1 — capability lift

Goal: use RL for what it's actually good at — **raise solve-rate on train cases
the policy only solves *sometimes***. SFT_V1 already terminates cleanly in
distribution; the held-out churn/termination gap is an OOD tail RL can't install
(see Lessons). So we don't RL stopping. We RL solving, on the band where a
gradient exists.

Reward (`rl/task_trace.py`) is verifier-dominant with the termination tails
**zeroed** for this run:

```text
verifier passed              +8     <- the whole signal
structure valid              +0.5   } format floor
no tool call                 -2     }
malformed call (per, cap 4)  -1     }
FINAL / churn / round-cap     0     <- termination tails zeroed (not this run's goal)
```

Locked by `reward_golden_tests.py` (6 tests: solving dominates, termination neutral, bounded).

Base = SFT_V1.

## Pipeline

```
0. pass@k scan (pick targets)  ->  synthetic_data/passk_train134.json   [DONE: 39 targets]
1. freeze rlvr-target band      ->  synthetic_data/rl_prompts_passk_target.jsonl [DONE]
2. RLVR (GRPO) on that band     <- do this
3. measure in-set pass@k before vs after  <- the artifact
```

## 0. pass@k scan — find the RLVR-addressable band  ✅ DONE

Scanned the 134 depth≥3 train prompts (`runs/rlvr_passk_train150/`, section
`train_passk_scan_134`) with SFT_V1, k=8, T=0.8. Result in
`synthetic_data/passk_train134.json` (aggregate only: `{name, solves, k,
pass_at_k, band}`). Bands by `terminal_tool_success`: `0<solves<k` =
**rlvr-target**, `==k` = solved, `==0` = capability-gap.

Outcome: **95 solved (8/8) · 39 rlvr-target · 0 capability-gap.** The 39 targets
skew near-solved (27 at 7/8, 12 at ≤6/8) — gradient everywhere, modest lift
ceiling. To reproduce:

```bash
env HF_HOME=/workspace/.hf_home CUDA_VISIBLE_DEVICES=0 PYTHONPATH=/workspace/glyph \
  /workspace/prime-rl-src/.venv/bin/python sft/passk_scan.py \
    --sft-model JayZenith/SFT_V1 \
    --prompt-file runs/rlvr_passk_train150/prompts.yaml \
    --prompt-section train_passk_scan_134 \
    --cases-root runs/rlvr_passk_train150/cases \
    -k 8 --temperature 0.8 --output synthetic_data/passk_train134.json
```

This same json is the **SFT_V1 baseline** (the "before"): mean pass@k over the 39
targets = the number RL has to beat.

## 1. RL dataset (the 39 targets)  ✅ DONE

`synthetic_data/rl_prompts_passk_target.jsonl` — 39 rows, one per rlvr-target
case, in the schema `rl/train.py --data` reads (`prompt`, `kind`, `case_id`,
`expected_tool`, `expected_args`, `expected_tool_sequence`, `expected_output`,
`blueprint_root`, `trace_prefix`). Built directly from
`runs/rlvr_passk_train150/prompts.yaml` (NOT joined to `rl_prompts_v2_1323.jsonl`
— different case_ids/paths). RL ONLY on this band; solved / capability-gap
prompts give zero advantage. Rebuild if the band changes: filter
`passk_train134.json` to `band=="rlvr-target"`, pull those names from the yaml,
emit the schema above.

## 2. Install + run RLVR (2-GPU)  ← do this

```bash
git clone https://github.com/JayZenith/glyph.git && cd glyph
bash rl/setup/install_prime_rl.sh
source /workspace/prime-rl-src/.venv/bin/activate
```

```bash
mkdir -p outputs/rlvr_passk/logs
nohup env \
  HF_HOME=/workspace/.hf_home CARGO_HOME=$HOME/.cargo RUSTUP_HOME=$HOME/.rustup \
  PATH=/workspace/prime-rl-src/.venv/bin:$HOME/.cargo/bin:$PATH \
  PYTHONPATH=/workspace/glyph:/workspace/glyph/rl \
  /workspace/prime-rl-src/.venv/bin/python rl/train.py \
    --model JayZenith/SFT_V1 \
    --teacher-model JayZenith/SFT_V1 --teacher-device 0 --teacher-tau 0.2 \
    --prime-rl-gpu-ids 2,3 --num-infer-gpus 1 --num-train-gpus 1 --gpus-per-node 2 \
    --data synthetic_data/rl_prompts_passk_target.jsonl \
    --output outputs/rlvr_passk \
    --max-steps 200 --batch-size 24 --rollouts-per-example 8 \
    --seq-len 5120 --max-model-len 12288 --teacher-max-model-len 12288 \
    --max-completion-tokens 1536 --learning-rate 5e-7 --weight-decay 0.01 \
    --checkpoint-interval 25 --temperature 0.8 \
    --gpu-memory-utilization 0.70 --teacher-gpu-memory-utilization 0.50 \
    --max-tool-rounds 15 --tool-timeout 30 --port 8010 --teacher-port 8011 \
    > outputs/rlvr_passk/logs/launcher.log 2>&1 < /dev/null &
```

Settings that matter (the rest are scenery): `teacher-tau 0.2` (anchor to SFT —
`0.01` collapsed the first run), `rollouts-per-example 8` + `temperature 0.8`
(within-group variance is the whole gradient on a partial-solve prompt;
4 / 0.6 starved it), `zero_advantage` filter on
(`rl/configs/task_trace/orchestrator.toml`). Do NOT use `--terminal-on-success`
(that was the stopping experiment; see Lessons).

Logs: `tail -f outputs/rlvr_passk/logs/{launcher,orchestrator,trainer}.log`

## 3. Measure — pass@k before vs after (the artifact)

**Before** = SFT_V1 pass@k on the 39 targets, already in
`synthetic_data/passk_train134.json` (filter `band=="rlvr-target"`, mean the
`pass_at_k`).

**After** = re-scan the SAME 39 per checkpoint, on a **separate 1-GPU box** (the
RL box blocks while evaling). Same flags as the baseline scan, swapping the model
and output:

```bash
nohup env HF_HOME=/workspace/.hf_home CUDA_VISIBLE_DEVICES=0 PYTHONPATH=/workspace/glyph \
  /workspace/prime-rl-src/.venv/bin/python sft/passk_scan.py \
    --sft-model outputs/rlvr_passk/weights/step_25 \
    --prompt-file runs/rlvr_passk_train150/prompts.yaml \
    --prompt-section train_passk_scan_134 \
    --cases-root runs/rlvr_passk_train150/cases \
    -k 8 --temperature 0.8 \
    --output outputs/rlvr_passk/passk_step25.json \
    > outputs/rlvr_passk/logs/eval_step25.log 2>&1 < /dev/null &
```

(Scan all 134; just compare the 39 target names against baseline so before/after
use the identical set.) Report mean pass@k on the 39, SFT_V1 vs each checkpoint —
that delta is the deliverable. Label it **in-set** (no held-out split for v1).

**Early-stop**: best checkpoint is usually early (~step 25); later checkpoints
regressed in every prior run. **Kill** if pass@k drops below the SFT_V1 baseline
for 2 checkpoints.

## 4. Cleanup

```bash
pkill -f "rl/train.py|prime_rl|vllm|torchrun|wandb|compile_worker" || true
for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader | tr -d " " | grep -E "^[0-9]+$" || true); do
  kill -9 "$p" 2>/dev/null || true
done
nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader
```

GPU box billed hourly — stop it when idle (`vastai stop instance <id>`).

## Lessons (why the pipeline is shaped this way)

- **RL can't install a behavior the policy never samples.** Two stop-targeted
  variants regressed full eval: RLVR_V1 (stacked-penalty reward, 52→20) and
  RLVR_B (corrected bounded reward **+** `--terminal-on-success` horizon
  truncation, 52→19). B changes two things at once, so it's *not* a clean reward
  control — it only shows the most aggressive credit trick for stopping still
  collapses. The real evidence is a **direct measurement**: train prompts emit ~0
  churn (temp-0: 0 churn; temp-0.8 depth≥3: 0/16). Churn is an OOD tail of the
  *held-out* set, not in the rollouts → no gradient, regardless of reward or
  truncation. The termination gap is an **SFT-coverage** problem, not an RL one.
- **So RL's real job here is solve-rate on the partial-solve band** — where
  rollout variance (some pass, some fail) actually exists. Hence the pass@k gate.
- **Reward: verifier-dominant + bounded.** RLVR_V1 collapsed on stacked −13..−23
  penalties with no positive path; the fix is sparse +8-on-success, format floor,
  no stacking. Termination tails zeroed for this run (off-target).
