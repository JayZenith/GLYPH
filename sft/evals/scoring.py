"""Per-output scoring for the simplified CALL/RESULT/FINAL eval."""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from agent_runtime.protocol import (
    RESULT_ID_RE,
    ROLE_LEAK_RE,
    SEG_RE,
    call_syntax_errors,
    final_hygiene_errors,
    parse_calls,
)
from agent_runtime.rust.results import parse_call_blocks


def _segments(text: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in SEG_RE.finditer(text)]


def _assistant_bodies(full_trace: str) -> list[str]:
    return [body for role, body in _segments(full_trace) if role == "assistant"]


def _tool_bodies(full_trace: str) -> list[str]:
    return [body for role, body in _segments(full_trace) if role == "tool"]


def _extract_calls(assistant_bodies: list[str]) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []
    for body in assistant_bodies:
        calls.extend((call.tool, call.id) for call in parse_calls(body))
    return calls


def _cargo_project_path_errors(calls: list[dict]) -> list[str]:
    errors: list[str] = []
    for call in calls:
        if call["tool"] not in {"cargo_run", "cargo_test"}:
            continue
        project_path = str(call.get("params", {}).get("project_path", ""))
        if re.search(r"/src/(?:main|lib)\.rs$", project_path):
            errors.append(f"{call['id']}: cargo project_path points at source file")
    return errors


def _extract_result_ids(tool_bodies: list[str]) -> list[str]:
    result_ids: list[str] = []
    for body in tool_bodies:
        result_ids.extend(RESULT_ID_RE.findall(body))
    return result_ids


def _extract_result_body(tool_bodies: list[str], call_id: str) -> str | None:
    merged = "\n".join(tool_bodies)
    match = re.search(
        r"RESULT\s+" + re.escape(call_id) + r":\n(.*?)(?=\nRESULT\s+[A-Za-z0-9_\-]+:|\Z)",
        merged,
        re.DOTALL,
    )
    return match.group(1).strip() if match else None


def _tool_succeeded(tool_name: str, result_body: str | None, expected_output: str | None) -> bool:
    if tool_name not in {"cargo_run", "cargo_test"}:
        return False
    if not result_body:
        return False
    if re.search(r"^status:\s*success\b", result_body, re.MULTILINE) is None:
        return False
    if tool_name == "cargo_run" and expected_output is not None:
        stdout_match = re.search(r"stdout:\n(.*?)(?:\nstderr:|\Z)", result_body, re.DOTALL)
        stdout = stdout_match.group(1).strip() if stdout_match else ""
        return stdout == expected_output.strip()
    return True


def _failure_buckets(metrics: dict) -> list[str]:
    buckets: list[str] = []
    if not metrics["has_final"]:
        buckets.append("missing_final")
    if not metrics["clean_end"]:
        buckets.append("dirty_final")
    if not metrics["result_ids_match_call_ids"]:
        buckets.append("wrong_result_mapping")
    if not metrics["all_calls_have_ids"]:
        buckets.append("missing_call_ids")
    if not metrics["exact_call_syntax"]:
        buckets.append("malformed_call_syntax")
    if not metrics["final_hygiene"]:
        buckets.append("bad_final_hygiene")
    if not metrics["cargo_project_paths_valid"]:
        buckets.append("bad_cargo_project_path")
    if metrics["role_marker_leakage"]:
        buckets.append("role_marker_leakage")
    if not metrics["not_truncated"]:
        buckets.append("truncated")
    if not metrics["final_after_last_tool"]:
        buckets.append("final_before_tool_completion")
    if not metrics["terminal_tool_success"]:
        buckets.append("task_failure")
    return buckets


def _expected_sequence_match(kind: str, call_sequence: list[str], expected_tool_sequence: list[str]) -> bool:
    if kind == "patch_test_recover":
        if len(call_sequence) < 3 or len(call_sequence) % 3 != 0:
            return False
        return all(
            call_sequence[i:i + 3] == ["read_file", "apply_patch", "cargo_test"]
            for i in range(0, len(call_sequence), 3)
        )
    if kind == "patch_run_recover":
        if len(call_sequence) < 3 or len(call_sequence) % 3 != 0:
            return False
        return all(
            call_sequence[i:i + 3] == ["read_file", "apply_patch", "cargo_run"]
            for i in range(0, len(call_sequence), 3)
        )
    return call_sequence == expected_tool_sequence


