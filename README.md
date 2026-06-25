# Glyph

Repository: <https://github.com/JayZenith/glyph>

Readable blog version: [blog/index.html](blog/index.html)

Glyph is a Rust tool-use agent experiment.

The model emits `CALL tool {...}` blocks, tools execute against real Rust crates,
and the model should stop with a clean `FINAL`. The final result is not an RLVR
win. SFT built the strongest aggregate agent; RLVR changed the sampled
distribution but did not improve held-out prompt-level reliability.

## Final Status

Strict success is `valid_trace`: terminal `cargo_test`/`cargo_run` success,
clean `FINAL` after that verifier success, exact CALL syntax, and no extra
tool use after success.

| Model / checkpoint | Held-out-69 greedy `valid_trace` | Notes |
| --- | ---: | --- |
| `SFT_V1` | 52/69 | Best broad SFT result |
| `SFT_V2` | 48/69 | More recovery data, worse broad reliability |
| `SFT_V3` | 50/69 | More hard-tail capability, no broad improvement |
| `SFT_HALF_A` | 51/69 | Clean split baseline |
| `RLVR_V1000` step 25 direct merge | 50/69 | One SFT miss gained, two SFT solves lost |
| `RLVR_V999_STEP5` adapter | 46/69 | Clean adapter eval, regressed |
| `RLVR_V999_STEP10` adapter | 45/69 | Clean adapter eval, regressed |

Held-out-69 pass@4, SFT vs `RLVR_V999_STEP10`:

| Metric | `SFT_HALF_A` | `RLVR_V999_STEP10` |
| --- | ---: | ---: |
| Prompt-level valid pass@4 | 59/69 | 59/69 |
| Valid rollouts | 185/276 | 190/276 |
| 4/4 stable prompts | 31/69 | 35/69 |

Conclusion: RLVR did not improve prompt-level held-out reliability. The rollout-level
shift (+5/276) is within sampling noise (sigma ~8), and gains and losses offset at
pass@4. The one reproducible effect was negative: run_only FINAL-hygiene drift caused
by kind imbalance in the RL pool.

Decomposition: greedy cargo-only success was roughly preserved (SFT 51/69,
step 5 51/69, step 10 50/69). The larger strict drop came from final-answer
hygiene on the drifted run_only cases. The main diagnosed failure was training
coverage for that kind, not malformed export or lost Rust tool-use ability.

## Data

The clean experiment split `synthetic_data/signal_v3.jsonl` into deterministic,
non-overlapping halves grouped by case id.

| File | Purpose | Size |
| --- | --- | ---: |
| `synthetic_data/signal_v3_sft_half_a.jsonl` | SFT traces | 1,042 rows, 762 unique cases |
| `synthetic_data/signal_v3_rl_pool_b.jsonl` | RL trace pool | 1,041 rows, 760 unique cases |
| `synthetic_data/rl_prompts_signal_v3_pool_b.jsonl` | RL prompt manifest for `rl/train.py` | 760 prompts |
| `synthetic_data/rl_prompts_signal_v3_pool_b_mixed.jsonl` | mixed-outcome RL prompt subset used for V999/V4000 | 703 prompts |
| `synthetic_data/signal_v3_rl_pool_b_prompts.yaml` | pass@k-compatible prompt manifest | 760 prompts |
| `synthetic_data/signal_v3_split_summary.json` | split audit | summary |
| `synthetic_data/signal_v3_split_summary.md` | split audit | summary |

Leakage checks:

```text
case_id_overlap = 0
trace_overlap = 0
```

Important: RL training uses the prompt manifest:

```text
synthetic_data/rl_prompts_signal_v3_pool_b*.jsonl
```

Do not pass the SFT trace JSONL directly to `rl/train.py`.

## SFT Reproduction

### 1. Setup

```bash
git clone https://github.com/JayZenith/glyph.git
cd glyph
git pull --ff-only

bash sft/setup/install_sft_env.sh
source .venv/bin/activate
```

The SFT/eval environment installs Torch, Transformers, PEFT, Rust tooling, and
vLLM for batched formal eval/pass@k scans.

### 2. Train `SFT_HALF_A`

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

Observed artifact:

```text
JayZenith/SFT_HALF_A
JayZenith/SFT_HALF_A_DATASET
```

### 3. Greedy Held-Out Eval

