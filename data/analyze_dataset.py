#!/usr/bin/env python3
"""Dupe + validator-pass-rate audit. Run: python -m data.analyze_dataset FILE"""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from core.validator import validate_trace


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="replace")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", type=Path)
    ap.add_argument("--max-errors", type=int, default=10)
    args = ap.parse_args()

    total = 0
    valid = 0
    dupes = 0
    seen = set()

    char_lens = []
    has_think = 0
    has_trunc = 0
    has_response = 0
    any_warnings = 0
    severe_warnings = 0

    err_counter = Counter()
    warn_counter = Counter()
    sample_bad = []

    with args.jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                obj = json.loads(line)
            except Exception:
                err_counter["json_parse_error"] += 1
                continue

            trace = obj.get("trace")
            if not isinstance(trace, str):
                err_counter["missing_trace_str"] += 1
                continue

            h = _sha1(trace)
            if h in seen:
                dupes += 1
            else:
                seen.add(h)

            char_lens.append(len(trace))
            if "<think>" in trace or "</think>" in trace:
                has_think += 1
            if "tokens truncated" in trace or "truncated" in trace:
                has_trunc += 1
            if "response「" in trace:
                has_response += 1

            v = validate_trace(trace)
            if v.valid:
                valid += 1
            else:
                if len(sample_bad) < args.max_errors:
                    sample_bad.append(v.errors[:])
                for e in v.errors:
                    err_counter[e] += 1

            for w in v.warnings:
                warn_counter[w] += 1
            if v.warnings:
                any_warnings += 1
            if any(
                w.startswith("References to undefined tags:")
                or w.startswith("Unsatisfied todo items:")
                or w.startswith("Satisfaction markers for undefined todos:")
                for w in v.warnings
            ):
                severe_warnings += 1

    def pct(n: int) -> str:
        return "0.0%" if total == 0 else f"{(100.0 * n / total):.1f}%"

    print(f"file={args.jsonl}")
    print(f"records={total} valid={valid} ({pct(valid)}) dupes={dupes} ({pct(dupes)})")
    if char_lens:
        char_lens_sorted = sorted(char_lens)
        p50 = char_lens_sorted[len(char_lens_sorted) // 2]
        p90 = char_lens_sorted[int(len(char_lens_sorted) * 0.9)]
        print(f"trace_chars: min={min(char_lens)} p50={p50} p90={p90} max={max(char_lens)}")
    print(f"contains_<think>={has_think} ({pct(has_think)})")
    print(f"contains_trunc_marker={has_trunc} ({pct(has_trunc)})")
    print(f"contains_response_block={has_response} ({pct(has_response)})")
    print(f"has_any_warnings={any_warnings} ({pct(any_warnings)})")
    print(f"has_severe_warnings={severe_warnings} ({pct(severe_warnings)})")

    if err_counter:
        print("\nTop errors:")
        for k, v in err_counter.most_common(10):
            print(f"- {k}: {v}")
    if warn_counter:
        print("\nTop warnings:")
        for k, v in warn_counter.most_common(10):
            print(f"- {k}: {v}")

    if sample_bad:
        print("\nSample invalid error lists:")
        for i, errs in enumerate(sample_bad, 1):
            print(f"- {i}: {errs}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
