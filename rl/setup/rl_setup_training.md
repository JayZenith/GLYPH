# RLVR on GLYPH_SFT (full fine-tune)

Preferred target: 4× 80GB GPUs. Rollout vLLM on GPU 0, frozen teacher vLLM on GPU 1, trainer on GPUs 2-3.

Fallback target: 2× A100 80GB (or 2× H100 80GB / 2× H200). Trainer on GPU 1, rollout vLLM + frozen teacher vLLM on GPU 0.

## 1. Clone

```bash
git clone https://github.com/JayZenith/glyph.git
cd glyph
```

## 2. Install prime-rl + flash-attn + rust + patches

```bash
bash rl/setup/install_prime_rl.sh
source /workspace/prime-rl-src/.venv/bin/activate

```

## 3. Generate Dataset 
```bash
python3 -m rl.rust.prepare_cases \
   --root runs/rlvr1/rust_cases \
   --output runs/rlvr1/prompts.jsonl \
   --phrasings 2 \
   --gold-count 12
```

## 4. Run training

### Preferred 4-GPU KL setup

```bash
HF_HOME=/workspace/.hf_home \
  CARGO_HOME=$HOME/.cargo \
  RUSTUP_HOME=$HOME/.rustup \
  PATH=/workspace/prime-rl-src/.venv/bin:$HOME/.cargo/bin:$PATH \
  PYTHONPATH=/workspace/glyph:/workspace/glyph/rl \
  CUDA_VISIBLE_DEVICES=0,1,2,3 \
  /workspace/prime-rl-src/.venv/bin/python rl/train.py \
    --model JayZenith/GLYPH_SFT \
    --teacher-model JayZenith/GLYPH_SFT \
    --teacher-anchor \
    --teacher-device 1 \
    --teacher-tau 0.01 \
    --prime-rl-gpu-ids 0,2,3 \
    --num-infer-gpus 1 \
    --num-train-gpus 2 \
    --gpus-per-node 3 \
    --data runs/rlvr1/prompts.jsonl \
    --output outputs/rlvr1_4gpu_run1 \
    --max-steps 200 \
    --batch-size 12 \
    --rollouts-per-example 2 \
    --seq-len 5120 \
    --max-model-len 12288 \
    --teacher-max-model-len 12288 \
    --max-completion-tokens 1536 \
    --learning-rate 5e-7 \
    --weight-decay 0.01 \
    --checkpoint-interval 1000 \
    --temperature 0.4 \
    --gpu-memory-utilization 0.70 \
    --teacher-gpu-memory-utilization 0.50 \
    --max-samples 95 \
    --max-trace-chars 50000 \
    --max-tool-rounds 5 \
    --tool-timeout 30 \
    --port 8000 \
    --teacher-port 8001 \
    --clean-tool-boundary-bonus 1.5 \
    --structure-valid-bonus 1.0 \
    --penalty-unbalanced-braces -0.5 \
    --penalty-unbalanced-brackets -0.5 \
    --penalty-unbalanced-special-quotes -0.5 \
    --penalty-garbage-after-final-response -3.0 \
    --penalty-final-response-unclosed -1.25 \
    --penalty-missing-response -1.5 \
    --penalty-undefined-tags -0.4 \
    --penalty-unsatisfied-todos -1.5 \
    --penalty-repetition -1.0 \
    --penalty-tool-calls-without-matching-result -1.0 \
    --penalty-not-ended-cleanly-after-response -3.0 \
    --no-call-penalty -1.25 \
    --any-success-bonus 0.5 \
    --missing-results-penalty -1.0 \
    --response-presence-bonus 0.2 \
    --exact-final-termination-bonus 0.75 \
    --dirty-final-response-reward-cap -5.0 \
    --require-clean-termination-for-success-reward
```

### 2-GPU fallback

```bash
cd /workspace/glyph && mkdir -p outputs/rlvr1_4gpu_run2/logs && nohup env
 \
 HF_HOME=/workspace/.hf_home \
 CARGO_HOME=$HOME/.cargo \
 RUSTUP_HOME=$HOME/.rustup \
 PATH=/workspace/prime-rl-src/.venv/bin:$HOME/.cargo/bin:$PATH \
 PYTHONPATH=/workspace/glyph:/workspace/glyph/rl \
 CUDA_VISIBLE_DEVICES=0,1,2,3 \
 /workspace/prime-rl-src/.venv/bin/python rl/train.py \
   --model JayZenith/GLYPH_SFT \
   --teacher-model JayZenith/GLYPH_SFT \
   --teacher-anchor \
   --teacher-device 1 \
   --teacher-tau 0.01 \
   --prime-rl-gpu-ids 0,2,3 \
   --num-infer-gpus 1 \
   --num-train-gpus 2 \
   --gpus-per-node 3 \
   --data runs/rlvr1/prompts.jsonl \
   --output outputs/rlvr1_4gpu_run2 \
   --max-steps 200 \
   --batch-size 12 \
   --rollouts-per-example 2 \
   --seq-len 5120 \
   --max-model-len 12288 \
   --teacher-max-model-len 12288 \
   --max-completion-tokens 1536 \
   --learning-rate 5e-7 \
   --weight-decay 0.01 \
   --checkpoint-interval 1000 \
   --temperature 0.4 \
   --gpu-memory-utilization 0.70 \
   --teacher-gpu-memory-utilization 0.50 \
   --max-samples 95 \
   --max-trace-chars 50000 \
   --max-tool-rounds 5 \
   --tool-timeout 30 \
   --port 8000 \
   --teacher-port 8001 \
   --clean-tool-boundary-bonus 1.5 \
   --structure-valid-bonus 1.0 \
   --penalty-unbalanced-braces -0.5 \
   --penalty-unbalanced-brackets -0.5 \
   --penalty-unbalanced-special-quotes -0.5 \
   --penalty-garbage-after-final-response -3.0 \
   --penalty-final-response-unclosed -1.25 \
   --penalty-missing-response -1.5 \
   --penalty-undefined-tags -0.4 \
   --penalty-unsatisfied-todos -1.5 \
   --penalty-repetition -1.0 \
   --penalty-tool-calls-without-matching-result -1.0 \
   --penalty-not-ended-cleanly-after-response -3.0 \
   --no-call-penalty -1.25 \
   --any-success-bonus 0.5 \
   --missing-results-penalty -1.0 \
   --response-presence-bonus 0.2 \
   --exact-final-termination-bonus 0.75 \
   --dirty-final-response-reward-cap -5.0 \
   --require-clean-termination-for-success-reward \
   > outputs/rlvr1_4gpu_run2/logs/launcher.log 2>&1 < /dev/null &


```

## Cleanup training commands
```bash
bash rl/setup/cleanup_rl_processes.sh /workspace/glyph/outputs/ /workspace/glyph/outputs/rlvr1_runY
```