```bash
mkdir -p results/SFT_HALF_A

python -m sft.eval_formal \
  --sft-model runs/SIGNAL_v3_HALF_A_SFT_E3_LR2E5/final \
  --train-data synthetic_data/signal_v3_sft_half_a.jsonl \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
  --prompt-section post_eval_heldout_69 \
  --cases-root runs/heldout69_sft_half_a \
  --output results/SFT_HALF_A/eval_formal_heldout_69.json \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --prompt-batch-size 4 \
  --tool-workers 8
```

Result:

```text
SFT_HALF_A strict held-out-69 valid_trace = 51/69
```

`--max-new-tokens 4000` is the per-assistant-turn generation cap. The full trace
can span multiple assistant turns up to `--max-tool-rounds`.

## RLVR Reproduction

### 1. Setup

RLVR used a 4-GPU node:

```text
GPU 0: student inference
GPU 1,2: trainer
GPU 3: external teacher inference
```

Install:

```bash
git clone https://github.com/JayZenith/glyph.git
cd glyph
git pull --ff-only

PRIME_RL_ENABLE_LORA=1 bash rl/setup/install_prime_rl.sh
source /workspace/prime-rl-src/.venv/bin/activate
```

### 2. Final RLVR Run Actually Used: V999/V4000

This was the final cleaner run: LoRA only, SFT teacher anchor, mixed RL pool,
strict reward top score only for held-out-style clean verifier success.

Start the frozen teacher endpoint separately on GPU 3 before launching RL:

```bash
CUDA_VISIBLE_DEVICES=3 inference --model.name JayZenith/SFT_HALF_A --server.port 8001
```

```bash
python rl/train.py \
  --model JayZenith/SFT_HALF_A \
  --teacher-model JayZenith/SFT_HALF_A \
  --lora-rank 64 \
  --lora-alpha 128 \
  --lora-dropout 0.0 \
  --lora-name glyph-signal-v4000-pool-b-mixed-r64-a128 \
  --data synthetic_data/rl_prompts_signal_v3_pool_b_mixed.jsonl \
  --output outputs/RLVR_SIGNAL_V4000_POOL_B_MIXED_LORA_R64_A128 \
  --max-steps 30 \
  --batch-size 96 \
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
  --verifier-success-clean-final-bonus 10 \
  --verifier-success-bonus 0 \
  --final-once-bonus 0 \
  --structure-valid-bonus 0 \
  --no-call-penalty 0 \
  --malformed-call-penalty 0 \
  --bad-cargo-project-path-penalty 0 \
  --bad-final-hygiene-penalty 0 \
  --tool-budget-exhausted-penalty 0 \
  --missing-final-penalty 0 \
  --tool-after-success-penalty 0 \
  --failed-verifier-penalty 0 \
  --max-failed-verifier-penalty 0 \
  --activation-checkpointing \
  --fused-lm-head-token-chunk-size auto \
  --gpu-memory-utilization 0.70 \
  --prime-rl-gpu-ids 0,1,2 \
  --num-infer-gpus 1 \
  --num-train-gpus 2 \
  --gpus-per-node 3 \
  --port 8000 \
  --teacher-port 8001 \
  --enforce-gibberish-filter \
  --enforce-repetition-filter
```

Published adapters:

```text
JayZenith/RLVR_V999_STEP5
JayZenith/RLVR_V999_STEP10
```

### 3. Export Checkpoints

Use the broadcast adapter, not `weights/step_N`.

```bash
python rl/scripts/export_prime_lora_adapter.py \
  --base-model JayZenith/SFT_HALF_A \
  --adapter-dir outputs/RLVR_SIGNAL_V4000_POOL_B_MIXED_LORA_R64_A128/run_default/broadcasts/step_10 \
  --output outputs/RLVR_SIGNAL_V4000_POOL_B_MIXED_LORA_R64_A128/adapter_step_10

huggingface-cli upload JayZenith/RLVR_V999_STEP10 \
  outputs/RLVR_SIGNAL_V4000_POOL_B_MIXED_LORA_R64_A128/adapter_step_10 .
```

The export must contain:

```text
adapter_config.json
adapter_model.safetensors
prime_lora_adapter_export.json
```

### 4. Greedy Held-Out Eval for RLVR Adapters

```bash
mkdir -p results/RLVR_V999_STEP5

python -m sft.eval_formal \
  --sft-model JayZenith/SFT_HALF_A \
  --sft-adapter JayZenith/RLVR_V999_STEP5 \
  --train-data synthetic_data/signal_v3_sft_half_a.jsonl \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
  --prompt-section post_eval_heldout_69 \
  --cases-root runs/heldout69_rlvr_v999_step5_rounds20 \
  --output results/RLVR_V999_STEP5/eval_formal_heldout_69_maxrounds20.json \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --prompt-batch-size 8 \
  --tool-workers 16
```