def score_output(
    prompt_text: str,
    output_text: str,
    item: dict,
    new_token_count: int,
    max_new_tokens: int,
) -> dict:
    full_trace = prompt_text + output_text
    assistant_bodies = _assistant_bodies(full_trace)
    tool_bodies = _tool_bodies(full_trace)
    assistant_text = "\n".join(assistant_bodies)
    calls = _extract_calls(assistant_bodies)
    call_sequence = [tool for tool, _ in calls]
    call_ids = [call_id for _, call_id in calls]
    result_ids = _extract_result_ids(tool_bodies)
    parsed_calls = parse_call_blocks(assistant_text)
    syntax_errors = call_syntax_errors(assistant_text)
    final_errors = final_hygiene_errors(assistant_text)
    cargo_path_errors = _cargo_project_path_errors(parsed_calls)
    expected_tool_sequence = item.get("expected_tool_sequence", [])
    kind = item.get("kind", "other")
    final_blocks = [body for body in assistant_bodies if body.strip().startswith("FINAL:")]
    last_assistant = assistant_bodies[-1].strip() if assistant_bodies else ""
    last_call = parsed_calls[-1] if parsed_calls else None
    expected_output = item.get("expected_output")
    terminal_result_body = _extract_result_body(tool_bodies, last_call["id"]) if last_call else None
    terminal_tool_success = (
        _tool_succeeded(last_call["tool"], terminal_result_body, expected_output)
        if last_call else False
    )

    metrics = {
        "kind": item.get("kind", "other"),
        "call_sequence": call_sequence,
        "call_ids": call_ids,
        "result_ids": result_ids,
        "expected_tool_sequence": expected_tool_sequence,
        "has_final": bool(final_blocks),
        "final_count": len(final_blocks),
        "clean_end": bool(assistant_bodies) and last_assistant.startswith("FINAL:"),
        "expected_tool_sequence_exact": _expected_sequence_match(kind, call_sequence, expected_tool_sequence),
        "result_ids_match_call_ids": result_ids == call_ids[: len(result_ids)],
        "all_calls_have_ids": len(call_ids) == len(calls),
        "role_marker_leakage": bool(ROLE_LEAK_RE.search(assistant_text)),
        "exact_call_syntax": not syntax_errors,
        "final_hygiene": not final_errors,
        "cargo_project_paths_valid": not cargo_path_errors,
        "not_truncated": new_token_count < max_new_tokens - 10,
        "terminal_tool_success": terminal_tool_success,
        "new_token_count": new_token_count,
        "assistant_block_count": len(assistant_bodies),
        "tool_block_count": len(tool_bodies),
        "raw_chars": len(output_text),
    }

    if final_blocks:
        last_final_idx = max(i for i, body in enumerate(assistant_bodies) if body.strip().startswith("FINAL:"))
        last_call_idx = max((i for i, body in enumerate(assistant_bodies) if parse_calls(body)), default=-1)
        metrics["final_after_last_tool"] = last_final_idx > last_call_idx
    else:
        metrics["final_after_last_tool"] = False

    metrics["valid_trace"] = (
        metrics["has_final"]
        and metrics["final_count"] == 1
        and metrics["clean_end"]
        and metrics["result_ids_match_call_ids"]
        and metrics["all_calls_have_ids"]
        and metrics["exact_call_syntax"]
        and metrics["final_hygiene"]
        and metrics["cargo_project_paths_valid"]
        and metrics["final_after_last_tool"]
        and metrics["terminal_tool_success"]
        and not metrics["role_marker_leakage"]
    )

    score = 0
    score += 4 if metrics["clean_end"] else 0
    score += 4 if metrics["terminal_tool_success"] else 0
    score += 2 if metrics["result_ids_match_call_ids"] else 0
    score += 1 if metrics["all_calls_have_ids"] else 0
    score += 1 if metrics["exact_call_syntax"] else 0
    score += 1 if metrics["final_hygiene"] else 0
    score += 1 if metrics["final_after_last_tool"] else 0
    score += 1 if metrics["not_truncated"] else 0
    metrics["score"] = score
    metrics["failure_buckets"] = _failure_buckets(metrics)
    return metrics


def summarize(name: str, rows: list[dict]) -> dict:
    total = len(rows)
    by_kind: dict[str, list[dict]] = defaultdict(list)
    failure_counts: Counter[str] = Counter()
    for row in rows:
        metrics = row["metrics"]
        by_kind[metrics["kind"]].append(row)
        failure_counts.update(metrics["failure_buckets"])

    kinds = {}
    for kind, kind_rows in sorted(by_kind.items()):
        n = len(kind_rows)
        kinds[kind] = {
            "num_prompts": n,
            "valid_trace_rate": sum(r["metrics"]["valid_trace"] for r in kind_rows) / n,
            "clean_end_rate": sum(r["metrics"]["clean_end"] for r in kind_rows) / n,
            "expected_tool_sequence_rate": sum(r["metrics"]["expected_tool_sequence_exact"] for r in kind_rows) / n,
            "result_id_match_rate": sum(r["metrics"]["result_ids_match_call_ids"] for r in kind_rows) / n,
            "exact_call_syntax_rate": sum(r["metrics"]["exact_call_syntax"] for r in kind_rows) / n,
            "final_hygiene_rate": sum(r["metrics"]["final_hygiene"] for r in kind_rows) / n,
            "final_after_last_tool_rate": sum(r["metrics"]["final_after_last_tool"] for r in kind_rows) / n,
            "terminal_tool_success_rate": sum(r["metrics"]["terminal_tool_success"] for r in kind_rows) / n,
        }

    return {
        "model": name,
        "num_prompts": total,
        "valid_traces": sum(1 for row in rows if row["metrics"]["valid_trace"]),
        "avg_score": sum(row["metrics"]["score"] for row in rows) / total,
        "clean_end_rate": sum(1 for row in rows if row["metrics"]["clean_end"]) / total,
        "expected_tool_sequence_rate": sum(1 for row in rows if row["metrics"]["expected_tool_sequence_exact"]) / total,
        "result_id_match_rate": sum(1 for row in rows if row["metrics"]["result_ids_match_call_ids"]) / total,
        "exact_call_syntax_rate": sum(1 for row in rows if row["metrics"]["exact_call_syntax"]) / total,
        "final_hygiene_rate": sum(1 for row in rows if row["metrics"]["final_hygiene"]) / total,
        "final_after_last_tool_rate": sum(1 for row in rows if row["metrics"]["final_after_last_tool"]) / total,
        "terminal_tool_success_rate": sum(1 for row in rows if row["metrics"]["terminal_tool_success"]) / total,
        "not_truncated_rate": sum(1 for row in rows if row["metrics"]["not_truncated"]) / total,
        "failure_buckets": dict(sorted(failure_counts.items())),
        "by_kind": kinds,
    }
