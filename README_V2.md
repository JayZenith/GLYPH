
  Created Files

  - synthetic_data/signal_v3_sft_half_a.jsonl: 1,042 rows, 762 unique cases

  - synthetic_data/signal_v3_rl_pool_b.jsonl: 1,041 rows, 760
    unique cases

  - synthetic_data/rl_prompts_signal_v3_pool_b.jsonl: RL-
    compatible prompt manifest, 760 rows

  - synthetic_data/signal_v3_rl_pool_b_prompts.yaml: pass@k-
    compatible prompt manifest, 760 rows

  - synthetic_data/signal_v3_split_summary.json
  - synthetic_data/signal_v3_split_summary.md

  The split is deterministic, stratified by family, difficulty,
  expected tool-sequence length, and run/test verifier family. I
  grouped by case_id, so duplicate/oversampled traces cannot leak
  across SFT and RL. Checks: case_id_overlap = 0, trace_overlap =
  0.

  Risk Audit
  Main invalidation risk: do not pass synthetic_data/
  signal_v3_rl_pool_b.jsonl directly to rl/train.py. That file is
  SFT trace JSONL. rl/train.py needs prompt rows with prompt,
  expected_tool, blueprint_root, trace_prefix, etc. Use
  synthetic_data/rl_prompts_signal_v3_pool_b.jsonl.

  Reward/eval mostly match but not perfectly. Heldout eval
  requires strict cargo verifier success plus exactly one clean
  final. RL reward strongly rewards first cargo success plus
  clean final, but a rollout can still get positive reward after
  success even if it later churns. Keep --teacher-tau explicit
  and do not use --terminal-on-success for this experiment.

  Zero-advantage filtering is enabled in rl/configs/task_trace/
  orchestrator.toml; your CLI overrides do not disable it.

  One subtle issue: sft/train.py deduplicates exact traces before
  training, so SFT_HALF_A’s 1,042 rows become 762 unique traces
  in practice. That means the old V3-style exact oversampling
  does not actually weight SFT unless you change training code. I
  left code unchanged.

  SFT Command
```bash
  python -m sft.train \
    --model Qwen/Qwen3-4B-Base --tokenizer Qwen/Qwen3-4B-Base \
    --data synthetic_data/signal_v3_sft_half_a.jsonl \
    --output runs/SIGNAL_v3_HALF_A_SFT_E3_LR2E5 \
    --epochs 3 --batch-size 1 --grad-accum 8 --lr 2e-5 \
    --max-seq-length 12000 --no-train-split --gradient-checkpointing
```

EVAL and cmopare RLVR later with same command changing onlu --sft-model and output path
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
  --max-tool-rounds 20
```

Also held out eval is stricter with exactly one clean FINAL after successful cargo_test/cargo_run. RL reward is close but shaped; it give spartial bonuses/penalties. so trust eval_formal.py for final claim, not RL traiing reward. 

  1. RL dataset pass@4
     This tells you whether the RL pool has useful mixed groups for learning. Installed vLLM env on instance /workspace/glyph/.venv-vllm and then ran scan with this interpreter: 

  ```bash
  PYTHONPATH=/workspace/glyph .venv-vllm/bin/python sft/passk_scan_vllm.py \
      --sft-model runs/SIGNAL_v3_HALF_A_SFT_E3_LR2E5/final \
      --prompt-file synthetic_data/signal_v3_rl_pool_b_prompts.yaml \
      --prompt-section rl_pool_b \
      --cases-root runs/passk_signal_v3_rl_pool_b_sft_half_a \
      -k 4 \
      --temperature 0.8 \
      --max-new-tokens 4000 \
      --max-tool-rounds 15 \
      --output results/SFT_HALF_A/passk_rl_pool_b_k4.json \
      --save-rollouts
```

  2. Heldout-69 pass@4
     This diagnoses whether heldout failures have latent
     capability under sampling.

  ```bash
  python sft/passk_scan_vllm.py \
    --sft-model runs/SIGNAL_v3_HALF_A_SFT_E3_LR2E5/final \
    --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
    --prompt-section post_eval_heldout_69 \
    --cases-root runs/passk_heldout69_sft_half_a \
    -k 4 \
    --temperature 0.8 \
    --max-new-tokens 4000 \
    --max-tool-rounds 20 \
    --output results/SFT_HALF_A/passk_heldout69_k4.json \
    --save-rollouts