For step 10, change only `--sft-adapter`, `--cases-root`, and `--output`.

Results:

```text
SFT_HALF_A:        51/69
RLVR_V999_STEP5:  46/69
RLVR_V999_STEP10: 45/69
```

Both adapters kept exact CALL syntax at `1.0`, so these regressions were not the
old malformed-export failure.

### 5. Held-Out-69 pass@4 Diagnostic

This was the final decisive sampled eval. It used vLLM batching on one 98 GB GPU
with `k=4`, `prompt_batch_size=8`, effective generation batch `32`, and separate
isolated Rust crate environments per rollout.

Base:

```bash
python -m sft.passk_scan_vllm \
  --sft-model JayZenith/SFT_HALF_A \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
  --prompt-section post_eval_heldout_69 \
  --cases-root runs/passk_heldout69_sft_half_a_k4 \
  -k 4 \
  --temperature 0.8 \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --output results/passk_heldout69/SFT_HALF_A_k4.json \
  --gpu-memory-utilization 0.88 \
  --max-model-len 16384 \
  --prompt-batch-size 8 \
  --save-rollouts
```

Adapter:

```bash
python -m sft.passk_scan_vllm \
  --sft-model JayZenith/SFT_HALF_A \
  --sft-adapter JayZenith/RLVR_V999_STEP10 \
  --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
  --prompt-section post_eval_heldout_69 \
  --cases-root runs/passk_heldout69_rlvr_v999_step10_k4 \
  -k 4 \
  --temperature 0.8 \
  --max-new-tokens 4000 \
  --max-tool-rounds 20 \
  --output results/passk_heldout69/RLVR_V999_STEP10_k4.json \
  --gpu-memory-utilization 0.88 \
  --max-model-len 16384 \
  --max-lora-rank 64 \
  --prompt-batch-size 8 \
  --save-rollouts
```

Results are in the Final Status table above. Prompt-level gains:

```text
eval100_014_patch_test_pass_015_layered_config_env_does_not_override_explicit_file
eval100_035_patch_test_recover_001_record_line_parse_validate_recover
eval100_039_patch_test_recover_005_select_event_codes_partial_then_full_fix
```

Prompt-level losses:

```text
eval100_037_patch_test_recover_003_weekly_region_summary_recover
eval100_097_run_only_003_department_expense_summary_report
eval100_099_run_only_005_filter_map_inventory_restock_report
```

## Known Traps

Do not use `weights/step_N` as the official RLVR artifact. It is a trainer
checkpoint, not the served policy. Use `run_default/broadcasts/step_N` and export
a PEFT adapter.

Do not claim success from loose terminal-tool success. Use strict `valid_trace`.

Do not change the tool protocol between SFT, RL, and eval. The model was trained
on the literal ChatML-style `CALL` / `RESULT` format.

Do not compare evals with different budgets. The reported held-out results here
used `--max-tool-rounds 20` and `--max-new-tokens 4000`.

## Artifact Pointers

Local artifacts:

```text
new_results/SFT_HALF_A/eval_formal_heldout_69.json
new_results/RLVR_V999STEP5/eval/eval_formal_heldout_69_maxrounds20.json
new_results/RLVR_V999STEP10/eval/eval_formal_heldout_69_maxrounds20.json
new_results/passk_heldout69_v999_step10/SFT_HALF_A_k4.json
new_results/passk_heldout69_v999_step10/RLVR_V999_STEP10_k4.json
new_results/passk_heldout69_v999_step10/passk_heldout69_v999_step10_vs_sft.log
blog/finalized_blogv3.md
```

Hugging Face:

```text
JayZenith/SFT_HALF_A
JayZenith/SFT_HALF_A_DATASET
JayZenith/RLVR_V999_STEP5
JayZenith/RLVR_V999_STEP10
```

## Final Takeaway

SFT made a real Rust tool-use agent. RLVR produced case-level movement and a
small cargo-solving pass@4 uptick, but not a held-out win: strict pass@4 was
flat and greedy strict held-out regressed. The main engineering lesson is that
verifier RL is only meaningful when reward, protocol, checkpoint export, data
coverage, and eval all enforce the same whole-trace contract.
