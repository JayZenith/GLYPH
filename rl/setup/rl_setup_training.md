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

Build RL prompts from the SFT_V1 trace dataset. These rows carry model-facing
prompts plus execution metadata for the RL environment: expected first tool,
expected args, blueprint root, trace prefix, expected output, and task kind.

```bash
python3 synthetic_data/build_rl_prompts.py \
  --data synthetic_data/signal_1062.jsonl \
  --blueprint-root synthetic_data/blueprints \
  --output synthetic_data/rl_prompts_1062.jsonl
```

## 3. Run RLVR

Current target: start from `JayZenith/SFT_V1`, keep a frozen `JayZenith/SFT_V1`
teacher for KL, and optimize real tool-use rollouts. The current reward focuses
on the observed held-out failure:

- successful verifier -> exactly one `FINAL`
- successful verifier -> more tools is penalized
- last `RESULT` -> empty assistant/no `FINAL` is penalized
- recovery still gets shaped credit: fail -> read again -> second patch -> pass -> `FINAL`

Recommended 2-GPU run:

```bash
cd /workspace/glyph

mkdir -p outputs/rlvr_final_penalty/logs

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
    --output outputs/rlvr_final_penalty \
    --max-steps 200 \
    --batch-size 24 \
    --rollouts-per-example 8 \
    --seq-len 5120 \
    --max-model-len 12288 \
    --teacher-max-model-len 12288 \
    --max-completion-tokens 1536 \
    --learning-rate 5e-7 \
    --weight-decay 0.01 \
    --checkpoint-interval 25 \
    --temperature 0.8 \
    --gpu-memory-utilization 0.70 \
    --teacher-gpu-memory-utilization 0.50 \
    --max-tool-rounds 15 \
    --tool-timeout 30 \
    --port 8010 \
    --teacher-port 8011 \
    > outputs/rlvr_final_penalty/logs/launcher.log 2>&1 < /dev/null & 
```

Useful logs:

```bash
tail -f outputs/rlvr_final_penalty/logs/launcher.log
tail -f outputs/rlvr_final_penalty/logs/orchestrator.log
tail -f outputs/rlvr_final_penalty/logs/trainer.log
tail -f outputs/rlvr_final_penalty/logs/canary_eval.log
```

## 4. Monitor Rollouts

Rollouts are written under:

```bash
outputs/rlvr_final_penalty/run_default/rollouts/step_N/train_rollouts.jsonl
outputs/rlvr_final_penalty/weights/step_N/
```

Inspect aggregate trajectory health without printing full rollouts:

```bash
python3 reward_golden_tests.py \
  --rollout results/RLVR1/rollouts8/step_0/train_rollouts.jsonl \
  --rollout results/RLVR1/rollouts8/step_50/train_rollouts.jsonl
```

Or inspect a run directory:

```bash
python3 rl/scripts/inspect_rollouts.py outputs/rlvr_final_penalty
python3 rl/scripts/live_rollout_viewer.py outputs/rlvr_final_penalty --port 8090
```

Key collapse checks:

- `% reaching apply_patch`
- `% reaching verifier`
- `% reaching FINAL`
- empty assistant after final `RESULT`
- tool calls after successful verifier
- max tool rounds hit

## 5. Canary Eval During Training

Run a tiny held-out canary whenever a new `weights/step_N` checkpoint appears.
This is not part of PPO reward; it is an external monitor for whether the actual
held-out behavior is changing.

```bash
nohup env \
  HF_HOME=/workspace/.hf_home \
  CUDA_VISIBLE_DEVICES=0 \
  PYTHONPATH=/workspace/glyph \
  /workspace/prime-rl-src/.venv/bin/python rl/scripts/watch_canary_eval.py \
  --weights-root outputs/rlvr_final_penalty/weights \
  --output-dir outputs/rlvr_final_penalty/canary_eval \
  --train-data synthetic_data/signal_1062.jsonl \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
  --prompt-section post_eval_heldout_69 \
  --cases-root runs/rlvr1/rust_cases/eval_canary \
  --interval-seconds 60 \
  > outputs/rlvr_final_penalty/logs/canary_eval.log 2>&1 < /dev/null &
```

