# Glyph

A verifiable-reward **RL environment + eval suite** for a Rust tool-use coding
agent (Qwen3-4B). The model emits `CALL tool {...}` blocks, tools execute against
real Rust crates via cargo, and it must finish with a clean `FINAL`. Built on
`verifiers` / PRIME-RL — `rl/task_trace.py` exposes
`load_environment() -> vf.Environment`.

Full write-up (deployed): <https://jayzenith.github.io/glyph/> (source:
[`blog/index.html`](blog/index.html)).

## Results (held-out 150 unseen crates)

Strict `valid_trace` = terminal cargo success + one clean `FINAL` after it +
exact `CALL` syntax + no tool use after success.

| model | greedy pass@1 | pass@8 (3 seeds) |
| --- | ---: | ---: |
| SFT_HALF_A_V8 (base) | 74/150 | 97.3 (95, 97, 100) |
| + sparse-reward RLVR | 72/150 (flat) | — |
| + dense-reward RLVR (step 10) | — | **101.0** (102, 102, 99) |

Sparse binary reward is flat at pass@1 and gives no gradient on the hard tail
(all-fail rollout groups → zero advantage → filtered). A dense partial-credit
reward (compile + test-pass fraction) restores it: **+3.7 pass@8** (97.3 →
101.0), small but reproducible across 3 seeds (seed-level t-test p ≈ 0.06; a
single run showed +7, which replication revealed was seed noise). Greedy pass@1
is too noisy for an effect this size, so the dense comparison uses pass@8 with
seed replication. See the [write-up](https://jayzenith.github.io/glyph/) for the
full diagnosis.

Artifacts: `JayZenith/SFT_HALF_A_V8` · dense adapters
`JayZenith/RLVR_VFINAL_STEP{10,20,30}` · sparse baseline
`JayZenith/RLVR_POOL_B_V8_STEP{10,20,30}`.

## Hardware

Run on vast.ai (NVIDIA RTX PRO 6000 Blackwell, 96 GB each):

- **RLVR:** 4 GPUs — 2 trainer, 1 student inference, 1 auto-launched teacher.
- **Eval:** 1 GPU (vLLM).
- **Disk:** the per-rollout cargo sandboxes are large — a pass@8 run over 150
  crates writes ~20 GB, and they accumulate across runs (I filled a 200 GB disk).
  Clear `runs/` between eval runs.

## GPU Setup

```bash
git clone https://github.com/JayZenith/glyph.git
cd glyph
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

## RLVR Train (dense reward)

Runs on 4 GPUs. PRIME-RL launches the frozen teacher itself
(`--num-teacher-gpus 1`) and wires `orchestrator.teacher` to it — no manual
teacher server. The dense partial-credit reward is enabled by
`--progress-compile-bonus` / `--progress-test-frac-bonus`; omit both for the
sparse baseline.

```bash
python rl/train.py \
  --model JayZenith/SFT_HALF_A_V8 \
  --teacher-model JayZenith/SFT_HALF_A_V8 \
  --lora-rank 64 \
  --lora-alpha 128 \
  --lora-dropout 0.0 \
  --lora-name glyph-signal-v4002-pool-b-dense-r64-a128 \
  --data synthetic_data/rl_prompts_signal_v3_pool_b_mixed_oversampled.jsonl \
  --output outputs/RLVR_SIGNAL_V4002_POOL_B_DENSE_LORA_R64_A128 \
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
  --progress-compile-bonus 0.5 \
  --progress-test-frac-bonus 2.0
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

Greedy pass@1 is too noisy for a small effect; pass@8 with seed replication is
the honest bar. `--max-model-len 24576` gives headroom for tool-accumulated
context at T=0.8 (16384 overflows on long recovery rollouts).

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

For seed replication, rerun with a different `--cases-root` / `--output` per seed
and compare mean valid@8 across seeds.
