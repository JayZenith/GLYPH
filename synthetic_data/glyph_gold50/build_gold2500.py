#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.validator import validate_trace
from synthetic_data.glyph_gold50 import build_gold300 as g300


OUT = Path(__file__).parent / "gold_glyph_2500.jsonl"
SYSTEM_RE = re.compile(r"(<\|im_start\|>system\n)system「(.*?)」", re.DOTALL)
USER_RE = re.compile(r"(<\|im_start\|>user\n)user「(.*?)」🏷 usr1", re.DOTALL)


SYSTEM_VARIANTS = {
    "rust_no_tool": [
        "You are a Rust language assistant who gives compact conceptual explanations.",
        "You are a concise Rust mentor who answers in short technical paragraphs.",
        "You are a Rust engineering explainer who stays brief and practical.",
        "You are a focused Rust assistant who gives short, direct explanations.",
        "You are a practical Rust reviewer who explains tradeoffs concisely.",
        "You are a concise Rust education assistant who prefers concrete answers.",
        "You are a Rust API design assistant who answers briefly and precisely.",
        "You are a Rust systems explainer who keeps answers compact and clear.",
    ],
    "rustdoc": [
        "You are a Rust documentation assistant who answers briefly and precisely.",
        "You are a concise Rust docs assistant who explains looked-up symbols clearly.",
        "You are a Rust reference assistant who uses doc results and responds briefly.",
        "You are a practical Rust documentation explainer who keeps answers short.",
        "You are a Rust docs helper who summarizes symbol behavior concisely.",
        "You are a precise Rust API assistant who uses the docs tool and answers briefly.",
        "You are a Rust documentation guide who explains tool results in compact language.",
        "You are a Rust symbol reference assistant who answers in one short explanation.",
    ],
    "cargo": [
        "You are a Rust debugging assistant who diagnoses compiler and tool output concisely.",
        "You are a concise Rust build-failure assistant who explains likely fixes briefly.",
        "You are a practical Rust diagnostics assistant who keeps repair guidance short.",
        "You are a Rust troubleshooting assistant who reads tool output and answers tersely.",
        "You are a focused Rust compiler assistant who gives brief diagnosis and repair direction.",
        "You are a Rust code-health assistant who interprets cargo output concisely.",
        "You are a concise Rust lint-and-test assistant who stays practical and direct.",
        "You are a Rust debugging mentor who turns tool output into a short fix recommendation.",
    ],
    "ci": [
        "You are a debugging assistant who keeps incident analysis concise and resilient to tool failure.",
        "You are a concise incident assistant who uses evidence first and answers briefly.",
        "You are a practical CI-debugging assistant who gives short, concrete next steps.",
        "You are an operations assistant who keeps failure analysis focused and compact.",
        "You are a concise reliability assistant who prioritizes direct evidence and short answers.",
        "You are a debugging assistant who narrows failures quickly and avoids unnecessary loops.",
        "You are a practical incident triage assistant who answers with one focused recommendation.",
        "You are a concise CI assistant who uses minimal tool steps and short diagnosis.",
    ],
    "sql": [
        "You are a data access assistant who uses SQL and answers briefly.",
        "You are a concise analytics assistant who runs one query and responds directly.",
        "You are a practical SQL assistant who returns short, exact answers.",
        "You are a read-only database assistant who answers compactly from query results.",
        "You are a concise reporting assistant who uses SQL and keeps responses short.",
        "You are an analytics helper who prefers one query and a direct answer.",
        "You are a SQL lookup assistant who answers briefly and precisely.",
        "You are a concise data-query assistant who returns only the needed result.",
    ],
    "math": [
        "You are a helpful assistant specialized in symbolic mathematics. Provide clear, concise solutions.",
        "You are a concise symbolic math assistant who uses tools and answers briefly.",
        "You are a practical calculus assistant who verifies results and keeps explanations short.",
        "You are a focused symbolic algebra assistant who responds in compact technical language.",
        "You are a concise math-solving assistant who uses one or two precise tool steps.",
        "You are a symbolic math helper who answers clearly and without extra verbosity.",
        "You are a practical mathematics assistant who verifies results and stops promptly.",
        "You are a concise calculus assistant who gives direct final answers after verification.",
    ],
    "file": [
        "You are a document assistant who reads a file and returns a short, concrete summary.",
        "You are a concise file-reading assistant who summarizes excerpts directly.",
        "You are a practical document assistant who answers with short, specific takeaways.",
        "You are a concise notes assistant who loads a file and summarizes only the essentials.",
        "You are a focused document summarizer who keeps outputs short and concrete.",
        "You are a brief file-summary assistant who extracts only the main conclusions.",
        "You are a practical reading assistant who turns excerpts into tight summaries.",
        "You are a concise document-review assistant who answers in one short summary.",
    ],
    "plan": [
        "You are a planning assistant that helps product teams build realistic launch plans and concise schedules.",
        "You are a concise planning assistant who checks staffing and produces short rollout recommendations.",
        "You are a practical launch-planning assistant who keeps plans realistic and brief.",
        "You are a scheduling assistant who gives compact rollout guidance grounded in tool results.",
        "You are a concise product-planning assistant who answers with short, actionable schedules.",
        "You are a practical operations planner who checks feasibility and responds briefly.",
        "You are a concise launch assistant who uses staffing data and keeps output tight.",
        "You are a planning helper who turns availability and task data into short rollout guidance.",
    ],
    "git": [
        "You are a concise git assistant who reads repository status and answers briefly.",
        "You are a practical git hygiene assistant who summarizes repo state compactly.",
        "You are a concise version-control assistant who uses git tools and answers directly.",
        "You are a git workflow assistant who keeps status summaries short and concrete.",
        "You are a practical git review assistant who reports only the important repo details.",
        "You are a concise source-control assistant who answers with brief actionable summaries.",
        "You are a git diagnostics assistant who reads repository metadata and stays short.",
        "You are a practical repository assistant who gives compact git-based answers.",
    ],
}


