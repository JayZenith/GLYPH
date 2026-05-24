"""Per-output scoring + summary for the RL-focused formal generation eval."""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from core.validator import validate_trace


REPETITION_PATTERN = re.compile(r"(.{20,200}?)\1{4,}", re.DOTALL)
TAIL_OK_PATTERN = re.compile(r"[\s※⊨𝑝🏷•\[\]\w\d\.\-\"']*")
SEG_RE = re.compile(r"<\|im_start\|>(\w+)\n(.*?)<\|im_end\|>", re.DOTALL)
RESULT_RE = re.compile(r"(^|\n)\s*result\s*\{")
CALL_TOOL_RE = re.compile(r"call\s*↦\s*\{[^}]*?\btool\s*↦\s*([^\s•}]+)", re.DOTALL)


def _segments(text: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in SEG_RE.finditer(text)]


def _assistant_text(full_trace: str) -> str:
    return "\n".join(body for role, body in _segments(full_trace) if role == "assistant")


def _call_sequence(assistant_text: str) -> list[str]:
    return [m.group(1).strip('"') for m in CALL_TOOL_RE.finditer(assistant_text)]


def _expectations(item: dict) -> dict:
    name = item["name"]
    if name.startswith("devtool_lib_"):
        return {"kind": "patch_test", "expected_tool_sequence": ["read_file", "apply_patch", "cargo_test"]}
    if name.startswith("devtool_bin_"):
        return {"kind": "patch_run", "expected_tool_sequence": ["read_file", "apply_patch", "cargo_run"]}
    if name.startswith("devtool_run_"):
        return {"kind": "run_only", "expected_tool_sequence": ["cargo_run"]}
    if name.startswith("devtool_build_"):
        return {"kind": "build_only", "expected_tool_sequence": ["cargo_build"]}
    if name.startswith("devtool_check_") or name.startswith("cargo_"):
        return {"kind": "check_only", "expected_tool_sequence": ["cargo_check"]}
    if name.startswith("devtool_test_"):
        return {"kind": "test_only", "expected_tool_sequence": ["cargo_test"]}
    if name.startswith("devtool_rustc_"):
        return {"kind": "rustc_only", "expected_tool_sequence": ["rustc"]}
    if name.startswith("devtool_read_"):
        return {"kind": "read_only", "expected_tool_sequence": ["read_file"]}
    if name.startswith("plan_"):
        return {
            "kind": "planning",
            "expected_tool_sequence": ["get_availability", "create_project_plan"],
        }
    return {"kind": "other", "expected_tool_sequence": []}


def _failure_buckets(metrics: dict, validation_errors: list[str]) -> list[str]:
    buckets: list[str] = []
    if not metrics["has_response"]:
        buckets.append("missing_response")
    if not metrics["clean_end"]:
        buckets.append("dirty_or_unclosed_final_response")
    if not metrics["no_repetition"]:
        buckets.append("repetition")
    if metrics["assistant_has_result"]:
        buckets.append("assistant_emitted_result_block")
    if not metrics["response_after_last_tool"]:
        buckets.append("response_before_tool_completion")
    if not metrics["expected_tool_sequence_exact"]:
        buckets.append("wrong_tool_sequence")
    if not metrics["not_truncated"]:
        buckets.append("truncated")
    for err in validation_errors:
        if err.startswith("Unsatisfied todo items"):
            buckets.append("unsatisfied_todos")
        elif err.startswith("References to undefined tags"):
            buckets.append("undefined_tags")
        elif err.startswith("Garbage after final response"):
            buckets.append("garbage_after_response")
        elif err.startswith("Final response block is unclosed"):
            buckets.append("unclosed_response")
        elif err.startswith("Tool calls without matching result"):
            buckets.append("missing_tool_results")
    return sorted(set(buckets))


