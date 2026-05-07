#!/usr/bin/env bash
# Full data pipeline: synthesize → postprocess → patch → filter.
# Re-creates the shape of synthetic_data/sft_train_1098_official.jsonl.
#
# NOTE: the EXACT flags used to build the existing dataset are not recorded
# (see synthetic_data/data_manifest.json). The values below are sensible
# defaults based on TraceGenerator's class signature; rebuilding will give a
# new dataset with similar properties, not a byte-identical copy.
#
# Usage (from repo root):
#   OPENAI_API_KEY=... ./data/build.sh [run_name] [count]

set -euo pipefail

RUN_NAME="${1:-run_$(date +%Y%m%d_%H%M)}"
COUNT="${2:-1000}"
MODEL="${MODEL:-gpt-5-mini}"
OUT_DIR="synthetic_data/${RUN_NAME}"

mkdir -p "$OUT_DIR"
echo "==> $RUN_NAME — generating $COUNT traces with $MODEL"

# 1. Synthesize. Validator runs inline; bad traces are rejected.
python data/generate.py \
    --count "$COUNT" \
    --model "$MODEL" \
    --output "$OUT_DIR/raw.jsonl" \
    --concurrency 5 \
    --error-rate 0.2 \
    --no-tools-rate 0.2 \
    --follow-up-rate 0.3 \
    --retries 3

# 2. Postprocess: merge sequential think/act blocks, wrap with chat-template tokens.
python data/postprocess.py "$OUT_DIR/raw.jsonl" \
    --output "$OUT_DIR/processed.jsonl" \
    --token-style qwen3

# 3. Patch: fix recoverable bugs (missing 🏷 tags, unclosed 」, trailing junk).
python data/patch_dataset.py \
    --input "$OUT_DIR/processed.jsonl" \
    --output "$OUT_DIR/patched.jsonl"

# 4. Filter: drop anything still failing the validator.
python data/filter_dataset.py "$OUT_DIR/patched.jsonl" "$OUT_DIR/sft_train.jsonl"

# 5. Diversity audit (sanity check, doesn't modify).
python data/audit_diversity.py --data "$OUT_DIR/sft_train.jsonl"

echo "==> done. Final dataset: $OUT_DIR/sft_train.jsonl"
wc -l "$OUT_DIR"/*.jsonl
