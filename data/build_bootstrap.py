#!/usr/bin/env python3
"""Bootstrap stage of the synthesis pipeline. Run: python -m data.build_bootstrap"""
import argparse
import json
from pathlib import Path

from transformers import AutoTokenizer

from core.validator import validate_trace


def keep_trace(trace: str, token_count: int, max_tokens: int, max_acts: int) -> tuple[bool, str]:
    result = validate_trace(trace)
    if not result.valid:
        return False, "invalid"
    if result.warnings:
        return False, "warnings"
    if token_count > max_tokens:
        return False, "too_long"
    if trace.count("user「") != 1:
        return False, "multi_turn"
    if trace.count("response「") != 1:
        return False, "bad_response_count"
    if trace.count("plan {") != 1:
        return False, "bad_plan_count"
    if trace.count("act {") > max_acts or trace.count("result {") > max_acts:
        return False, "too_many_steps"
    if "łazienk" in trace or "permission ↦" in trace:
        return False, "junk_tail"
    return True, "kept"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--model", default="Qwen/Qwen3-4B-Base")
    parser.add_argument("--max-tokens", type=int, default=3584)
    parser.add_argument("--max-acts", type=int, default=5)
    args = parser.parse_args()

    rows = [json.loads(line) for line in Path(args.input).read_text().splitlines() if line.strip()]
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)

    kept = []
    stats: dict[str, int] = {}
    for row in rows:
        trace = row["trace"]
        token_count = len(tokenizer(trace, truncation=False, add_special_tokens=True)["input_ids"])
        ok, reason = keep_trace(trace, token_count, args.max_tokens, args.max_acts)
        stats[reason] = stats.get(reason, 0) + 1
        if ok:
            kept.append({"trace": trace})

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for row in kept:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(json.dumps({
        "input": len(rows),
        "kept": len(kept),
        "max_tokens": args.max_tokens,
        "max_acts": args.max_acts,
        "stats": stats,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