The watcher writes one JSON per checkpoint:

```bash
outputs/rlvr_final_penalty/canary_eval/step_25.json
outputs/rlvr_final_penalty/canary_eval/step_50.json
```

Each canary JSON reports:

- valid trace
- has `FINAL`
- empty assistant after `RESULT`
- tool calls after successful verifier
- terminal tool success
- max tool rounds hit

To run the same canary once by hand against the latest checkpoint:

```bash
python3 rl/scripts/canary_eval.py \
  --weights-root outputs/rlvr_final_penalty/weights \
  --train-data synthetic_data/signal_1062.jsonl \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
  --prompt-section post_eval_heldout_69 \
  --output outputs/rlvr_final_penalty/canary_eval/latest.json \
  --cases-root runs/rlvr1/rust_cases/eval_canary
```

## 6. Formal Held-Out Eval

After exporting or uploading a checkpoint, run the same held-out eval used for
SFT_V1. Keep `--train-data synthetic_data/signal_1062.jsonl`; that is the SFT
overlap guard.

```bash
python -m sft.eval_formal \
  --sft-model JayZenith/RLVR_V1 \
  --train-data synthetic_data/signal_1062.jsonl \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
  --prompt-section post_eval_heldout_69 \
  --output results/RLVR_V1/eval_formal_heldout_69.json \
  --max-new-tokens 4000 \
  --max-tool-rounds 15 \
  --cases-root runs/rlvr1/rust_cases/eval_heldout_69
```

The current baseline comparison:

```text
SFT_V1:   52/69 valid, 68/69 terminal success, 17 missing FINAL
RLVR_V1: 51/69 valid, 68/69 terminal success, 18 missing FINAL
```

The current diagnosis is not dirty/multiple final text. It is mostly:

```text
RESULT cN:
status: success
...
<|im_end|>

<|im_start|>assistant
```

Then no `FINAL`, often after the model kept using tools past a successful
`cargo_test`/`cargo_run`.

## 7. Pull Artifacts Locally

```bash
mkdir -p results/RLVR_V1/rollouts results/RLVR_V1/artifacts

rsync -av \
  --include='*/' --include='train_rollouts.jsonl' --exclude='*' \
  -e 'ssh -p PORT' \
  root@HOST:/workspace/glyph/outputs/rlvr_final_penalty/run_default/rollouts/ \
  results/RLVR_V1/rollouts/

find results/RLVR_V1/rollouts -name train_rollouts.jsonl | sort -V | \
  xargs cat > results/RLVR_V1/rlvr_v1_rollouts.jsonl

rsync -av \
  --include='*/' --include='*.toml' --include='*.log' --include='*.wandb' \
  --include='*.json' --exclude='*.safetensors' --exclude='*.bin' --exclude='*' \
  -e 'ssh -p PORT' \
  root@HOST:/workspace/glyph/outputs/rlvr_final_penalty/ \
  results/RLVR_V1/artifacts/
```

## 8. Upload Checkpoint and Dataset

Upload the selected saved model, usually `weights/step_50` or the latest stable
step:

```bash
python - <<'PY'
from huggingface_hub import HfApi

api = HfApi()
api.create_repo("JayZenith/RLVR_V1", repo_type="model", exist_ok=True)
api.upload_folder(
    repo_id="JayZenith/RLVR_V1",
    repo_type="model",
    folder_path="outputs/rlvr_final_penalty/weights/step_50",
    commit_message="Upload RLVR V1 checkpoint",
)

api.create_repo("JayZenith/RLVR_V1_DATASET", repo_type="dataset", exist_ok=True)
api.upload_file(
    repo_id="JayZenith/RLVR_V1_DATASET",
    repo_type="dataset",
    path_or_fileobj="synthetic_data/rl_prompts_1062.jsonl",
    path_in_repo="rl_prompts_1062.jsonl",
    commit_message="Upload RLVR V1 training prompts",
)
PY
```

## 9. Cleanup

```bash
pkill -f "rl/train.py|prime_rl|vllm|torchrun|wandb|compile_worker" || true
for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader | tr -d " " | grep -E "^[0-9]+$" || true); do
  kill -9 "$p" 2>/dev/null || true
done

nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader
```
