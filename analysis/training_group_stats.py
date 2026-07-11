#!/usr/bin/env python3
"""Reproduce saved training-group reward-resolution statistics.

"No-Cargo-success" matches the exact branch where `_progress_reward` applies.
Only complete groups of eight are counted. The script separately asks whether
the configured shaping component itself varies, rather than attributing
variance from the base penalty table to shaping.
"""
from __future__ import annotations

import glob
import itertools
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_runtime.protocol import parse_calls
from agent_runtime.rust.executor import ExecutionResult
from rl.reward import _progress_reward


ARMS = {
    "sparse": (
        "glyph_results/RLVR_POOL_B_V8_STEP*/rollouts_step_*/train_rollouts.jsonl",
        {"progress_compile_bonus": 0.0, "progress_test_frac_bonus": 0.0, "progress_error_ladder_bonus": 0.0},
    ),
    "dense": (
        "glyph_results/RLVR_VFINAL_STEP*/rollouts_step_*/train_rollouts.jsonl",
        {"progress_compile_bonus": 0.5, "progress_test_frac_bonus": 2.0, "progress_error_ladder_bonus": 0.0},
    ),
    "compiler": (
        "glyph_results/RLVR_VFINAL2_STEP10/run_default/rollouts/step_*/train_rollouts.jsonl",
        {"progress_compile_bonus": 0.0, "progress_test_frac_bonus": 0.0, "progress_error_ladder_bonus": 2.5},
    ),
}


def rollout_facts(row: dict, config: dict) -> tuple[bool, float]:
    calls = []
    results: dict[str, ExecutionResult] = {}
    for message in row["completion"]:
        content = str(message.get("content", ""))
        if message.get("role") == "assistant":
            calls.extend(parse_calls(content))
        elif message.get("role") == "tool":
            match = re.match(r"RESULT ([^:]+):\nstatus: (success|failed)(.*)", content, re.DOTALL)
            if not match:
                continue
            body = match.group(3)
            stdout = re.search(r"\nstdout:\n(.*?)(?=\nstderr:|\Z)", body, re.DOTALL)
            stderr = re.search(r"\nstderr:\n(.*)", body, re.DOTALL)
            success = match.group(2) == "success"
            results[match.group(1)] = ExecutionResult(
                success,
                stdout.group(1) if stdout else "",
                stderr.group(1) if stderr else "",
                0 if success else 1,
            )
    cargo_success = any(
        call.tool in {"cargo_test", "cargo_run"}
        and call.id in results
        and results[call.id].success
        for call in calls
    )
    return cargo_success, _progress_reward(calls, results, config)


def main() -> int:
    summary = {}
    for arm, (pattern, config) in ARMS.items():
        files = sorted(glob.glob(str(ROOT / pattern)))
        groups = []
        incomplete = 0
        for path in files:
            rows = [json.loads(line) for line in open(path) if line.strip()]
            for _, grouped in itertools.groupby(rows, key=lambda row: row["example_id"]):
                group = list(grouped)
                if len(group) != 8:
                    incomplete += 1
                    continue
                groups.append(group)
        no_cargo = []
        for group in groups:
            facts = [rollout_facts(row, config) for row in group]
            if not any(cargo_success for cargo_success, _ in facts):
                no_cargo.append(facts)
        shaping_varies = sum(
            len({round(progress, 9) for _, progress in facts}) > 1 for facts in no_cargo
        )
        dropped = sum(all(row.get("is_filtered") for row in group) for group in groups)
        summary[arm] = {
            "files": len(files),
            "complete_groups": len(groups),
            "incomplete_groups_excluded": incomplete,
            "no_cargo_success_groups": len(no_cargo),
            "groups_where_shaping_itself_varies": shaping_varies,
            "fully_filtered_groups": dropped,
        }
    assert summary["dense"]["no_cargo_success_groups"] == 7
    assert summary["dense"]["groups_where_shaping_itself_varies"] == 1
    assert summary["compiler"]["no_cargo_success_groups"] == 8
    assert summary["compiler"]["groups_where_shaping_itself_varies"] == 5
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
