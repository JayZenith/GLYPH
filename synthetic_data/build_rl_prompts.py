#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_runtime.rust.results import parse_call_blocks


def prompt_prefix(trace: str) -> str:
    marker = "<|im_start|>assistant"
    if marker not in trace:
        raise ValueError("trace missing first assistant marker")
    return trace.split(marker, 1)[0] + marker + "\n"


def build_row(item: dict, blueprint_root: Path, trace_prefix_root: str) -> dict:
    trace = item["trace"]
    calls = parse_call_blocks(trace)
    if not calls:
        raise ValueError(f"no calls found for case_id={item.get('case_id')}")

    case_id = item["case_id"]
    first = calls[0]
    return {
        "prompt": prompt_prefix(trace),
        "kind": item.get("family"),
        "case_id": case_id,
        "difficulty": item.get("difficulty"),
        "expected_tool": first["tool"],
        "expected_args": first["params"],
        "expected_tool_sequence": item.get("expected_tool_sequence") or [call["tool"] for call in calls],
        "expected_output": item.get("expected_output"),
        "blueprint_root": str(blueprint_root / case_id),
        "trace_prefix": f"{trace_prefix_root.rstrip('/')}/{case_id}",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RL prompt rows from validated SFT traces.")
    parser.add_argument("--data", type=Path, default=Path("synthetic_data/signal_v3_rl_pool_b.jsonl"))
    parser.add_argument("--blueprint-root", type=Path, default=Path("synthetic_data/blueprints"))
    parser.add_argument("--trace-prefix-root", default="runs/rlvr1/rust_cases")
    parser.add_argument("--output", type=Path, default=Path("synthetic_data/rl_prompts_signal_v3_pool_b.jsonl"))
    args = parser.parse_args()

    rows = []
    with args.data.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rows.append(build_row(json.loads(line), args.blueprint_root, args.trace_prefix_root))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(rows)} RL prompts to {args.output}")


if __name__ == "__main__":
    main()
