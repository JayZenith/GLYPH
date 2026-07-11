#!/usr/bin/env python3
"""Reproduce the dense run-1 48-case never-solved taxonomy from raw traces."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
try:
    from .public_artifacts import resolve
except ImportError:
    from public_artifacts import resolve


DEFAULT_INPUT = (
    Path(__file__).resolve().parent.parent
    / "glyph_results/RLVR_VFINAL_STEP10/evals/passk8_heldout150.json"
)


def passed_tests(trace: str) -> int:
    counts = [int(value) for value in re.findall(r"test result: FAILED\. (\d+) passed", trace)]
    counts.extend(
        len(re.findall(r"^test .* \.\.\. ok$", block, re.MULTILINE))
        for block in trace.split("RESULT ")
    )
    return max(counts, default=0)


def reached_compiler_or_runtime(trace: str) -> bool:
    return bool(
        re.search(r"Finished [`'](?:test|dev)`,? profile", trace)
        or re.search(r"CALL cargo_run ", trace)
        or re.search(r"test result: (?:ok|FAILED)", trace)
    )


def classify(row: dict) -> dict:
    best_tests = max((passed_tests(rollout["trace"]) for rollout in row["rollouts"]), default=0)
    reached = any(reached_compiler_or_runtime(rollout["trace"]) for rollout in row["rollouts"])
    return {
        "name": row["name"],
        "classification": "partial_test_credit" if best_tests > 0 else "compiled_or_ran_zero_credit",
        "best_tests_passed": best_tests,
        "reached_compiler_or_runtime": reached,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = resolve(
        args.input,
        "RLVR_VFINAL_STEP10/evals/passk8_heldout150.json",
    )
    rows = json.loads(source.read_text())
    never = [classify(row) for row in rows if row["cargo_solves"] == 0]
    counts = {
        label: sum(row["classification"] == label for row in never)
        for label in ("compiled_or_ran_zero_credit", "partial_test_credit")
    }
    summary = {
        "source": str(source),
        "never_solved": len(never),
        "counts": counts,
        "all_reached_compiler_or_runtime": all(row["reached_compiler_or_runtime"] for row in never),
        "cases": never,
    }
    assert len(never) == 48
    assert counts == {"compiled_or_ran_zero_credit": 20, "partial_test_credit": 28}
    assert summary["all_reached_compiler_or_runtime"]
    rendered = json.dumps(summary, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
