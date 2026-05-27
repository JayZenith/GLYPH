#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_runtime.rust.executor import create_executor
from agent_runtime.rust.runtime import execute_rust_tool
from sft.evals.prompt_loader import assert_no_prompt_overlap, load_prompts
from sft.evals.real_cases import materialize_case

FAMILY_SEQUENCES = {
    "patch_test_pass": ["read_file", "apply_patch", "cargo_test"],
    "patch_run_pass": ["read_file", "apply_patch", "cargo_run"],
    "patch_test_recover_once": ["read_file", "apply_patch", "cargo_test", "read_file", "apply_patch", "cargo_test"],
    "patch_run_recover_once": ["read_file", "apply_patch", "cargo_run", "read_file", "apply_patch", "cargo_run"],
    "patch_test_recover_twice": ["read_file", "apply_patch", "cargo_test", "read_file", "apply_patch", "cargo_test", "read_file", "apply_patch", "cargo_test"],
    "patch_run_recover_twice": ["read_file", "apply_patch", "cargo_run", "read_file", "apply_patch", "cargo_run", "read_file", "apply_patch", "cargo_run"],
    "test_only": ["cargo_test"],
    "run_only": ["cargo_run"],
    "read_only": ["read_file"],
}

REQUIRED_FIELDS = (
    "name",
    "kind",
    "real_case_name",
    "user_template",
    "expected_tool_sequence",
    "case_id",
    "difficulty",
    "expected_output",
)


def _src(project: Path, file_name: str) -> str:
    return str(project / "src" / file_name)


def golden_calls(case_name: str, project: Path) -> list[tuple[str, dict]]:
    if case_name == "patch_test_pass_sumswap":
        return [
            ("read_file", {"file_path": _src(project, "lib.rs")}),
            ("apply_patch", {"file_path": _src(project, "lib.rs"), "find": "a - b", "replace": "a + b"}),
            ("cargo_test", {"project_path": str(project)}),
        ]
    if case_name == "patch_run_pass_welcome":
        return [
            ("read_file", {"file_path": _src(project, "main.rs")}),
            ("apply_patch", {"file_path": _src(project, "main.rs"), "find": "Welcom", "replace": "Welcome"}),
            ("cargo_run", {"project_path": str(project)}),
        ]
    if case_name == "patch_test_recover_once_triangle":
        return [
            ("read_file", {"file_path": _src(project, "lib.rs")}),
            ("apply_patch", {"file_path": _src(project, "lib.rs"), "find": "1..n", "replace": "1..=n-1"}),
            ("cargo_test", {"project_path": str(project)}),
            ("read_file", {"file_path": _src(project, "lib.rs")}),
            ("apply_patch", {"file_path": _src(project, "lib.rs"), "find": "1..=n-1", "replace": "1..=n"}),
            ("cargo_test", {"project_path": str(project)}),
        ]
    if case_name == "patch_run_recover_once_banner":
        return [
            ("read_file", {"file_path": _src(project, "main.rs")}),
            ("apply_patch", {"file_path": _src(project, "main.rs"), "find": "ready", "replace": "Ready"}),
            ("cargo_run", {"project_path": str(project)}),
            ("read_file", {"file_path": _src(project, "main.rs")}),
            ("apply_patch", {"file_path": _src(project, "main.rs"), "find": "Ready", "replace": "Ready!"}),
            ("cargo_run", {"project_path": str(project)}),
        ]
    if case_name == "patch_test_recover_twice_signed_parse":
        return [
            ("read_file", {"file_path": _src(project, "lib.rs")}),
            ("apply_patch", {"file_path": _src(project, "lib.rs"), "find": "unwrap_or(1)", "replace": "unwrap_or(0)"}),
            ("cargo_test", {"project_path": str(project)}),
            ("read_file", {"file_path": _src(project, "lib.rs")}),
            ("apply_patch", {"file_path": _src(project, "lib.rs"), "find": "s.parse::<u32>()", "replace": "s.trim().parse::<u32>()"}),
            ("cargo_test", {"project_path": str(project)}),
            ("read_file", {"file_path": _src(project, "lib.rs")}),
            ("apply_patch", {"file_path": _src(project, "lib.rs"), "find": "parse::<u32>()", "replace": "parse::<i32>()"}),
            ("cargo_test", {"project_path": str(project)}),
        ]
    if case_name == "patch_run_recover_twice_counter":
        return [
            ("read_file", {"file_path": _src(project, "main.rs")}),
            ("apply_patch", {"file_path": _src(project, "main.rs"), "find": "1..4", "replace": "1..=4"}),
            ("cargo_run", {"project_path": str(project)}),
            ("read_file", {"file_path": _src(project, "main.rs")}),
            ("apply_patch", {"file_path": _src(project, "main.rs"), "find": 'print!("count {n} "', "replace": 'print!("Count: {n} "'}),
            ("cargo_run", {"project_path": str(project)}),
            ("read_file", {"file_path": _src(project, "main.rs")}),
            ("apply_patch", {"file_path": _src(project, "main.rs"), "find": 'print!("Count: {n} "', "replace": 'println!("Count: {n}"'}),
            ("cargo_run", {"project_path": str(project)}),
        ]
    if case_name == "test_only_passing_suite":
        return [("cargo_test", {"project_path": str(project)})]
    if case_name == "run_only_total":
        return [("cargo_run", {"project_path": str(project)})]
    if case_name == "read_only_headline":
        return [("read_file", {"file_path": _src(project, "lib.rs")})]
    raise KeyError(f"No golden calls for {case_name}")