NO_TOOL_PREFIXES = [
    "Briefly, ",
    "In one short paragraph, ",
    "Give a concise answer: ",
    "Short answer: ",
]
NO_TOOL_SUFFIXES = [
    " Keep the answer concise.",
    " Answer briefly.",
    " Give a short practical explanation.",
    " Keep it to the key point.",
]
TOOL_PREFIXES = [
    "Briefly, ",
    "Keep it short: ",
    "Concisely, ",
    "Give a short answer: ",
]
TOOL_SUFFIXES = [
    " Use the available tool support and keep the answer concise.",
    " Use the tool flow and answer briefly.",
    " Keep the final answer short.",
    " Keep it compact.",
]


def infer_category(trace: str) -> str:
    if "rustdoc_lookup" in trace and not any(x in trace for x in ("cargo_check", "cargo_test", "cargo_clippy")):
        return "rustdoc"
    if any(x in trace for x in ("cargo_check", "cargo_test", "cargo_clippy")):
        return "cargo"
    if "get_ci_logs" in trace:
        return "ci"
    if "run_sql" in trace:
        return "sql"
    if "solve_symbolic" in trace:
        return "math"
    if "load_file" in trace:
        return "file"
    if "get_availability" in trace:
        return "plan"
    if "git_status" in trace or "git_log" in trace:
        return "git"
    return "rust_no_tool"


def replace_system(trace: str, system_text: str) -> str:
    return SYSTEM_RE.sub(rf"\1system「{system_text}」", trace, count=1)


def replace_user(trace: str, user_text: str) -> str:
    return USER_RE.sub(rf"\1user「{user_text}」🏷 usr1", trace, count=1)


def extract_user(trace: str) -> str:
    m = USER_RE.search(trace)
    if not m:
        raise ValueError("user segment not found")
    return m.group(2)


def has_tools(trace: str) -> bool:
    return "<|im_start|>tool" in trace or "tool {" in trace


def vary_user_text(user_text: str, idx: int, tooly: bool) -> str:
    if idx == 0:
        return user_text
    prefixes = TOOL_PREFIXES if tooly else NO_TOOL_PREFIXES
    suffixes = TOOL_SUFFIXES if tooly else NO_TOOL_SUFFIXES
    style = (idx - 1) % 4
    if (idx - 1) // 4 == 0:
        return prefixes[style] + user_text[0].lower() + user_text[1:] if user_text and user_text[0].isupper() else prefixes[style] + user_text
    return user_text + suffixes[style]


def augment_trace(trace: str, idx: int) -> str:
    category = infer_category(trace)
    system_text = SYSTEM_VARIANTS[category][idx % len(SYSTEM_VARIANTS[category])]
    user_text = vary_user_text(extract_user(trace), idx, has_tools(trace))
    return replace_user(replace_system(trace, system_text), user_text)


def build_records() -> list[str]:
    base = g300.extend_records()
    traces: list[str] = []
    seen: set[str] = set()

    def add(trace: str) -> None:
        if trace not in seen:
            seen.add(trace)
            traces.append(trace)

    for trace in base:
        add(trace)

    # 7 additional variants per seed trace.
    for variant_idx in range(1, 8):
        for trace in base:
            add(augment_trace(trace, variant_idx))

    # One more variant for the first 100 traces.
    for trace in base[:100]:
        add(augment_trace(trace, 8))

    extra_idx = 9
    while len(traces) < 2500:
        for trace in base:
            add(augment_trace(trace, extra_idx))
            if len(traces) == 2500:
                break
        extra_idx += 1

    assert len(traces) == 2500, len(traces)
    return traces


def main() -> int:
    traces = build_records()
    bad: list[tuple[int, list[str]]] = []
    with OUT.open("w") as f:
        for i, trace in enumerate(traces, start=1):
            res = validate_trace(trace)
            if not res.valid:
                bad.append((i, res.errors))
            f.write(json.dumps({"trace": trace}, ensure_ascii=False) + "\n")
    rustish = sum(1 for t in traces if ("Rust" in t or "rust" in t or "cargo_" in t or "rustdoc_" in t))
    print(json.dumps({"count": len(traces), "rustish": rustish, "ratio": rustish / len(traces), "output": str(OUT), "invalid": bad[:20], "invalid_count": len(bad)}, indent=2))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
