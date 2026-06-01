# RLVR on SFT_V1

Goal: RL-teach the one remaining gap — **stop with one `FINAL` after a successful
verifier**. SFT_V1 already solves (terminal 68/69); RL only fixes stopping.
Reward is minimal and success-anchored (see `rl/task_trace.py` / `rl/RLVR_NOTES.md`):

```text
verifier passed                       +8
passed AND one FINAL, no tools after  +3
tool used after success (churn)       -3   <- the failure
hit max tool rounds                   -2
one FINAL / missing FINAL            +1 / -2
```

Base = SFT_V1 (not V2/V3 — they over-recover, which RL would have to unteach).

## 1. Install

```bash
git clone https://github.com/JayZenith/glyph.git
cd glyph
bash rl/setup/install_prime_rl.sh
source /workspace/prime-rl-src/.venv/bin/activate
```

Note: this currently uses the pinned PRIME-RL path in `install_prime_rl.sh` plus an external frozen-teacher server. Migrating to newer native `num_teacher_gpus` should be done on an instance and tested end-to-end, not half-migrated locally.

## 2. Build RL prompts

Variable-depth prompts (from signal_v2) so rollouts actually go deep, where the
stop failure happens. Already committed as `rl_prompts_v2_1323.jsonl`; rebuild with:

```bash
python3 synthetic_data/build_rl_prompts.py \
  --data synthetic_data/signal_v2_1323.jsonl \
  --output synthetic_data/rl_prompts_v2_1323.jsonl
```

## 3. Run RLVR (2-GPU)

Use `rl/scripts/launch_rlvr_v2.sh`, or directly:

```bash
mkdir -p outputs/rlvr_v2/logs
nohup env \
  HF_HOME=/workspace/.hf_home CARGO_HOME=$HOME/.cargo RUSTUP_HOME=$HOME/.rustup \
  PATH=/workspace/prime-rl-src/.venv/bin:$HOME/.cargo/bin:$PATH \
  PYTHONPATH=/workspace/glyph:/workspace/glyph/rl \
  /workspace/prime-rl-src/.venv/bin/python rl/train.py \
    --model JayZenith/SFT_V1 \
    --teacher-model JayZenith/SFT_V1 --teacher-device 0 --teacher-tau 0.2 \
    --prime-rl-gpu-ids 2,3 --num-infer-gpus 1 --num-train-gpus 1 --gpus-per-node 2 \
    --data synthetic_data/rl_prompts_v2_1323.jsonl \
    --output outputs/rlvr_v2 \
    --max-steps 200 --batch-size 24 --rollouts-per-example 8 \
    --seq-len 5120 --max-model-len 12288 --teacher-max-model-len 12288 \
    --max-completion-tokens 1536 --learning-rate 5e-7 --weight-decay 0.01 \
    --checkpoint-interval 25 --temperature 0.8 \
    --gpu-memory-utilization 0.70 --teacher-gpu-memory-utilization 0.50 \
    --max-tool-rounds 15 --tool-timeout 30 --port 8010 --teacher-port 8011 \
    > outputs/rlvr_v2/logs/launcher.log 2>&1 < /dev/null &
```

Key settings and why: `teacher-tau 0.2` (anchor hard to SFT — 0.01 collapsed the
first run), `rollouts-per-example 8` + `temperature 0.8` (within-group variance;
4 / 0.6 starved the gradient), `zero_advantage` filter enforced in
`rl/configs/task_trace/orchestrator.toml`.

Logs: `tail -f outputs/rlvr_v2/logs/{launcher,orchestrator,trainer}.log`

## 4. Gate every checkpoint (separate 1-GPU box)

Eval needs 1 GPU; the RL box is multi-GPU and blocks while evaling — run the
watcher elsewhere. Fast smoke set (12 prompts, includes the prior failures) per
checkpoint:

```bash
nohup env HF_HOME=/workspace/.hf_home CUDA_VISIBLE_DEVICES=0 PYTHONPATH=/workspace/glyph \
  /workspace/prime-rl-src/.venv/bin/python rl/scripts/watch_canary_eval.py \
  --weights-root outputs/rlvr_v2/weights \
  --output-dir outputs/rlvr_v2/canary_eval \
  --train-data synthetic_data/signal_1062.jsonl \
  --prompt-file sft/evals/eval_prompts_smoke_12.yaml --prompt-section post_eval_smoke_12 \
  --cases-root runs/rlvr1/rust_cases/eval_canary --interval-seconds 60 \
  > outputs/rlvr_v2/logs/smoke_eval.log 2>&1 < /dev/null &
```

Watch per checkpoint: clean_end_rate, final_after_last_tool, terminal_tool_success,
tool-calls-after-success, max-rounds-hit. **Early-stop** — the best checkpoint is
usually early (~step 25); 25→50→75 regressed in every prior run.

## 5. Full held-out eval (best 2–3 checkpoints only)

```bash
python -m sft.eval_formal \
  --sft-model outputs/rlvr_v2/weights/step_25 \
  --train-data synthetic_data/signal_1062.jsonl \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml --prompt-section post_eval_heldout_69 \
  --output results/RLVR_V2/eval_formal_heldout_69.json \
  --max-new-tokens 4000 --max-tool-rounds 15 \
  --cases-root runs/rlvr1/rust_cases/eval_heldout_69
```

**Success bar: beat SFT_V1's 52/69** (clean_end 0.75). Kill if clean_end or
terminal_tool_success drops below SFT_V1 for 2 consecutive checkpoints — that's
the collapse signature.

## 6. Cleanup

```bash
pkill -f "rl/train.py|prime_rl|vllm|torchrun|wandb|compile_worker" || true
for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader | tr -d " " | grep -E "^[0-9]+$" || true); do
  kill -9 "$p" 2>/dev/null || true
done
nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader
```