def expected_statuses(kind: str) -> list[str]:
    if kind.endswith("recover_once"):
        return ["success", "success", "failed", "success", "success", "success"]
    if kind.endswith("recover_twice"):
        return ["success", "success", "failed", "success", "success", "failed", "success", "success", "success"]
    return ["success"] * len(FAMILY_SEQUENCES[kind])


def preflight_row(row: dict, cases_root: Path, timeout: int) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in row:
            errors.append(f"{row.get('name', '<unnamed>')}: missing {field}")
    if errors:
        return errors

    name = row["name"]
    kind = row["kind"]
    if kind not in FAMILY_SEQUENCES:
        return [f"{name}: unknown kind {kind!r}"]
    if row["expected_tool_sequence"] != FAMILY_SEQUENCES[kind]:
        errors.append(f"{name}: expected_tool_sequence does not match kind {kind}")

    case = materialize_case(row["real_case_name"], cases_root / name)
    project = Path(case.blueprint_root)
    if row["expected_output"] != case.expected_output:
        errors.append(f"{name}: expected_output metadata != real case expected_output")

    calls = golden_calls(row["real_case_name"], project)
    tools = [tool for tool, _ in calls]
    if tools != row["expected_tool_sequence"]:
        errors.append(f"{name}: golden tools {tools} != expected_tool_sequence {row['expected_tool_sequence']}")
        return errors

    executor = create_executor(timeout=timeout)
    statuses: list[str] = []
    for tool, params in calls:
        result = execute_rust_tool(
            executor,
            tool,
            params,
            expected_output=row["expected_output"] if tool == "cargo_run" else None,
        )
        statuses.append("success" if result.success else "failed")
        if tool == "cargo_run" and statuses[-1] == "success" and row["expected_output"] is not None:
            if result.stdout.strip() != row["expected_output"].strip():
                errors.append(f"{name}: cargo_run stdout mismatch")

    expected = expected_statuses(kind)
    if statuses != expected:
        errors.append(f"{name}: golden statuses {statuses} != expected {expected}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight held-out SFT eval prompts without model inference.")
    parser.add_argument("--prompt-section", default="post_eval")
    parser.add_argument("--prompt-file", default=None)
    parser.add_argument("--train-data", required=True,
                        help="Train JSONL used to reject exact eval/train prompt overlap.")
    parser.add_argument("--cases-root", type=Path, default=Path("runs/eval_preflight_cases"),
                        help="Disposable workspace where eval cases are materialized and mutated.")
    parser.add_argument("--tool-timeout", type=int, default=30)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    rows = load_prompts(args.prompt_section, args.prompt_file)
    render_rows = []
    for row in rows:
        case = materialize_case(row["real_case_name"], args.cases_root / "_overlap" / row["name"])
        rendered = dict(row)
        rendered["user"] = rendered["user_template"].format(project_root=case.blueprint_root)
        render_rows.append(rendered)
    assert_no_prompt_overlap(render_rows, args.train_data)
    shutil.rmtree(args.cases_root / "_overlap", ignore_errors=True)

    if args.cases_root.exists():
        shutil.rmtree(args.cases_root)
    args.cases_root.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    families: Counter[str] = Counter()
    for row in rows:
        families[row.get("kind", "missing")] += 1
        errors.extend(preflight_row(row, args.cases_root, args.tool_timeout))

    if args.summary:
        print(json.dumps({"rows": len(rows), "families": dict(sorted(families.items()))}, indent=2))
    if errors:
        for error in errors[:50]:
            print(error)
        if len(errors) > 50:
            print(f"... {len(errors) - 50} more errors")
        return 1
    print(f"ok: {len(rows)} eval prompts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
