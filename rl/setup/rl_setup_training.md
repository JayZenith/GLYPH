# RLVR on SFT_V1

Goal: run PRIME-RL on `JayZenith/SFT_V1` with real Rust tool execution and frozen-teacher KL anchoring.

## 1. Install

```bash
git clone https://github.com/JayZenith/glyph.git
cd glyph
bash rl/setup/install_prime_rl.sh
source /workspace/prime-rl-src/.venv/bin/activate
```

Note: this currently uses the pinned PRIME-RL path in `install_prime_rl.sh` plus an external frozen-teacher server. Migrating to newer native `num_teacher_gpus` should be done on an instance and tested end-to-end, not half-migrated locally.

## 2. Build RL Prompts

```bash
python3 synthetic_data/build_rl_prompts.py \
  --data synthetic_data/signal_1062.jsonl \
  --blueprint-root synthetic_data/blueprints \
  --output synthetic_data/rl_prompts_1062.jsonl
```

## 3. Run

Recommended multi-GPU run:

```bash
  cd /workspace/glyph
  mkdir -p outputs/rlvr1/logs

  nohup env \
  HF_HOME=/workspace/.hf_home \
    CARGO_HOME=$HOME/.cargo \
    RUSTUP_HOME=$HOME/.rustup \   
    PATH=/workspace/prime-rl-src/.venv/bin:$HOME/.cargo/bin:$PATH \
    PYTHONPATH=/workspace/glyph:/workspace/glyph/rl \
    /workspace/prime-rl-src/.venv/bin/python rl/train.py \
      --model JayZenith/SFT_V1 \
      --teacher-model JayZenith/SFT_V1 \
      --teacher-device 0 \
      --teacher-tau 0.01 \
      --prime-rl-gpu-ids 2,3 \
      --num-infer-gpus 1 \
      --num-train-gpus 1 \
      --gpus-per-node 2 \
      --data synthetic_data/rl_prompts_1062.jsonl \
      --output outputs/rlvr_penalty_runpod \
      --max-steps 200 \
      --batch-size 24 \ 
      --rollouts-per-example 8 \
      --seq-len 5120 \
      --max-model-len 12288 \
      --teacher-max-model-len 12288 \
      --max-completion-tokens 1536 \
      --learning-rate 5e-7 \
      --weight-decay 0.01 \
      --checkpoint-interval 1000 \
      --temperature 0.8 \
      --gpu-memory-utilization 0.70 \
      --teacher-gpu-memory-utilization 0.50 \
      --max-tool-rounds 15 \
      --tool-timeout 30 \
      --port 8010 \
      --teacher-port 8011
    > outputs/rlvr1/logs/launcher.log 2>&1 < /dev/null &

```

Or use the wrapper:

```bash
bash rl/setup/run_task_trace_2xa100.sh
```

## 4. Monitor
```bash
mkdir -p results/RLVR1
scp -P 12886 root@23.127.144.217:/workspace/glyph/outputs/rlvr1/run_default/
rollouts/step_5/train_rollouts.jsonl results/RLVR1/step_5_train_rollouts.jsonl

```

```bash
python3 rl/scripts/inspect_rollouts.py outputs/rlvr1
python3 rl/scripts/live_rollout_viewer.py outputs/rlvr1 --port 8090
```

## 5. Cleanup

```bash
bash rl/setup/cleanup_rl_processes.sh /workspace/glyph/outputs/ /workspace/glyph/outputs/rlvr1
```
