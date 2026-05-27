#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_runtime.protocol import (
    SEG_RE,
    assistant_text,
    ended_cleanly_after_final,
    extract_result_ids,
    final_count,
    parse_calls,
    tool_text,
)
from agent_runtime.rust.executor import create_executor
from agent_runtime.rust.results import parse_call_blocks
from agent_runtime.rust.runtime import execute_rust_tool, rewrite_params_for_sandbox

CANONICAL_FAMILIES = (
    "patch_test_pass",
    "patch_run_pass",
    "patch_test_recover",
    "patch_run_recover",
    "test_only",
    "run_only",
)
LEGACY_FAMILY_MAP = {
    "patch_test_recover_once": "patch_test_recover",
    "patch_test_recover_twice": "patch_test_recover",
    "patch_run_recover_once": "patch_run_recover",
    "patch_run_recover_twice": "patch_run_recover",
}
REQUIRED_METADATA = ("family", "case_id", "difficulty", "expected_tool_sequence", "expected_output")
STATUS_RE = re.compile(r"^status:\s*(\w+)", re.MULTILINE)
RESULT_BODY_RE = re.compile(r"RESULT\s+([A-Za-z0-9_\-]+):\n(.*?)(?=\n<\|im_end\|>|\Z)", re.DOTALL)
PATH_RE = re.compile(r"runs/rlvr1/rust_cases/([^/\"\s)]+)")


def normalize_family(family: str | None) -> str | None:
    if family is None:
        return None
    return LEGACY_FAMILY_MAP.get(family, family)


