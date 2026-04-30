#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from transformers import AutoTokenizer

from validator import validate_trace


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--model", default="Qwen/Qwen3-4B-Base")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--allow-warnings", action="store_true")
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    input_path = Path(args.input)
    output_path = Path(args.output)

    rows = [json.loads(line) for line in input_path.read_text().splitlines() if line.strip()]
    kept = []
    stats = {
        "total": len(rows),
        "kept": 0,
        "dropped_invalid": 0,
        "dropped_warnings": 0,
        "dropped_too_long": 0,
    }

    for row in rows:
        trace = row["trace"]
        validation = validate_trace(trace)
        if not validation.valid:
            stats["dropped_invalid"] += 1
            continue
        if validation.warnings and not args.allow_warnings:
            stats["dropped_warnings"] += 1
            continue
        token_count = len(tokenizer(trace, truncation=False, add_special_tokens=True)["input_ids"])
        if token_count > args.max_tokens:
            stats["dropped_too_long"] += 1
            continue
        kept.append({"trace": trace})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        for row in kept:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    stats["kept"] = len(kept)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
