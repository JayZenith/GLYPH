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
0. pass@k scan (pick targets)  ->  results/passk_train134.json
1. freeze rlvr-target band     ->  RL prompt subset (0<pass@k<k only)
2. RLVR (GRPO) on that band
3. measure in-set pass@1 before vs after  <- the artifact
```

## 0. pass@k scan — find the RLVR-addressable band

Candidate set already carved: `runs/rlvr_passk_train150/` (150 mixed-difficulty
train prompts + cases). Trim the 16 depth-1 trivia (pass@k=k, no gradient) →
scan the ~134 depth≥3.

```bash
env HF_HOME=/workspace/.hf_home CUDA_VISIBLE_DEVICES=0 PYTHONPATH=/workspace/glyph \
  /workspace/prime-rl-src/.venv/bin/python sft/passk_scan.py \
    --sft-model JayZenith/SFT_V1 \
    --prompt-file runs/rlvr_passk_train150/prompts.yaml \
    --prompt-section train_passk_scan_134 \
    --cases-root runs/rlvr_passk_train150/cases \
    -k 8 --temperature 0.8 \
    --output results/passk_train134.json
```

Bands by `terminal_tool_success`: `0<solves<k` = **rlvr-target** (gradient exists),
`==k` = solved (no variance), `==0` = capability-gap (RL can't cross).
`passk_train134.json` stores aggregate only — `{name, solves, k, pass_at_k, band}`.
That's all RL needs; GRPO re-samples its own rollouts at train time.

## 1. Freeze the target band → RL prompts

Keep only `band=="rlvr-target"` from `passk_train134.json`. **Build the RL jsonl
directly from the scanned yaml** `runs/rlvr_passk_train150/prompts.yaml`, filtered
to those names — do NOT try to join back to `rl_prompts_v2_1323.jsonl` (different
case_ids and crate paths; the names won't line up). The yaml rows already carry
everything the env needs, so this is just a format conversion.

Each RL row (the schema `rl/train.py --data` reads, one JSON per line):
`prompt` (chatml = system+user+`<|im_start|>assistant\n`), `kind`, `case_id`,
`expected_tool`, `expected_args`, `expected_tool_sequence`, `expected_output`,
`blueprint_root`, `trace_prefix`. All present in the yaml per case (assemble
`prompt` from `system`+`user`; `expected_tool`/`expected_args` = first tool of
`expected_tool_sequence` + its path). Write to
`synthetic_data/rl_prompts_passk_target.jsonl` (small local script). RL ONLY on
this band — solved / capability-gap prompts give zero advantage.

## 2. Install + run RLVR (2-GPU)

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

## 3. Measure — pass@1 before vs after (the artifact)

Gate checkpoints on a **separate 1-GPU box** (the RL box blocks while evaling).
Re-run pass@k on the SAME rlvr-target band, per checkpoint:

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

Report: mean pass@k on the rlvr-target band, SFT_V1 vs each checkpoint. Lift =
the deliverable. Label it **in-set** (no held-out split for v1 — a small
unmatched held-out is noisier than honest in-set numbers).

**Early-stop**: best checkpoint is usually early (~step 25); later checkpoints
regressed in every prior run. **Kill** if pass@k drops below SFT_V1 baseline for
2 checkpoints.

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