def family_sequence_is_valid(family: str, sequence: list[str]) -> bool:
    if family == "patch_test_pass":
        return sequence == ["read_file", "apply_patch", "cargo_test"]
    if family == "patch_run_pass":
        return sequence == ["read_file", "apply_patch", "cargo_run"]
    if family == "patch_test_recover":
        return (
            len(sequence) >= 6
            and len(sequence) % 3 == 0
            and sequence == ["read_file", "apply_patch", "cargo_test"] * (len(sequence) // 3)
        )
    if family == "patch_run_recover":
        return (
            len(sequence) >= 6
            and len(sequence) % 3 == 0
            and sequence == ["read_file", "apply_patch", "cargo_run"] * (len(sequence) // 3)
        )
    if family == "test_only":
        return sequence == ["cargo_test"]
    if family == "run_only":
        return sequence == ["cargo_run"]
    return False


def _error(errors: list[str], line_no: int, message: str) -> None:
    errors.append(f"line {line_no}: {message}")


def _result_bodies(trace: str) -> dict[str, str]:
    return {m.group(1): m.group(2).strip() for m in RESULT_BODY_RE.finditer(trace)}


def _statuses_for_tool(trace: str, tool_name: str) -> list[str]:
    calls = parse_calls(assistant_text(trace))
    bodies = _result_bodies(trace)
    statuses: list[str] = []
    for call in calls:
        if call.tool != tool_name:
            continue
        match = STATUS_RE.search(bodies.get(call.id, ""))
        statuses.append(match.group(1) if match else "missing")
    return statuses


def _valid_recover_statuses(statuses: list[str]) -> bool:
    return len(statuses) >= 2 and statuses[-1] == "success" and all(status == "failed" for status in statuses[:-1])


def _case_name_from_trace(trace: str) -> str | None:
    for call in parse_call_blocks(assistant_text(trace)):
        for value in call["params"].values():
            if not isinstance(value, str):
                continue
            match = PATH_RE.search(value)
            if match:
                return match.group(1).rstrip(".,:;")
    match = PATH_RE.search(trace)
    return match.group(1).rstrip(".,:;") if match else None


def _prepare_case_workspace(trace: str, source_root: Path, cases_root: Path) -> tuple[str | None, str | None, str | None]:
    case_name = _case_name_from_trace(trace)
    if not case_name:
        return None, None, None
    trace_prefix = f"runs/rlvr1/rust_cases/{case_name}"
    blueprint = source_root / case_name
    sandbox = cases_root / case_name
    if not blueprint.exists():
        return trace_prefix, str(blueprint), None
    if sandbox.exists():
        shutil.rmtree(sandbox)
    sandbox.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(blueprint, sandbox)
    return trace_prefix, str(blueprint), str(sandbox)


def validate_row(obj: dict, line_no: int, require_metadata: bool, max_chars: int | None) -> list[str]:
    errors: list[str] = []
    trace = obj.get("trace")
    if not isinstance(trace, str) or not trace.strip():
        return [f"line {line_no}: missing string trace"]

    if max_chars is not None and len(trace) > max_chars:
        _error(errors, line_no, f"trace has {len(trace)} chars > max_chars={max_chars}")

    segments = SEG_RE.findall(trace)
    roles = [role for role, _ in segments]
    if not segments:
        _error(errors, line_no, "no chat segments found")
    if roles[:2] != ["system", "user"]:
        _error(errors, line_no, f"first roles are {roles[:2]}, expected ['system', 'user']")
    if roles and roles[-1] != "assistant":
        _error(errors, line_no, "last segment is not assistant")

    assistant = assistant_text(trace)
    tools = tool_text(trace)
    calls = parse_calls(assistant)
    call_ids = [call.id for call in calls]
    result_ids = extract_result_ids(tools)
    expected_ids = [f"c{i}" for i in range(1, len(call_ids) + 1)]
    if call_ids != expected_ids:
        _error(errors, line_no, f"call ids {call_ids} != {expected_ids}")
    if result_ids != call_ids:
        _error(errors, line_no, f"result ids {result_ids} != call ids {call_ids}")
    if final_count(assistant) != 1:
        _error(errors, line_no, f"final_count={final_count(assistant)}, expected 1")
    if not ended_cleanly_after_final(assistant):
        _error(errors, line_no, "assistant does not end cleanly after FINAL")

    family = normalize_family(obj.get("family"))
    expected_sequence = obj.get("expected_tool_sequence")
    actual_sequence = [call.tool for call in calls]

    if require_metadata:
        for key in REQUIRED_METADATA:
            if key not in obj:
                _error(errors, line_no, f"missing metadata field {key}")
    if family is not None and family not in CANONICAL_FAMILIES:
        _error(errors, line_no, f"unknown family {family!r}")
    if family in CANONICAL_FAMILIES:
        if expected_sequence != actual_sequence:
            _error(errors, line_no, f"metadata expected_tool_sequence {expected_sequence} != actual tool sequence {actual_sequence}")
        if not family_sequence_is_valid(family, actual_sequence):
            _error(errors, line_no, f"actual tool sequence {actual_sequence} is invalid for family {family}")
        if family == "patch_test_recover":
            statuses = _statuses_for_tool(trace, "cargo_test")
            if not _valid_recover_statuses(statuses):
                _error(errors, line_no, f"{family} statuses for cargo_test are {statuses}, expected one or more failures then success")
        if family == "patch_run_recover":
            statuses = _statuses_for_tool(trace, "cargo_run")
            if not _valid_recover_statuses(statuses):
                _error(errors, line_no, f"{family} statuses for cargo_run are {statuses}, expected one or more failures then success")

    return errors


def _status_from_body(body: str) -> str | None:
    match = STATUS_RE.search(body)
    return match.group(1) if match else None


def _stdout_from_body(body: str) -> str:
    match = re.search(r"stdout:\n(.*?)(?:\nstderr:|\Z)", body, re.DOTALL)
    return match.group(1).strip() if match else ""


def replay_row(obj: dict, line_no: int, source_root: Path, cases_root: Path, timeout: int) -> list[str]:
    errors: list[str] = []
    trace = obj.get("trace")
    if not isinstance(trace, str):
        return errors
    trace_prefix, blueprint, sandbox = _prepare_case_workspace(trace, source_root, cases_root)
    if blueprint and sandbox is None:
        return [f"line {line_no}: blueprint case not found: {blueprint}"]

    expected_results = _result_bodies(trace)
    executor = create_executor(timeout=timeout)
    actual_statuses: list[tuple[str, str]] = []
    for call in parse_call_blocks(assistant_text(trace)):
        params = call["params"]
        if trace_prefix and sandbox:
            params = rewrite_params_for_sandbox(params, trace_prefix, sandbox)
        result = execute_rust_tool(
            executor,
            call["tool"],
            params,
            expected_output=obj.get("expected_output") if call["tool"] == "cargo_run" else None,
        )
        expected_body = expected_results.get(call["id"], "")
        expected_status = _status_from_body(expected_body)
        actual_status = "success" if result.success else "failed"
        if expected_status != actual_status:
            _error(errors, line_no, f"replay status mismatch for {call['id']} {call['tool']}: trace={expected_status} actual={actual_status}")
        if call["tool"] == "read_file" and result.stdout.strip() != _stdout_from_body(expected_body):
            _error(errors, line_no, f"replay read_file stdout mismatch for {call['id']}")
        if call["tool"] == "cargo_run" and result.stdout.strip() != _stdout_from_body(expected_body):
            _error(errors, line_no, f"replay cargo_run stdout mismatch for {call['id']}")
        if call["tool"] == "apply_patch" and actual_status != "success":
            _error(errors, line_no, f"apply_patch replay failed for {call['id']}: {result.stderr[:200]}")
        actual_statuses.append((call["tool"], actual_status))

    if actual_statuses and actual_statuses[-1][1] != "success":
        _error(errors, line_no, f"final tool {actual_statuses[-1][0]} replayed as {actual_statuses[-1][1]}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and replay CALL/RESULT/FINAL synthetic trace JSONL.")
    parser.add_argument("data", type=Path)
    parser.add_argument("--cases-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=ROOT / "runs" / "rlvr1" / "rust_cases")
    parser.add_argument("--require-metadata", action="store_true")
    parser.add_argument("--max-chars", type=int, default=None)
    parser.add_argument("--tool-timeout", type=int, default=30)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    families: Counter[str] = Counter()
    rows: list[tuple[int, dict]] = []
    with args.data.open(encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_no}: invalid json: {exc}")
                continue
            rows.append((line_no, obj))
            family = normalize_family(obj.get("family"))
            if family:
                families[family] += 1
            errors.extend(validate_row(obj, line_no, args.require_metadata, args.max_chars))

    if not errors:
        if args.cases_root.exists():
            shutil.rmtree(args.cases_root)
        args.cases_root.mkdir(parents=True, exist_ok=True)
        for line_no, obj in rows:
            errors.extend(replay_row(obj, line_no, args.source_root, args.cases_root, args.tool_timeout))

    if args.summary:
        print(json.dumps({"rows": len(rows), "families": dict(sorted(families.items()))}, indent=2))
    if errors:
        for error in errors[:50]:
            print(error)
        if len(errors) > 50:
            print(f"... {len(errors) - 50} more errors")
        return 1
    print(f"ok: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
