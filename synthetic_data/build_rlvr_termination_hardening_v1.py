#!/usr/bin/env python3
"""Build a large RL-oriented SFT top-up focused on verified closure.

This top-up is intentionally repetitive in *behavioral target* while still
varying the surface form:
  read_file -> apply_patch -> cargo_test/cargo_run -> one final response -> stop

The existing final SFT file already contains some of this pattern, but it is
underweighted versus the broader corpus. This script appends many more
termination-explicit traces and writes a new recommended SFT dataset for RL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "synthetic_data") not in sys.path:
    sys.path.insert(0, str(ROOT / "synthetic_data"))

import build_gold50 as g  # noqa: E402
from core.validator import validate_trace  # noqa: E402
from synthetic_data.build_gold_rust_tooluse import (  # noqa: E402
    BIN_BUGFIX_CASES,
    LIB_BUGFIX_CASES,
    SYSTEM,
    rust_dev_tools,
    three_tool_trace,
)


BASE_DATASET = ROOT / "synthetic_data" / "final_glyph_sft_dataset.jsonl"
EVAL_PROMPTS = ROOT / "sft" / "evals" / "prompts_125.yaml"
TOPUP_OUT = ROOT / "synthetic_data" / "rlvr_seed_termination_hardening_v1.jsonl"
COMBINED_OUT = ROOT / "synthetic_data" / "final_glyph_sft_dataset_rlvr_term_v1.jsonl"
REPORT_OUT = ROOT / "synthetic_data" / "rlvr_seed_termination_hardening_v1_report.json"


LIB_USER_TEMPLATES = [
    'The Cargo crate at "{project_path}" has a failing test. Read "{file_path}", patch the exact bug, run cargo_test, then reply once and stop immediately.',
    'Open "{file_path}" in the crate "{project_path}", make one exact fix, verify with cargo_test, then end with one final response only.',
    'Investigate the failing Rust crate at "{project_path}". Read the source, apply one precise patch, verify with cargo_test, and stop right after the final response.',
    'Read "{file_path}", repair the bug with a single apply_patch call, run cargo_test on "{project_path}", then answer briefly and terminate cleanly.',
    'The test failure in "{project_path}" should be fixed by one targeted source edit. Read "{file_path}", patch it, verify with cargo_test, then close with one response and no extra output.',
    'Inspect "{file_path}" for the exact defect, patch it once, run cargo_test for "{project_path}", and after the verified final response emit nothing else.',
    'Use the Rust tools to fix the failing crate "{project_path}": read the file, patch the bug, run cargo_test, then stop immediately after the response.',
    'For "{project_path}", do the full repair loop: read "{file_path}", apply one exact patch, verify with cargo_test, then give one concise final response and end cleanly.',
]

BIN_USER_TEMPLATES = [
    'The Cargo binary at "{project_path}" is wrong. Read "{file_path}", apply one exact patch, run cargo_run, then reply once and stop immediately.',
    'Open "{file_path}" for the binary "{project_path}", make one precise fix, verify it with cargo_run, then end with one final response only.',
    'Inspect the Rust binary at "{project_path}". Read the source, patch the bug, run cargo_run, and stop right after the final response.',
    'Read "{file_path}", fix the exact bug with a single apply_patch call, verify with cargo_run on "{project_path}", then answer briefly and terminate cleanly.',
    'The binary behavior in "{project_path}" should be repaired by one targeted edit. Read "{file_path}", patch it, run cargo_run, then close with one response and no trailing output.',
    'Inspect "{file_path}" for the exact defect, patch it once, run cargo_run for "{project_path}", and after the verified final response emit nothing else.',
    'Use the Rust tools to fix the binary "{project_path}": read the file, patch the bug, run cargo_run, then stop immediately after the response.',
    'For "{project_path}", do the full repair loop: read "{file_path}", apply one exact patch, verify with cargo_run, then give one concise final response and end cleanly.',
]

RATIONALES = [
    "The trace is only complete after the verifier succeeds, and it must stop immediately after the final response.",
    "Do not stop after apply_patch. Verification comes next, then exactly one clean final response, then no more tokens.",
    "The assistant should demonstrate the full repair loop and terminate right after the closing response.",
    "Success here means patch, verify, answer, and then stop with no extra act blocks, notes, or repeated tags.",
]

SRC_THOUGHTS = [
    "The read_file output exposes the exact buggy snippet, so one precise patch is enough.",
    "The relevant code is visible now; patch the exact text and keep the workflow tight.",
    "The source inspection is complete, so the next step is a single targeted apply_patch call.",
    "The bug is localized in the displayed snippet; fix only that text before verification.",
]

PATCH_THOUGHTS = [
    "The patch landed, but the task is still incomplete until the verifier runs successfully.",
    "apply_patch succeeded; do not close yet because verification must happen before the final response.",
    "The edit is in place, but this trace should continue to the verifier before any closing response.",
    "The source change succeeded. The next assistant action must be the verifier call, not the final answer.",
]

VERIFY_THOUGHTS = [
    "Verification succeeded. Give one final response now and then stop immediately with no extra tokens.",
    "The verifier output is available, so the assistant can close with exactly one final response and no trailing content.",
    "The repair is confirmed. The next turn should be only the final response, followed by immediate termination.",
    "The verifier passed, so the trace can end cleanly after a single concise response.",
]

LIB_RESPONSE_TEMPLATES = [
    'I patched the bug, verified it with `cargo_test`, and the crate now passes its tests.',
    'I made the one-line fix, ran `cargo_test`, and the test suite now passes cleanly.',
    'I applied the targeted repair, confirmed it with `cargo_test`, and the crate is now green.',
    'I fixed the source bug, verified the result via `cargo_test`, and the tests now succeed.',
]

BIN_RESPONSE_TEMPLATES = [
    'I patched the bug, verified it with `cargo_run`, and the fixed stdout is `"{stdout}"`.',
    'I made the exact edit, ran `cargo_run`, and the program now prints `"{stdout}"`.',
    'I applied the targeted fix, confirmed it with `cargo_run`, and the corrected stdout is `"{stdout}"`.',
    'I fixed the source bug, verified it via `cargo_run`, and the binary now outputs `"{stdout}"`.',
]


def load_eval_users() -> set[str]:
    data = yaml.safe_load(EVAL_PROMPTS.read_text(encoding="utf-8"))
    rows = data["formal_eval"] if isinstance(data, dict) else data
    return {row["user"] for row in rows}


def extract_users(traces: list[str]) -> list[str]:
    users: list[str] = []
    marker = "<|im_start|>user\nuser「"
    end = "」🏷 usr1"
    for trace in traces:
        start = trace.index(marker) + len(marker)
        stop = trace.index(end, start)
        users.append(trace[start:stop])
    return users


def lib_trace(case_index: int, variant_index: int, case: tuple[str, str, str, str, str]) -> str:
    crate, source, find, replace, summary = case
    project_path = f"/workspace/glyph/runs/rlvr1/rust_cases/{crate}"
    file_path = f"{project_path}/src/lib.rs"
    name = f"{crate}_term_{variant_index + 1}"
    user = LIB_USER_TEMPLATES[variant_index].format(project_path=project_path, file_path=file_path)
    todos = [
        f"Read {file_path} to locate the exact buggy code.",
        "Apply one exact patch and do not introduce unrelated edits.",
        f"Run cargo_test on {project_path} to verify the fix.",
        "After verification, give exactly one final response and stop immediately with no extra output.",
    ]
    rationale = RATIONALES[(case_index + variant_index) % len(RATIONALES)]
    t1 = SRC_THOUGHTS[(case_index + variant_index) % len(SRC_THOUGHTS)]
    t2 = PATCH_THOUGHTS[(case_index + variant_index) % len(PATCH_THOUGHTS)]
    t3 = VERIFY_THOUGHTS[(case_index + variant_index) % len(VERIFY_THOUGHTS)]
    response = LIB_RESPONSE_TEMPLATES[(case_index + variant_index) % len(LIB_RESPONSE_TEMPLATES)]
    if variant_index % 2 == 1:
        response = f"{response} {summary}"
    return three_tool_trace(
        user,
        todos,
        rationale,
        "read_file",
        [("file_path", file_path)],
        f"src_{name}",
        source.replace('"', '\\"'),
        t1,
        f"note_src_{name}",
        "apply_patch",
        [("file_path", file_path), ("find", find), ("replace", replace)],
        f"patch_{name}",
        "status: success\\nexit_code: 0",
        t2,
        f"note_patch_{name}",
        "cargo_test",
        [("project_path", project_path)],
        f"test_{name}",
        "status: success\\nexit_code: 0\\nstdout: test result: ok",
        t3,
        f"note_test_{name}",
        response,
    )


def bin_trace(case_index: int, variant_index: int, case: tuple[str, str, str, str, str, str]) -> str:
    crate, source, find, replace, stdout, summary = case
    project_path = f"/workspace/glyph/runs/rlvr1/rust_cases/{crate}"
    file_path = f"{project_path}/src/main.rs"
    name = f"{crate}_term_{variant_index + 1}"
    user = BIN_USER_TEMPLATES[variant_index].format(project_path=project_path, file_path=file_path)
    todos = [
        f"Read {file_path} to locate the exact buggy code.",
        "Apply one exact patch and keep the edit narrowly scoped.",
        f"Run cargo_run on {project_path} to verify the corrected stdout.",
        "After verification, give exactly one final response and stop immediately with no trailing output.",
    ]
    rationale = RATIONALES[(case_index + variant_index) % len(RATIONALES)]
    t1 = SRC_THOUGHTS[(case_index + variant_index) % len(SRC_THOUGHTS)]
    t2 = PATCH_THOUGHTS[(case_index + variant_index) % len(PATCH_THOUGHTS)]
    t3 = VERIFY_THOUGHTS[(case_index + variant_index) % len(VERIFY_THOUGHTS)]
    response = BIN_RESPONSE_TEMPLATES[(case_index + variant_index) % len(BIN_RESPONSE_TEMPLATES)].format(stdout=stdout)
    if variant_index % 2 == 1:
        response = f"{response} {summary}"
    return three_tool_trace(
        user,
        todos,
        rationale,
        "read_file",
        [("file_path", file_path)],
        f"src_{name}",
        source.replace('"', '\\"'),
        t1,
        f"note_src_{name}",
        "apply_patch",
        [("file_path", file_path), ("find", find), ("replace", replace)],
        f"patch_{name}",
        "status: success\\nexit_code: 0",
        t2,
        f"note_patch_{name}",
        "cargo_run",
        [("project_path", project_path)],
        f"run_{name}",
        f"status: success\\nexit_code: 0\\nstdout: {stdout}",
        t3,
        f"note_run_{name}",
        response,
    )


def build_traces() -> list[str]:
    traces: list[str] = []
    for case_index, case in enumerate(LIB_BUGFIX_CASES):
        for variant_index in range(len(LIB_USER_TEMPLATES)):
            traces.append(lib_trace(case_index, variant_index, case))
    for case_index, case in enumerate(BIN_BUGFIX_CASES):
        for variant_index in range(len(BIN_USER_TEMPLATES)):
            traces.append(bin_trace(case_index, variant_index, case))
    return traces


def load_jsonl(path: Path) -> list[str]:
    rows: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(line)
    return rows


def exact_dedupe(rows: list[str]) -> list[str]:
    seen: set[str] = set()
    kept: list[str] = []
    for row in rows:
        if row in seen:
            continue
        seen.add(row)
        kept.append(row)
    return kept


def count_patch_verify(rows: list[str]) -> int:
    total = 0
    for row in rows:
        trace = json.loads(row)["trace"]
        if "apply_patch" in trace and ("cargo_test" in trace or "cargo_run" in trace):
            total += 1
    return total


def main() -> int:
    traces = build_traces()
    overlaps = sorted(set(extract_users(traces)) & load_eval_users())
    invalid = []
    for i, trace in enumerate(traces):
        res = validate_trace(trace)
        if not res.valid:
            invalid.append({"index": i, "errors": res.errors[:5]})
    if overlaps:
        print(json.dumps({"exact_prompt_overlaps": overlaps[:10], "count": len(overlaps)}, indent=2))
        return 1
    if invalid:
        print(json.dumps({"invalid": invalid[:10], "count": len(invalid)}, indent=2))
        return 1

    topup_rows = [json.dumps({"trace": trace}, ensure_ascii=False) for trace in traces]
    base_rows = load_jsonl(BASE_DATASET)
    combined_rows = exact_dedupe(base_rows + topup_rows)

    TOPUP_OUT.write_text("\n".join(topup_rows) + "\n", encoding="utf-8")
    COMBINED_OUT.write_text("\n".join(combined_rows) + "\n", encoding="utf-8")

    report = {
        "base_rows": len(base_rows),
        "topup_rows": len(topup_rows),
        "combined_rows": len(combined_rows),
        "topup_patch_verify_rows": count_patch_verify(topup_rows),
        "combined_patch_verify_rows": count_patch_verify(combined_rows),
        "topup_file": str(TOPUP_OUT.relative_to(ROOT)),
        "combined_file": str(COMBINED_OUT.relative_to(ROOT)),
        "system_prompt": SYSTEM,
        "notes": [
            "This top-up aggressively reinforces patch-verify-close-stop behavior.",
            "Every synthetic trace includes explicit stop language after the final response.",
            "Use the combined file for the next RL-oriented SFT retrain.",
        ],
    }
    REPORT_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