```


--------------------------------------------------------
  RLVR LoRA Command

```bash
  PRIME_RL_ENABLE_LORA=1 bash rl/setup/install_prime_rl.sh
  source /workspace/prime-rl-src/.venv/bin/activate

  python rl/train.py \
    --model JayZenith/SFT_HALF_A \
    --teacher-model JayZenith/SFT_HALF_A \
    --lora-rank 16 --lora-alpha 32 --lora-dropout 0.0 \
    --lora-name glyph-signal-v3-pool-b-r16-a32 \
    --data synthetic_data/rl_prompts_signal_v3_pool_b.jsonl \
    --output outputs/RLVR_SIGNAL_V3_POOL_B_LORA_R16_A32 \
    --max-steps 100 --batch-size 48 --rollouts-per-example 8 \
    --seq-len 8192 --max-model-len 16384 --teacher-max-model-len 16384 \
    --max-completion-tokens 4000 --learning-rate 5e-7 --weight-decay 0.01 \
    --checkpoint-interval 25 --temperature 0.8 \
    --teacher-tau 0.2 \
    --max-tool-rounds 15 --tool-timeout 30 \
    --activation-checkpointing --fused-lm-head-token-chunk-size auto \
    --gpu-memory-utilization 0.70 --teacher-gpu-memory-utilization 0.50 \
    --prime-rl-gpu-ids 0,1,2 --num-infer-gpus 1 --num-train-gpus 2 \
    --gpus-per-node 3 --port 8000 --teacher-port 8001 --teacher-device 3
```

  RL_POOL_B pass@4 diagnostic

```bash
  python sft/passk_scan_vllm.py \
    --sft-model runs/SIGNAL_v3_HALF_A_SFT_E3_LR2E5/final \
    --prompt-file synthetic_data/signal_v3_rl_pool_b_prompts.yaml
    \
    --prompt-section rl_pool_b \
    --cases-root runs/passk_signal_v3_rl_pool_b/cases \
    -k 4 --temperature 0.8 \
    --max-new-tokens 4000 --max-tool-rounds 15 \
    --output results/passk_signal_v3_rl_pool_b_sft_half_a_k4.json
    \
    --save-rollouts
```

# RL held out EVAL ON RLVR_POOL_B
```bash
mkdir -p results/RLVR_POOL_B

  python -m sft.eval_formal \
    --sft-model JayZenith/RLVR_POOL_B \
    --train-data synthetic_data/signal_v3_sft_half_a_plus_rl_pool_b_traces.jsonl \
    --prompt-file sft/evals/eval_prompts_heldout_69.yaml \
    --prompt-section post_eval_heldout_69 \
    --cases-root runs/heldout69_rlvr_pool_b_step25 \
    --output results/RLVR_POOL_B/eval_formal_heldout_69_step25.json \
    --max-new-tokens 4000 \
    --max-tool-rounds 20



```

  Validation done: schema/protocol checks passed for both split
  JSONLs, RL prompt metadata is complete, and all RL prompt
  blueprint roots exist. I could not run rl/train.py --dry-run in
  the current shell because the active Python lacks tomli_w; that
  should be available inside the PRIME-RL venv.




KEY NOTES:
- rlvr IS LESS STRICT than heldout eval, it rewards cargo success strongly and extra rewards for clean FINAL but not identical to valid_trace. RLVR can improve training reward while not improving or even regressing heldout strict valid_trace. 
- so keep LORA, not full fine tune, keep teacher KL anchored, evaluate checkpoints early, pick checkpoint by heldout-69 valid_trace, not RL reward, do not use --terminal-on-success.

Current reward shapes rewards first verifier success, gives extra reward if FINAL appears after success, but heldout eval requires stricter behavior: successful cargo_test/cargo_run + exactly one clean final + final after last tool.
