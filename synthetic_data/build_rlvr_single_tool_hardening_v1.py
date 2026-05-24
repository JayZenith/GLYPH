#!/usr/bin/env python3
"""Build a single-tool sufficiency top-up for RL-oriented SFT.

Goal:
- keep the strong clean-termination behavior from rlvr_term_v1
- counterbalance overlearned read->patch->verify behavior
- teach exact minimal tool sufficiency:
  cargo_check -> response -> stop
  cargo_build -> response -> stop
  cargo_test -> response -> stop
  cargo_run -> response -> stop
  rustc -> response -> stop
  read_file -> response -> stop
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
from synthetic_data.build_gold_rust_tooluse import SYSTEM, rust_dev_tools  # noqa: E402


BASE_DATASET = ROOT / "synthetic_data" / "final_glyph_sft_dataset_rlvr_term_v1.jsonl"
EVAL_PROMPTS = ROOT / "sft" / "evals" / "prompts_125.yaml"
TOPUP_OUT = ROOT / "synthetic_data" / "rlvr_seed_single_tool_hardening_v1.jsonl"
COMBINED_OUT = ROOT / "synthetic_data" / "final_glyph_sft_dataset_rlvr_term_v2.jsonl"
REPORT_OUT = ROOT / "synthetic_data" / "rlvr_seed_single_tool_hardening_v1_report.json"


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


READ_USER_TEMPLATES = [
    'Read "{path}", answer the question directly, and stop immediately after one final response.',
    'Open "{path}" and summarize it briefly. Do not call any extra tools after the file read.',
    'Inspect "{path}" with read_file, then respond once and terminate cleanly with no extra output.',
    'Use exactly one read_file call on "{path}", answer briefly, and stop right after the final response.',
]

RUN_USER_TEMPLATES = [
    'Run the Cargo binary at "{path}" with cargo_run, report stdout briefly, and stop immediately after one final response.',
    'Use exactly one cargo_run call on "{path}", summarize the output, and do not read or patch any files.',
    'Execute "{path}" via cargo_run, answer once with the result, and terminate cleanly with no extra tool calls.',
    'Call cargo_run on "{path}", report the program output briefly, then stop right after the final response.',
]

BUILD_USER_TEMPLATES = [
    'Run cargo_build on "{path}", report whether the build succeeds, and stop immediately after one final response.',
    'Use exactly one cargo_build call on "{path}", summarize the build outcome, and do not read or patch any files.',
    'Build "{path}" with cargo_build, answer once with the result, and terminate cleanly with no extra tool calls.',
    'Call cargo_build on "{path}", report the compile outcome briefly, then stop right after the final response.',
]

CHECK_USER_TEMPLATES = [
    'Run cargo_check on "{path}", report the type-check result briefly, and stop immediately after one final response.',
    'Use exactly one cargo_check call on "{path}", summarize the diagnostic outcome, and do not read or patch any files.',
    'Check "{path}" with cargo_check, answer once with the result, and terminate cleanly with no extra tool calls.',
    'Call cargo_check on "{path}", report the compile diagnostics briefly, then stop right after the final response.',
]

TEST_USER_TEMPLATES = [
    'Run cargo_test on "{path}", report the test outcome briefly, and stop immediately after one final response.',
    'Use exactly one cargo_test call on "{path}", summarize the test result, and do not read or patch any files.',
    'Test "{path}" with cargo_test, answer once with the result, and terminate cleanly with no extra tool calls.',
    'Call cargo_test on "{path}", report the suite outcome briefly, then stop right after the final response.',
]

RUSTC_USER_TEMPLATES = [
    'Compile "{source}" to "{output}" with rustc, report the compile outcome briefly, and stop immediately after one final response.',
    'Use exactly one rustc call on "{source}" with output "{output}", summarize the result, and do not read or patch any files.',
    'Build the standalone file "{source}" into "{output}" via rustc, answer once with the result, and terminate cleanly.',
    'Call rustc on "{source}" with output "{output}", report whether compilation succeeded, then stop right after the final response.',
]

RATIONALES = [
    "This task is satisfied by one tool call. Do not add read_file, apply_patch, or any extra verifier after the requested tool succeeds.",
    "Use exactly the requested tool once, then close with one clean final response and no trailing output.",
    "The minimal sufficient behavior is one correct tool call followed by a brief response and immediate termination.",
    "Do not expand this into a repair workflow. One tool result is enough, then the trace must stop cleanly.",
]

TOOL_THOUGHTS = [
    "The request is fully answerable from this single tool result, so the response should close immediately after it.",
    "No extra inspection or patching is needed here; one tool call satisfies the task completely.",
    "The tool output now contains all the information required for the final response and clean termination.",
    "This is a single-tool task, so the trace should end after one brief response with no extra calls.",
]


def single_tool_hardened_trace(
    *,
    user: str,
    todo_1: str,
    todo_2: str,
    rationale: str,
    tool_name: str,
    args: list[tuple[str, str]],
    call_id: str,
    result_data: str,
    thought: str,
    note_tag: str,
    response: str,
) -> str:
    return g.join_trace(
        g.system_seg(SYSTEM, rust_dev_tools()),
        g.user_seg(user),
        g.assistant_seg(
            g.plan_block([todo_1, todo_2], rationale),
            g.call_act(tool_name, args, call_id, 1),
        ),
        g.result_seg(result_data, call_id),
        g.assistant_seg(
            g.think_act([(thought, note_tag, [call_id])]),
            g.response_block(response, [call_id, note_tag], 2),
        ),
    )


READ_CASES = [
    {
        "name": "showcase_api",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/showcase_lib/src/lib.rs",
        "result": 'pub fn greet(name: &str) -> String {\\n    format!("Hello, {}!", name)\\n}',
        "responses": [
            "The file defines a single public `greet` function that formats `Hello, <name>!`.",
            "It exposes one `greet` helper that returns a formatted hello string.",
        ],
    },
    {
        "name": "inspect_main",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/inspect_main_app/src/main.rs",
        "result": 'fn main() {\\n    let nums = [1, 2, 3, 4];\\n    let sum: i32 = nums.iter().sum();\\n    println!("{sum}");\\n}',
        "responses": [
            "The program sums `1, 2, 3, 4` and prints the total.",
            "It computes the sum of the array values and prints that result.",
        ],
    },
    {
        "name": "mathlib2",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/mathlib2/src/lib.rs",
        "result": "pub fn add(a: i32, b: i32) -> i32 { a + b }",
        "responses": [
            "The file defines a simple `add` function returning `a + b`.",
            "It exposes one public addition helper for two `i32` values.",
        ],
    },
    {
        "name": "strutils",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/strutils/src/lib.rs",
        "result": "pub fn shout(s: &str) -> String { s.to_uppercase() }",
        "responses": [
            "The file defines `shout`, which uppercases its input string.",
            "It exposes one function that returns the uppercase version of the input.",
        ],
    },
]

RUN_CASES = [
    {
        "name": "greeter2",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/greeter2",
        "result": "status: success\\nexit_code: 0\\nstdout: hello",
        "responses": [
            "cargo_run succeeded and the binary printed `hello`.",
            "The program ran successfully; stdout was `hello`.",
        ],
    },
    {
        "name": "counter2",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/counter2",
        "result": "status: success\\nexit_code: 0\\nstdout: 1\\n2\\n3\\n4\\n5",
        "responses": [
            "cargo_run succeeded and printed the numbers `1` through `5` on separate lines.",
            "The program ran successfully; stdout was the sequence `1, 2, 3, 4, 5` line by line.",
        ],
    },
    {
        "name": "rev_bin",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/rev_bin",
        "result": "status: success\\nexit_code: 0\\nstdout: olleh",
        "responses": [
            "cargo_run succeeded and the binary printed `olleh`.",
            "The program ran successfully; stdout was `olleh`.",
        ],
    },
    {
        "name": "hello_bin",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/hello_bin",
        "result": "status: success\\nexit_code: 0\\nstdout: hello",
        "responses": [
            "cargo_run succeeded and the binary printed `hello`.",
            "The program ran successfully; stdout was `hello`.",
        ],
    },
]

BUILD_CASES = [
    {
        "name": "greeter2",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/greeter2",
        "result": "status: success\\nexit_code: 0\\nstdout: Compiling greeter2 v0.1.0\\nFinished `dev` profile",
        "responses": [
            "cargo_build succeeded; the project compiled cleanly.",
            "The build finished successfully with no errors.",
        ],
    },
    {
        "name": "counter2",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/counter2",
        "result": "status: success\\nexit_code: 0\\nstdout: Compiling counter2 v0.1.0\\nFinished `dev` profile",
        "responses": [
            "cargo_build succeeded; the binary compiled cleanly.",
            "The build completed successfully with no compile errors.",
        ],
    },
    {
        "name": "release_pipeline",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/release_pipeline",
        "result": "status: success\\nexit_code: 0\\nstdout: Finished `dev` profile",
        "responses": [
            "cargo_build succeeded for the project.",
            "The build finished successfully.",
        ],
    },
    {
        "name": "workspace_lint",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/workspace_lint",
        "result": "status: success\\nexit_code: 0\\nstdout: Finished `dev` profile",
        "responses": [
            "cargo_build succeeded for the workspace project.",
            "The workspace build completed successfully.",
        ],
    },
]

CHECK_CASES = [
    {
        "name": "mathlib2",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/mathlib2",
        "result": "status: success\\nexit_code: 0\\nstdout: Checking mathlib2 v0.1.0\\nFinished",
        "responses": [
            "cargo_check passed; the crate type-checks cleanly.",
            "The project passed cargo_check with no diagnostics.",
        ],
    },
    {
        "name": "optionlib_eval",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/optionlib_eval",
        "result": "status: success\\nexit_code: 0\\nstdout: Checking optionlib_eval v0.1.0\\nFinished",
        "responses": [
            "cargo_check passed; the project type-checks cleanly.",
            "The crate passed cargo_check without compile errors.",
        ],
    },
    {
        "name": "traits_lib",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/traits_lib",
        "result": "status: failure\\nexit_code: 101\\nstderr: error[E0599]: no method named `run` found for struct `Runner` in the current scope",
        "responses": [
            "cargo_check failed with a missing-method diagnostic for `run` on `Runner`.",
            "The project did not pass cargo_check; the main diagnostic is that `Runner` has no `run` method in scope.",
        ],
    },
    {
        "name": "recursive_type_case",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/recursive_type_case",
        "result": "status: failure\\nexit_code: 101\\nstderr: error[E0072]: recursive type `Node` has infinite size",
        "responses": [
            "cargo_check failed with a recursive-type infinite-size error for `Node`.",
            "The project did not pass cargo_check; the main diagnostic is an infinite-size recursive `Node` type.",
        ],
    },
]

TEST_CASES = [
    {
        "name": "sortlib_eval",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/sortlib_eval",
        "result": "status: success\\nexit_code: 0\\nstdout: test result: ok",
        "responses": [
            "cargo_test passed; the test suite is green.",
            "The tests completed successfully with an `ok` result.",
        ],
    },
    {
        "name": "dedup_lib",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/dedup_lib",
        "result": "status: success\\nexit_code: 0\\nstdout: test result: ok",
        "responses": [
            "cargo_test passed; the crate's tests succeed.",
            "The test suite completed successfully.",
        ],
    },
    {
        "name": "gcdlib_bug_fixed",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/gcdlib_bug",
        "result": "status: success\\nexit_code: 0\\nstdout: test result: ok",
        "responses": [
            "cargo_test passed; the test run succeeded.",
            "The crate's tests completed successfully.",
        ],
    },
    {
        "name": "maxlib_bug_fixed",
        "path": "/workspace/glyph/runs/rlvr1/rust_cases/maxlib_bug",
        "result": "status: success\\nexit_code: 0\\nstdout: test result: ok",
        "responses": [
            "cargo_test passed; the suite is green.",
            "The tests ran successfully with an `ok` result.",
        ],
    },
]

RUSTC_CASES = [
    {
        "name": "hello2",
        "source": "/workspace/glyph/runs/rlvr1/rust_cases/hello2.rs",
        "output": "/workspace/glyph/runs/rlvr1/rust_cases/hello2_bin",
        "result": "status: success\\nexit_code: 0\\nstdout:",
        "responses": [
            "rustc succeeded and wrote the requested output binary.",
            "The source compiled successfully to the requested output path.",
        ],
    },
    {
        "name": "sum_one",
        "source": "/workspace/glyph/runs/rlvr1/rust_cases/sum_one.rs",
        "output": "/workspace/glyph/runs/rlvr1/rust_cases/sum_one_bin",
        "result": "status: success\\nexit_code: 0\\nstdout:",
        "responses": [
            "rustc succeeded and produced the requested binary.",
            "The standalone source compiled successfully.",
        ],
    },
    {
        "name": "hello_one",
        "source": "/workspace/glyph/runs/rlvr1/rust_cases/hello_one.rs",
        "output": "/workspace/glyph/runs/rlvr1/rust_cases/hello_one_bin",
        "result": "status: success\\nexit_code: 0\\nstdout:",
        "responses": [
            "rustc succeeded and generated the requested executable.",
            "The file compiled successfully to the output binary.",
        ],
    },
    {
        "name": "sum2",
        "source": "/workspace/glyph/runs/rlvr1/rust_cases/sum2.rs",
        "output": "/workspace/glyph/runs/rlvr1/rust_cases/sum2_bin",
        "result": "status: success\\nexit_code: 0\\nstdout:",
        "responses": [
            "rustc succeeded and produced the output binary cleanly.",
            "The standalone file compiled successfully with no errors.",
        ],
    },
]


def build_read_traces() -> list[str]:
    traces: list[str] = []
    for case_index, case in enumerate(READ_CASES):
        for variant_index, template in enumerate(READ_USER_TEMPLATES):
            response = case["responses"][variant_index % len(case["responses"])]
            traces.append(
                single_tool_hardened_trace(
                    user=template.format(path=case["path"]),
                    todo_1=f'Read {case["path"]} exactly once with read_file.',
                    todo_2="Answer directly, then stop immediately after one clean final response.",
                    rationale=RATIONALES[(case_index + variant_index) % len(RATIONALES)],
                    tool_name="read_file",
                    args=[("file_path", case["path"])],
                    call_id=f"src_{case['name']}_{variant_index + 1}",
                    result_data=case["result"].replace('"', '\\"'),
                    thought=TOOL_THOUGHTS[(case_index + variant_index) % len(TOOL_THOUGHTS)],
                    note_tag=f"note_read_{case['name']}_{variant_index + 1}",
                    response=response,
                )
            )
    return traces


def build_run_traces() -> list[str]:
    traces: list[str] = []
    for case_index, case in enumerate(RUN_CASES):
        for variant_index, template in enumerate(RUN_USER_TEMPLATES):
            response = case["responses"][variant_index % len(case["responses"])]
            traces.append(
                single_tool_hardened_trace(
                    user=template.format(path=case["path"]),
                    todo_1=f'Run cargo_run on {case["path"]} exactly once.',
                    todo_2="Report the stdout briefly, then stop immediately after one clean final response.",
                    rationale=RATIONALES[(case_index + variant_index) % len(RATIONALES)],
                    tool_name="cargo_run",
                    args=[("project_path", case["path"])],
                    call_id=f"run_{case['name']}_{variant_index + 1}",
                    result_data=case["result"],
                    thought=TOOL_THOUGHTS[(case_index + variant_index) % len(TOOL_THOUGHTS)],
                    note_tag=f"note_run_{case['name']}_{variant_index + 1}",
                    response=response,
                )
            )
    return traces


def build_build_traces() -> list[str]:
    traces: list[str] = []
    for case_index, case in enumerate(BUILD_CASES):
        for variant_index, template in enumerate(BUILD_USER_TEMPLATES):
            response = case["responses"][variant_index % len(case["responses"])]
            traces.append(
                single_tool_hardened_trace(
                    user=template.format(path=case["path"]),
                    todo_1=f'Run cargo_build on {case["path"]} exactly once.',
                    todo_2="Report the build outcome briefly, then stop immediately after one clean final response.",
                    rationale=RATIONALES[(case_index + variant_index) % len(RATIONALES)],
                    tool_name="cargo_build",
                    args=[("project_path", case["path"])],
                    call_id=f"build_{case['name']}_{variant_index + 1}",
                    result_data=case["result"],
                    thought=TOOL_THOUGHTS[(case_index + variant_index) % len(TOOL_THOUGHTS)],
                    note_tag=f"note_build_{case['name']}_{variant_index + 1}",
                    response=response,
                )
            )
    return traces


def build_check_traces() -> list[str]:
    traces: list[str] = []
    for case_index, case in enumerate(CHECK_CASES):
        for variant_index, template in enumerate(CHECK_USER_TEMPLATES):
            response = case["responses"][variant_index % len(case["responses"])]
            traces.append(
                single_tool_hardened_trace(
                    user=template.format(path=case["path"]),
                    todo_1=f'Run cargo_check on {case["path"]} exactly once.',
                    todo_2="Summarize the diagnostic outcome briefly, then stop immediately after one clean final response.",
                    rationale=RATIONALES[(case_index + variant_index) % len(RATIONALES)],
                    tool_name="cargo_check",
                    args=[("project_path", case["path"])],
                    call_id=f"chk_{case['name']}_{variant_index + 1}",
                    result_data=case["result"],
                    thought=TOOL_THOUGHTS[(case_index + variant_index) % len(TOOL_THOUGHTS)],
                    note_tag=f"note_check_{case['name']}_{variant_index + 1}",
                    response=response,
                )
            )
    return traces


def build_test_traces() -> list[str]:
    traces: list[str] = []
    for case_index, case in enumerate(TEST_CASES):
        for variant_index, template in enumerate(TEST_USER_TEMPLATES):
            response = case["responses"][variant_index % len(case["responses"])]
            traces.append(
                single_tool_hardened_trace(
                    user=template.format(path=case["path"]),
                    todo_1=f'Run cargo_test on {case["path"]} exactly once.',
                    todo_2="Report the test outcome briefly, then stop immediately after one clean final response.",
                    rationale=RATIONALES[(case_index + variant_index) % len(RATIONALES)],
                    tool_name="cargo_test",
                    args=[("project_path", case["path"])],
                    call_id=f"test_{case['name']}_{variant_index + 1}",
                    result_data=case["result"],
                    thought=TOOL_THOUGHTS[(case_index + variant_index) % len(TOOL_THOUGHTS)],
                    note_tag=f"note_test_{case['name']}_{variant_index + 1}",
                    response=response,
                )
            )
    return traces


def build_rustc_traces() -> list[str]:
    traces: list[str] = []
    for case_index, case in enumerate(RUSTC_CASES):
        for variant_index, template in enumerate(RUSTC_USER_TEMPLATES):
            response = case["responses"][variant_index % len(case["responses"])]
            traces.append(
                single_tool_hardened_trace(
                    user=template.format(source=case["source"], output=case["output"]),
                    todo_1=f'Compile {case["source"]} to {case["output"]} with exactly one rustc call.',
                    todo_2="Report the compile outcome briefly, then stop immediately after one clean final response.",
                    rationale=RATIONALES[(case_index + variant_index) % len(RATIONALES)],
                    tool_name="rustc",
                    args=[("source_file", case["source"]), ("output", case["output"])],
                    call_id=f"rustc_{case['name']}_{variant_index + 1}",
                    result_data=case["result"],
                    thought=TOOL_THOUGHTS[(case_index + variant_index) % len(TOOL_THOUGHTS)],
                    note_tag=f"note_rustc_{case['name']}_{variant_index + 1}",
                    response=response,
                )
            )
    return traces


def build_traces() -> list[str]:
    traces: list[str] = []
    traces.extend(build_read_traces())
    traces.extend(build_run_traces())
    traces.extend(build_build_traces())
    traces.extend(build_check_traces())
    traces.extend(build_test_traces())
    traces.extend(build_rustc_traces())
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


def count_rows_with_call(rows: list[str], tool_name: str) -> int:
    total = 0
    needle = f"tool ↦ {tool_name}"
    for row in rows:
        trace = json.loads(row)["trace"]
        if needle in trace:
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
        "topup_tool_mix": {
            "read_file": count_rows_with_call(topup_rows, "read_file"),
            "cargo_run": count_rows_with_call(topup_rows, "cargo_run"),
            "cargo_build": count_rows_with_call(topup_rows, "cargo_build"),
            "cargo_check": count_rows_with_call(topup_rows, "cargo_check"),
            "cargo_test": count_rows_with_call(topup_rows, "cargo_test"),
            "rustc": count_rows_with_call(topup_rows, "rustc"),
        },
        "topup_file": str(TOPUP_OUT.relative_to(ROOT)),
        "combined_file": str(COMBINED_OUT.relative_to(ROOT)),
        "notes": [
            "This top-up teaches exact single-tool sufficiency and clean immediate stopping.",
            "Use the combined file for the next RL-oriented SFT retrain if the current model is overusing read/patch workflows.",
        ],
    }
    REPORT_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
