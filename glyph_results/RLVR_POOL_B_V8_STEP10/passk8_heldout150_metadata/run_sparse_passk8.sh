#!/usr/bin/env bash
set -euo pipefail
cd /workspace/GLYPH
source .venv/bin/activate
ROOT="results/RLVR_POOL_B_V8_STEP10/passk8_heldout150_reruns"
mkdir -p "$ROOT/logs"
{
  echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "git_commit=$(git rev-parse HEAD)"
  echo "git_status_short_begin"
  git status --short
  echo "git_status_short_end"
  echo "python=$(python --version 2>&1)"
  python -c 'import importlib.metadata as m
for n in ["torch","transformers","vllm","peft","accelerate","datasets","huggingface_hub","verifiers"]:
    try:
        print(f"{n}=={m.version(n)}")
    except Exception as e:
        print(f"{n}=UNAVAILABLE({type(e).__name__})")'
  python -c 'from huggingface_hub import HfApi
for repo in ["Qwen/Qwen3-4B-Base","JayZenith/SFT_HALF_A_V8","JayZenith/RLVR_VFINAL_STEP10","JayZenith/RLVR_POOL_B_V8_STEP10"]:
    info=HfApi().model_info(repo)
    print(f"hf_model_revision {repo} {info.sha} {info.last_modified}")'
  python -c 'from huggingface_hub import hf_hub_download
import json
repo="JayZenith/RLVR_POOL_B_V8_STEP10"
p=hf_hub_download(repo,"adapter_config.json")
cfg=json.load(open(p))
print(f"sparse_adapter_config_path={p}")
print(f"sparse_adapter_r={cfg.get("r")}")
print(f"sparse_adapter_lora_alpha={cfg.get("lora_alpha")}")
print(f"sparse_adapter_base={cfg.get("base_model_name_or_path")}")'
  python -c 'from sft.evals import load_prompts
ps=load_prompts("post_eval_heldout_150", "sft/evals/eval_prompts_heldout_150.yaml")
print(f"prompt_count={len(ps)}")
print("prompt_file=sft/evals/eval_prompts_heldout_150.yaml")
print("prompt_section=post_eval_heldout_150")'
} > "$ROOT/environment.txt" 2>&1

cat > "$ROOT/parity_source_command.txt" <<EOF
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
EOF

for run in run1 run2 run3; do
  cases="runs/passk8_heldout150_rlvr_pool_b_v8_step10_${run}"
  output="results/RLVR_POOL_B_V8_STEP10/passk8_heldout150_${run}.json"
  cmdfile="$ROOT/command_${run}.txt"
  cat > "$cmdfile" <<EOF
CUDA_VISIBLE_DEVICES=0 python -m sft.passk_scan_vllm \\
  --sft-model JayZenith/SFT_HALF_A_V8 \\
  --sft-adapter JayZenith/RLVR_POOL_B_V8_STEP10 \\
  --max-lora-rank 64 \\
  --prompt-file sft/evals/eval_prompts_heldout_150.yaml \\
  --prompt-section post_eval_heldout_150 \\
  --cases-root ${cases} \\
  -k 8 \\
  --temperature 0.8 \\
  --max-new-tokens 4000 \\
  --max-tool-rounds 20 \\
  --output ${output} \\
  --gpu-memory-utilization 0.90 \\
  --max-model-len 24576 \\
  --prompt-batch-size 8 \\
  --save-rollouts
EOF
  echo "START ${run} $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$ROOT/logs/${run}.log"
  CUDA_VISIBLE_DEVICES=0 python -m sft.passk_scan_vllm \
    --sft-model JayZenith/SFT_HALF_A_V8 \
    --sft-adapter JayZenith/RLVR_POOL_B_V8_STEP10 \
    --max-lora-rank 64 \
    --prompt-file sft/evals/eval_prompts_heldout_150.yaml \
    --prompt-section post_eval_heldout_150 \
    --cases-root "$cases" \
    -k 8 \
    --temperature 0.8 \
    --max-new-tokens 4000 \
    --max-tool-rounds 20 \
    --output "$output" \
    --gpu-memory-utilization 0.90 \
    --max-model-len 24576 \
    --prompt-batch-size 8 \
    --save-rollouts 2>&1 | tee -a "$ROOT/logs/${run}.log"
  status=${PIPESTATUS[0]}
  echo "END ${run} status=${status} $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$ROOT/logs/${run}.log"
  if [[ $status -ne 0 ]]; then exit "$status"; fi
  python -c 'import json, sys, pathlib
run=sys.argv[1]; output=pathlib.Path(sys.argv[2]); rows=json.loads(output.read_text())
valid=sum(1 for r in rows if r.get("valid_trace_solves",0)>0)
cargo=sum(1 for r in rows if r.get("cargo_solves",0)>0)
rollouts=sum(len(r.get("rollouts",[])) for r in rows)
print(f"{run}\toutput={output}\tprompts={len(rows)}\tvalid@8={valid}\tcargo@8={cargo}\trollouts={rollouts}")' "$run" "$output" | tee "$ROOT/summary_${run}.txt"
done
python -c 'import json, pathlib
root=pathlib.Path("results/RLVR_POOL_B_V8_STEP10/passk8_heldout150_reruns")
for run in ["run1","run2","run3"]:
    p=pathlib.Path(f"results/RLVR_POOL_B_V8_STEP10/passk8_heldout150_{run}.json")
    rows=json.loads(p.read_text())
    valid=sum(1 for r in rows if r.get("valid_trace_solves",0)>0)
    cargo=sum(1 for r in rows if r.get("cargo_solves",0)>0)
    print(f"{run}: valid@8={valid}/150 cargo@8={cargo}/150 output={p}")' | tee "$ROOT/final_summary.txt"