def score_output(
    prompt_text: str,
    output_text: str,
    item: dict,
    new_token_count: int,
    max_new_tokens: int,
) -> dict:
    full_trace = prompt_text + output_text
    validation = validate_trace(full_trace)
    assistant_text = _assistant_text(full_trace)
    tool_turns = [body for role, body in _segments(full_trace) if role == "tool"]
    assistant_has_result = bool(RESULT_RE.search(assistant_text))
    call_sequence = _call_sequence(assistant_text)
    expect = _expectations(item)
    expected_tool_sequence = expect["expected_tool_sequence"]

    metrics = {
        "kind": expect["kind"],
        "valid_trace": validation.valid,
        "warning_count": len(validation.warnings),
        "error_count": len(validation.errors),
        "has_plan": "plan {" in assistant_text,
        "has_act": "act {" in assistant_text,
        "has_response": "response「" in assistant_text or 'response"' in assistant_text,
        "assistant_has_result": assistant_has_result,
        "tool_result_count": sum("result {" in body for body in tool_turns),
        "has_tool_turn": bool(tool_turns),
        "has_tool_call": "call ↦ {" in assistant_text,
        "has_think_block": "think ↦" in assistant_text,
        "call_sequence": call_sequence,
        "expected_tool_sequence": expected_tool_sequence,
        "raw_chars": len(output_text),
    }

    metrics["mentions_any_tool_name"] = any(
        tool["name"] in assistant_text for tool in item.get("tools", [])
    )
    metrics["no_repetition"] = REPETITION_PATTERN.search(assistant_text) is None
    last_resp = assistant_text.rfind("response「")
    last_close = assistant_text.rfind("」")
    tail = assistant_text[last_close + 1:].strip() if last_close >= 0 else ""
    tail_ok = bool(TAIL_OK_PATTERN.fullmatch(tail))
    metrics["clean_end"] = last_resp >= 0 and last_close > last_resp and tail_ok
    metrics["ends_with_response"] = metrics["clean_end"]
    metrics["not_truncated"] = new_token_count < max_new_tokens - 10
    metrics["new_token_count"] = new_token_count
    metrics["expected_tool_sequence_exact"] = call_sequence == expected_tool_sequence

    if last_resp >= 0:
        last_call_pos = max((m.start() for m in CALL_TOOL_RE.finditer(assistant_text)), default=-1)
        metrics["response_after_last_tool"] = last_resp > last_call_pos
    else:
        metrics["response_after_last_tool"] = False

    if expected_tool_sequence and "apply_patch" in expected_tool_sequence:
        try:
            patch_i = call_sequence.index("apply_patch")
        except ValueError:
            metrics["verifier_after_patch"] = False
        else:
            verifier = expected_tool_sequence[-1]
            metrics["verifier_after_patch"] = verifier in call_sequence[patch_i + 1 :]
    else:
        metrics["verifier_after_patch"] = True

    score = 0
    score += 4 if metrics["clean_end"] else 0
    score += 3 if metrics["expected_tool_sequence_exact"] else 0
    score += 2 if metrics["no_repetition"] else 0
    score += 1 if metrics["response_after_last_tool"] else 0
    score += 1 if not assistant_has_result else 0
    score += 1 if metrics["not_truncated"] else 0
    metrics["score"] = score
    metrics["validation_errors"] = validation.errors
    metrics["validation_warnings"] = validation.warnings
    metrics["failure_buckets"] = _failure_buckets(metrics, validation.errors)
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
            "no_repetition_rate": sum(r["metrics"]["no_repetition"] for r in kind_rows) / n,
            "not_truncated_rate": sum(r["metrics"]["not_truncated"] for r in kind_rows) / n,
        }

    return {
        "model": name,
        "num_prompts": total,
        "valid_traces": sum(1 for row in rows if row["metrics"]["valid_trace"]),
        "avg_score": sum(row["metrics"]["score"] for row in rows) / total,
        "clean_end_rate": sum(1 for row in rows if row["metrics"]["clean_end"]) / total,
        "expected_tool_sequence_rate": sum(
            1 for row in rows if row["metrics"]["expected_tool_sequence_exact"]
        ) / total,
        "response_after_last_tool_rate": sum(
            1 for row in rows if row["metrics"]["response_after_last_tool"]
        ) / total,
        "assistant_result_rate": sum(
            1 for row in rows if row["metrics"]["assistant_has_result"]
        ) / total,
        "no_repetition_rate": sum(1 for row in rows if row["metrics"]["no_repetition"]) / total,
        "not_truncated_rate": sum(1 for row in rows if row["metrics"]["not_truncated"]) / total,
        "failure_buckets": dict(sorted(failure_counts.items())),
        "by_kind": kinds,
    }
