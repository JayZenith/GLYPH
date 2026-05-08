#!/usr/bin/env python3
"""Drop traces that fail the validator. Run: python -m data.filter_dataset IN OUT"""
import argparse
import json
from pathlib import Path

from core.validator import validate_trace


def is_severe_warning(w: str) -> bool:
    return (
        w.startswith("References to undefined tags:")
        or w.startswith("Unsatisfied todo items:")
        or w.startswith("Satisfaction markers for undefined todos:")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("in_jsonl", type=Path)
    ap.add_argument("out_jsonl", type=Path)
    ap.add_argument("--allow-think", action="store_true")
    ap.add_argument("--allow-severe-warnings", action="store_true")
    args = ap.parse_args()

    kept = 0
    total = 0
    with args.in_jsonl.open("r", encoding="utf-8") as fin, args.out_jsonl.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            total += 1
            obj = json.loads(line)
            trace = obj.get("trace", "")
            if not args.allow_think and ("<think>" in trace or "</think>" in trace):
                continue
            v = validate_trace(trace)
            if not v.valid:
                continue
            if not args.allow_severe_warnings and any(is_severe_warning(w) for w in v.warnings):
                continue
            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            kept += 1

    print(f"kept={kept}/{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

