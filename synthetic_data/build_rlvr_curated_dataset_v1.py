#!/usr/bin/env python3
"""Build a curated RL-only SFT dataset from the clean seed/top-up files.

This intentionally drops the broad mixed corpus and keeps only the traces that
match the RL tool-use patterns we actually want to reinforce.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    ROOT / "synthetic_data" / "rlvr_seed_termination_hardening_v1.jsonl",
    ROOT / "synthetic_data" / "rlvr_seed_single_tool_hardening_v1.jsonl",
    ROOT / "synthetic_data" / "rlvr_seed_single_tool_hardening_v2.jsonl",
]
PROMPTS_FILE = ROOT / "sft" / "evals" / "prompts_125.yaml"
OUT = ROOT / "synthetic_data" / "final_glyph_sft_dataset_rlvr_curated_v1.jsonl"
REPORT = ROOT / "synthetic_data" / "final_glyph_sft_dataset_rlvr_curated_v1_report.json"

USER_RE = re.compile(r"<\|im_start\|>user\nuser「(.*?)」🏷 usr1", re.DOTALL)
CALL_TOOL_RE = re.compile(r"call\s*↦\s*\{[^}]*?\btool\s*↦\s*([^\s•}]+)", re.DOTALL)


def load_rows() -> list[dict]:
    rows: list[dict] = []
    for path in SOURCES:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def extract_user(trace: str) -> str:
    match = USER_RE.search(trace)
    if not match:
        raise ValueError("missing user segment")
    return match.group(1)


def load_formal_eval_rl_users() -> set[str]:
    obj = yaml.safe_load(PROMPTS_FILE.read_text(encoding="utf-8"))
    formal = {row["name"]: row["user"] for row in obj["formal_eval"]}
    spec = obj["formal_eval_rl"]
    return {formal[name] for name in spec["names"]}


def main() -> None:
    rows = load_rows()
    exact_seen: set[str] = set()
    user_seen: set[str] = set()
    kept: list[dict] = []
    removed_exact = 0
    removed_user = 0

    for row in rows:
        key = json.dumps(row, ensure_ascii=False, sort_keys=True)
        if key in exact_seen:
            removed_exact += 1
            continue
        exact_seen.add(key)

        user = extract_user(row["trace"])
        if user in user_seen:
            removed_user += 1
            continue
        user_seen.add(user)
        kept.append(row)

    seq_counts = Counter()
    for row in kept:
        seq = tuple(tool.strip('"') for tool in CALL_TOOL_RE.findall(row["trace"]))
        seq_counts[" -> ".join(seq)] += 1

    eval_overlap = sorted(load_formal_eval_rl_users().intersection(user_seen))

    with OUT.open("w", encoding="utf-8") as fh:
        for row in kept:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    report = {
        "source_files": [str(path.relative_to(ROOT)) for path in SOURCES],
        "source_rows": len(rows),
        "output_rows": len(kept),
        "removed_exact_duplicate_rows": removed_exact,
        "removed_duplicate_user_rows": removed_user,
        "unique_users": len(user_seen),
        "formal_eval_rl_exact_user_overlap": len(eval_overlap),
        "tool_sequences": dict(sorted(seq_counts.items())),
        "output_file": str(OUT.relative_to(ROOT)),
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
