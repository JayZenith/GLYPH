#!/usr/bin/env python3
"""Build a final RLVR-focused SFT augmentation and combined dataset.

Goals:
- reinforce read_file -> response with clean endings
- reinforce read_file -> apply_patch -> cargo_test/cargo_run -> response
- reinforce correct todo satisfaction and closure
- reinforce RL tool arg schema (`project_path`, `file_path`, `find`, `replace`)
- avoid exact user-prompt overlap with prompts_125.yaml

Outputs:
- synthetic_data/rlvr_seed_final_v1.jsonl
- synthetic_data/gold_glyph_3137_plus_rlvr_seed_final_v1.jsonl
- synthetic_data/rlvr_seed_final_v1_report.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "synthetic_data") not in sys.path:
    sys.path.insert(0, str(ROOT / "synthetic_data"))

import yaml

import build_gold50 as g  # noqa: E402
from core.validator import validate_trace  # noqa: E402
from synthetic_data.build_gold_rust_tooluse import (  # noqa: E402
    BIN_BUGFIX_CASES,
    LIB_BUGFIX_CASES,
    SINGLE_TOOL_CASES,
    SYSTEM,
    bin_bug_trace,
    lib_bug_trace,
    rust_dev_tools,
    single_call_trace,
    three_tool_trace,
)


BASE_DATASET = ROOT / "synthetic_data" / "gold_glyph_3000.jsonl"
EVAL_PROMPTS = ROOT / "sft" / "evals" / "prompts_125.yaml"
TOPUP_OUT = ROOT / "synthetic_data" / "rlvr_seed_final_v1.jsonl"
REPORT_OUT = ROOT / "synthetic_data" / "rlvr_seed_final_v1_report.json"


def load_eval_users() -> set[str]:
    data = yaml.safe_load(EVAL_PROMPTS.read_text(encoding="utf-8"))
    rows = data["formal_eval"] if isinstance(data, dict) else data
    return {row["user"] for row in rows}


def read_trace(name: str, user: str, file_path: str, contents: str, response: str, note: str) -> str:
    todos = [
        f"Read {file_path} once.",
        "Answer directly with a clean final response and no extra tool turns.",
    ]
    rationale = "Inspection-only requests should end immediately after the file read and response."
    return g.single_tool_trace(
        SYSTEM,
        rust_dev_tools(),
        user,
        todos,
        rationale,
        "read_file",
        [("file_path", file_path)],
        f"src_{name}",
        contents.replace('"', '\\"'),
        note,
        f"note_{name}",
        response,
    )


def cargo_diag_trace(name: str, user: str, project_path: str, stderr: str, response: str, note: str) -> str:
    todos = [
        f"Run cargo_check on {project_path} to inspect the compiler diagnostic.",
        "Give the first repair direction concisely.",
    ]
    rationale = "One compiler diagnostic is enough when the request is explanatory rather than patching."
    return g.single_tool_trace(
        SYSTEM,
        rust_dev_tools(),
        user,
        todos,
        rationale,
        "cargo_check",
        [("project_path", project_path)],
        f"chk_{name}",
        f"status: failure\\nexit_code: 101\\nstderr: {stderr}",
        note,
        f"note_{name}",
        response,
    )


def strong_bin_trace(
    name: str,
    project_path: str,
    file_path: str,
    source: str,
    find: str,
    replace: str,
    stdout: str,
    response: str,
) -> str:
    user = (
        f'The Cargo binary at "{project_path}" is wrong. Read "{file_path}", apply one precise patch, '
        f'then run cargo_run before replying. The fixed stdout should be "{stdout}".'
    )
    todos = [
        f"Read {file_path} to locate the exact buggy snippet.",
        "Use apply_patch once to replace only that snippet.",
        f"Run cargo_run on {project_path} before answering.",
        "Respond with the verified stdout and the fix in one clean closing response.",
    ]
    rationale = "This workflow should not stop after patching; the verifier call is required before the final response."
    return three_tool_trace(
        user,
        todos,
        rationale,
        "read_file",
        [("file_path", file_path)],
        f"src_{name}",
        source.replace('"', '\\"'),
        "The buggy expression is visible and can be patched with one exact find/replace.",
        f"note_src_{name}",
        "apply_patch",
        [("file_path", file_path), ("find", find), ("replace", replace)],
        f"patch_{name}",
        "status: success\\nexit_code: 0",
        "The patch succeeded, but the task is not complete until cargo_run verifies the new stdout.",
        f"note_patch_{name}",
        "cargo_run",
        [("project_path", project_path)],
        f"run_{name}",
        f"status: success\\nexit_code: 0\\nstdout: {stdout}",
        "cargo_run verified the fix, so the response can close cleanly now.",
        f"note_run_{name}",
        response,
    )


def strong_lib_trace(
    name: str,
    project_path: str,
    file_path: str,
    source: str,
    find: str,
    replace: str,
    response: str,
) -> str:
    user = (
        f'The Cargo crate at "{project_path}" has a failing test. Read "{file_path}", patch the exact bug, '
        f'then run cargo_test before replying.'
    )
    todos = [
        f"Read {file_path} to find the exact buggy code.",
        "Patch the file with one apply_patch call.",
        f"Run cargo_test on {project_path} before answering.",
        "Close with a concise response only after the test run succeeds.",
    ]
    rationale = "The trace should show the full patch-and-verify loop and end only after cargo_test."
    return three_tool_trace(
        user,
        todos,
        rationale,
        "read_file",
        [("file_path", file_path)],
        f"src_{name}",
        source.replace('"', '\\"'),
        "The read_file result exposes the exact buggy text, so a single apply_patch call is enough.",
        f"note_src_{name}",
        "apply_patch",
        [("file_path", file_path), ("find", find), ("replace", replace)],
        f"patch_{name}",
        "status: success\\nexit_code: 0",
        "The patch landed, but the trace should continue to cargo_test before closing.",
        f"note_patch_{name}",
        "cargo_test",
        [("project_path", project_path)],
        f"test_{name}",
        "status: success\\nexit_code: 0\\nstdout: test result: ok",
        "The test verifier succeeded, so the final response can end cleanly.",
        f"note_test_{name}",
        response,
    )


def extract_users(traces: list[str]) -> list[str]:
    users: list[str] = []
    marker = "<|im_start|>user\nuser「"
    end = "」🏷 usr1"
    for trace in traces:
        start = trace.index(marker) + len(marker)
        stop = trace.index(end, start)
        users.append(trace[start:stop])
    return users


def build_traces() -> tuple[list[str], dict[str, int]]:
    traces: list[str] = []
    counts: dict[str, int] = {}

    def add(tag: str, trace: str) -> None:
        traces.append(trace)
        counts[tag] = counts.get(tag, 0) + 1

    for case in LIB_BUGFIX_CASES:
        add("lib_bugfix", lib_bug_trace(*case))

    for case in BIN_BUGFIX_CASES:
        add("bin_bugfix", bin_bug_trace(*case))

    for user, tool_name, args, call_id, result_data, response, thought in SINGLE_TOOL_CASES:
        add("single_tool", single_call_trace(user, tool_name, args, call_id, result_data, response, thought))

    read_cases = [
        (
            "showcase_api",
            'Show the contents of "/workspace/glyph/runs/rlvr1/rust_cases/showcase_lib/src/lib.rs" so I can inspect the public API.',
            "/workspace/glyph/runs/rlvr1/rust_cases/showcase_lib/src/lib.rs",
            'pub fn greet(name: &str) -> String {\\n    format!("Hello, {}!", name)\\n}',
            'Contents of `/workspace/glyph/runs/rlvr1/rust_cases/showcase_lib/src/lib.rs`:\\n\\n```rust\\npub fn greet(name: &str) -> String {\\n    format!("Hello, {}!", name)\\n}\\n```',
            "The file is short, so quoting it directly is the cleanest complete answer.",
        ),
        (
            "inspect_main",
            'Open "/workspace/glyph/runs/rlvr1/rust_cases/inspect_main_app/src/main.rs" and describe what the binary does in one sentence.',
            "/workspace/glyph/runs/rlvr1/rust_cases/inspect_main_app/src/main.rs",
            'fn main() {\\n    let nums = [1, 2, 3, 4];\\n    let sum: i32 = nums.iter().sum();\\n    println!("{sum}");\\n}',
            "The binary sums the array `1, 2, 3, 4` and prints the total.",
            "This is inspection only, so the trace should stop immediately after the clean response.",
        ),
        (
            "option_summary",
            'Read "/workspace/glyph/runs/rlvr1/rust_cases/optionlib/src/lib.rs" and summarize the function briefly.',
            "/workspace/glyph/runs/rlvr1/rust_cases/optionlib/src/lib.rs",
            "pub fn maybe_first(s: &[i32]) -> Option<i32> { s.first().copied() }",
            "The file defines `maybe_first`, which returns the first slice element as `Option<i32>`.",
            "A single read plus a one-line summary is enough.",
        ),
        (
            "rev_bin_behavior",
            'Inspect "/workspace/glyph/runs/rlvr1/rust_cases/rev_bin/src/main.rs" and tell me what the program prints.',
            "/workspace/glyph/runs/rlvr1/rust_cases/rev_bin/src/main.rs",
            'fn main() { let s = "hello"; let r: String = s.chars().rev().collect(); println!("{r}"); }',
            "The program reverses `hello` and prints `olleh`.",
            "The read already determines the output, so no cargo_run call is needed.",
        ),
        (
            "char_count_lib",
            'Read "/workspace/glyph/runs/rlvr1/rust_cases/charcount_lib/src/lib.rs" and tell me what bug the function would avoid by using chars rather than bytes.',
            "/workspace/glyph/runs/rlvr1/rust_cases/charcount_lib/src/lib.rs",
            'pub fn char_count(s: &str) -> usize { s.chars().count() }',
            "It counts Unicode scalar values instead of raw UTF-8 bytes, so multibyte characters are not overcounted.",
            "The answer should end cleanly after the explanation.",
        ),
        (
            "trim_summary",
            'Open "/workspace/glyph/runs/rlvr1/rust_cases/trim_lib/src/lib.rs" and summarize the implementation.',
            "/workspace/glyph/runs/rlvr1/rust_cases/trim_lib/src/lib.rs",
            'pub fn trim_input(s: &str) -> &str { s.trim() }',
            "The function returns the input string slice with leading and trailing whitespace removed.",
            "This request is just file inspection, so one response is enough.",
        ),
        (
            "word_count_main",
            'Read "/workspace/glyph/runs/rlvr1/rust_cases/word_count_app/src/main.rs" and explain what it prints.',
            "/workspace/glyph/runs/rlvr1/rust_cases/word_count_app/src/main.rs",
            'fn main() { let s = "one two three"; println!("{}", s.split_whitespace().count()); }',
            "It counts whitespace-separated words in `one two three` and prints `3`.",
            "The code already reveals the printed value.",
        ),
        (
            "join_dash_lib",
            'Read "/workspace/glyph/runs/rlvr1/rust_cases/join_dash_lib/src/lib.rs" and tell me what separator it uses.',
            "/workspace/glyph/runs/rlvr1/rust_cases/join_dash_lib/src/lib.rs",
            'pub fn join_dash(parts: &[&str]) -> String { parts.join("-") }',
            "It joins the string parts with a dash (`-`) separator.",
            "The response should stop after the direct answer.",
        ),
    ]
    for case in read_cases:
        add("read_response", read_trace(*case))

    diag_cases = [
        (
            "borrow_move",
            "Cargo check says a Rust value was moved and then borrowed later. What is the first thing to inspect?",
            "/workspace/glyph/runs/rlvr1/rust_cases/borrow_move_case",
            "error[E0382]: borrow of moved value: `msg`\\nhelp: consider borrowing or cloning before the move",
            "Inspect the first move site and the later use of the same value. The first fix is usually borrowing instead of moving, cloning if ownership must be retained, or reordering the code so the later borrow happens before the move.",
            "The move/borrow diagnostic is enough to answer without extra tool calls.",
        ),
        (
            "debug_missing",
            "A Rust compile failure now says `Debug` is missing for a type in a derived path. What should I check first?",
            "/workspace/glyph/runs/rlvr1/rust_cases/debug_missing_case",
            "error[E0277]: `WidgetState` doesn't implement `Debug`\\nhelp: add `#[derive(Debug)]` or implement the trait manually",
            "Inspect the type named in the diagnostic and any fields it contains. The first repair is usually adding `#[derive(Debug)]` to the missing type or removing the `Debug` requirement at that call site.",
            "The diagnostic already names the missing trait and likely repair.",
        ),
        (
            "collect_target",
            "Rust compilation now fails around a `collect()` call because the target collection type is unclear. What is the first fix to check?",
            "/workspace/glyph/runs/rlvr1/rust_cases/collect_case",
            "error[E0282]: type annotations needed\\ncannot infer type of the type parameter `B` declared on the method `collect`",
            "Inspect the `collect()` target and add an explicit type where the collection is created. The most direct fix is usually `collect::<Vec<_>>()` or a typed binding on the receiving variable.",
            "A single diagnostic is enough here.",
        ),
        (
            "future_send",
            "A spawned async task now errors because the captured future is not `Send`. What should I inspect first?",
            "/workspace/glyph/runs/rlvr1/rust_cases/not_send_case",
            "error: future cannot be sent between threads safely\\nnote: a captured value is not `Send` across an await",
            "Inspect what non-`Send` value is captured across the await point. The first fix is usually replacing `Rc` or `RefCell` style state with `Arc` or `Mutex`, or moving the non-`Send` value out of the spawned future.",
            "The error already identifies the important class of captured state.",
        ),
        (
            "double_mut",
            "A Rust function now fails because it mutably borrows the same value twice. What is the first refactor angle to check?",
            "/workspace/glyph/runs/rlvr1/rust_cases/double_mut_case",
            "error[E0499]: cannot borrow `buf` as mutable more than once at a time",
            "Inspect where the first mutable borrow stays live. The first refactor angle is usually shortening that borrow's scope, splitting the work into phases, or moving the second mutation after the first borrow ends.",
            "The borrow-checker message already points at the right repair pattern.",
        ),
        (
            "object_safety",
            "A Rust trait object error appeared after adding a generic method to a trait. What should I inspect first?",
            "/workspace/glyph/runs/rlvr1/rust_cases/object_safety_case",
            "error[E0038]: the trait `Runner` cannot be made into an object\\nmethod `run_with<T>` has generic type parameters",
            "Inspect the newly added trait method for generics or `Self`-by-value usage. The first fix is usually moving that method behind `where Self: Sized` or redesigning it so the trait remains object safe.",
            "The generic method is the strongest clue in the diagnostic.",
        ),
        (
            "lifetime_return",
            "A refactored Rust helper now fails because it returns a reference tied to data that does not live long enough. What should I verify first?",
            "/workspace/glyph/runs/rlvr1/rust_cases/return_ref_case",
            "error[E0515]: cannot return reference to local variable `tmp`",
            "Inspect whether the returned reference points at a local temporary. The first fix is usually returning owned data instead, or tying the return reference to an input lifetime that actually outlives the function.",
            "The return-site lifetime problem is already explicit.",
        ),
        (
            "trait_bound",
            "A new generic Rust helper now fails cargo_check because a required trait bound is absent. What should I verify first?",
            "/workspace/glyph/runs/rlvr1/rust_cases/trait_bound_case",
            "error[E0277]: the trait bound `T: Display` is not satisfied",
            "Inspect the generic function signature and the operation that requires the trait. The first fix is usually adding the missing bound on `T` or removing the operation that requires it.",
            "The missing bound and the use site are the key things to inspect.",
        ),
    ]
    for case in diag_cases:
        add("cargo_diag", cargo_diag_trace(*case))

    strong_bin_cases = [
        (
            "bugbin_rev_strong",
            "/workspace/glyph/runs/rlvr1/rust_cases/bugbin_rev",
            "/workspace/glyph/runs/rlvr1/rust_cases/bugbin_rev/src/main.rs",
            'fn main() { let s = "rust"; let r: String = s.chars().collect(); println!("{r}"); }',
            "s.chars().collect()",
            "s.chars().rev().collect()",
            "tsur",
            'I patched `main.rs`, verified it with `cargo_run`, and the fixed stdout is `"tsur"`.',
        ),
        (
            "bugbin_upper_strong",
            "/workspace/glyph/runs/rlvr1/rust_cases/bugbin_upper",
            "/workspace/glyph/runs/rlvr1/rust_cases/bugbin_upper/src/main.rs",
            'fn main() { println!("{}", "rust".to_lowercase()); }',
            "to_lowercase",
            "to_uppercase",
            "RUST",
            'I replaced the lowercase call, ran `cargo_run`, and the program now prints `"RUST"`.',
        ),
        (
            "bugbin_word_strong",
            "/workspace/glyph/runs/rlvr1/rust_cases/bugbin_word",
            "/workspace/glyph/runs/rlvr1/rust_cases/bugbin_word/src/main.rs",
            'fn main() { let s = "one two three"; println!("{}", s.len()); }',
            "s.len()",
            "s.split_whitespace().count()",
            "3",
            'I patched the word-count logic, verified it with `cargo_run`, and stdout is now `"3"`.',
        ),
        (
            "bugbin_filteralpha_strong",
            "/workspace/glyph/runs/rlvr1/rust_cases/bugbin_filteralpha",
            "/workspace/glyph/runs/rlvr1/rust_cases/bugbin_filteralpha/src/main.rs",
            'fn main() { let s = "abc123"; let r: String = s.chars().filter(|c| c.is_alphabetic()).collect(); println!("{}", r); }',
            "is_alphabetic",
            "is_numeric",
            "123",
            'I switched the filter, confirmed it with `cargo_run`, and the corrected stdout is `"123"`.',
        ),
        (
            "bugbin_sum_strong",
            "/workspace/glyph/runs/rlvr1/rust_cases/bugbin_sum",
            "/workspace/glyph/runs/rlvr1/rust_cases/bugbin_sum/src/main.rs",
            'fn main() { let v = [1,2,3,4]; let s: i32 = v.iter().product(); println!("{s}"); }',
            "v.iter().product()",
            "v.iter().sum()",
            "10",
            'I changed the reducer, ran `cargo_run`, and verified the binary now prints `"10"`.',
        ),
        (
            "bugbin_range_strong",
            "/workspace/glyph/runs/rlvr1/rust_cases/bugbin_range",
            "/workspace/glyph/runs/rlvr1/rust_cases/bugbin_range/src/main.rs",
            'fn main() { let s: i32 = (1..10).sum(); println!("{s}"); }',
            "(1..10)",
            "(1..=10)",
            "55",
            'I patched the range bounds, verified them with `cargo_run`, and stdout is `"55"`.',
        ),
    ]
    for case in strong_bin_cases:
        add("strong_bin_bugfix", strong_bin_trace(*case))

    strong_lib_cases = [
        (
            "factlib_strong",
            "/workspace/glyph/runs/rlvr1/rust_cases/factlib_bug",
            "/workspace/glyph/runs/rlvr1/rust_cases/factlib_bug/src/lib.rs",
            "pub fn fact(n: u32) -> u32 { (1..n).product::<u32>().max(1) }\\n\\n#[cfg(test)]\\nmod tests {\\n    use super::*;\\n    #[test] fn t() { /* asserts pass after fix */ }\\n}\\n",
            "1..n",
            "1..=n",
            "I patched the range, verified the crate with `cargo_test`, and the test suite now passes.",
        ),
        (
            "revstrlib_strong",
            "/workspace/glyph/runs/rlvr1/rust_cases/revstrlib_bug",
            "/workspace/glyph/runs/rlvr1/rust_cases/revstrlib_bug/src/lib.rs",
            "pub fn rev(s: &str) -> String { s.chars().collect() }\\n\\n#[cfg(test)]\\nmod tests {\\n    use super::*;\\n    #[test] fn t() { /* asserts pass after fix */ }\\n}\\n",
            "s.chars().collect()",
            "s.chars().rev().collect()",
            "I added the missing reversal, ran `cargo_test`, and the crate now passes its tests.",
        ),
        (
            "sumlib_strong",
            "/workspace/glyph/runs/rlvr1/rust_cases/sumlib_bug",
            "/workspace/glyph/runs/rlvr1/rust_cases/sumlib_bug/src/lib.rs",
            "pub fn sum(s: &[i32]) -> i32 { s.iter().product() }\\n\\n#[cfg(test)]\\nmod tests {\\n    use super::*;\\n    #[test] fn t() { /* asserts pass after fix */ }\\n}\\n",
            "s.iter().product()",
            "s.iter().sum()",
            "I switched the iterator reducer, verified with `cargo_test`, and the crate is green now.",
        ),
        (
            "gcdlib_strong",
            "/workspace/glyph/runs/rlvr1/rust_cases/gcdlib_bug",
            "/workspace/glyph/runs/rlvr1/rust_cases/gcdlib_bug/src/lib.rs",
            "pub fn gcd(a: u32, b: u32) -> u32 { if b == 0 { b } else { gcd(b, a % b) } }\\n\\n#[cfg(test)]\\nmod tests {\\n    use super::*;\\n    #[test] fn t() { /* asserts pass after fix */ }\\n}\\n",
            "if b == 0 { b }",
            "if b == 0 { a }",
            "I corrected the base case, ran `cargo_test`, and the test suite now passes cleanly.",
        ),
        (
            "maxlib_strong",
            "/workspace/glyph/runs/rlvr1/rust_cases/maxlib_bug",
            "/workspace/glyph/runs/rlvr1/rust_cases/maxlib_bug/src/lib.rs",
            "pub fn max_of(s: &[i32]) -> i32 { *s.iter().min().unwrap_or(&0) }\\n\\n#[cfg(test)]\\nmod tests {\\n    use super::*;\\n    #[test] fn t() { /* asserts pass after fix */ }\\n}\\n",
            "s.iter().min()",
            "s.iter().max()",
            "I swapped the iterator method, verified with `cargo_test`, and the crate's tests now pass.",
        ),
        (
            "vowelslib_strong",
            "/workspace/glyph/runs/rlvr1/rust_cases/vowelslib_bug",
            "/workspace/glyph/runs/rlvr1/rust_cases/vowelslib_bug/src/lib.rs",
            "pub fn vowels(s: &str) -> usize { s.chars().filter(|c| \\\"bcdfg\\\".contains(*c)).count() }\\n\\n#[cfg(test)]\\nmod tests {\\n    use super::*;\\n    #[test] fn t() { /* asserts pass after fix */ }\\n}\\n",
            "\\\"bcdfg\\\"",
            "\\\"aeiouAEIOU\\\"",
            "I fixed the filter set, confirmed it with `cargo_test`, and the tests now pass.",
        ),
    ]
    for case in strong_lib_cases:
        add("strong_lib_bugfix", strong_lib_trace(*case))

    return traces, counts


def main() -> int:
    traces, counts = build_traces()
    eval_users = load_eval_users()
    dataset_users = extract_users(traces)
    overlaps = sorted(set(dataset_users) & eval_users)
    base_rows = sum(1 for row in BASE_DATASET.read_text(encoding="utf-8").splitlines() if row.strip())
    combined_out = ROOT / "synthetic_data" / f"gold_glyph_{base_rows + len(traces)}_plus_rlvr_seed_final_v1.jsonl"

    invalid: list[dict[str, object]] = []
    for idx, trace in enumerate(traces):
        result = validate_trace(trace)
        if not result.valid:
            invalid.append({"index": idx, "errors": result.errors[:5]})

    if invalid:
        print(json.dumps({"invalid": invalid[:10], "count": len(invalid)}, indent=2))
        return 1

    if overlaps:
        print(json.dumps({"exact_prompt_overlaps": overlaps[:10], "count": len(overlaps)}, indent=2))
        return 1

    with TOPUP_OUT.open("w", encoding="utf-8") as f:
        for trace in traces:
            f.write(json.dumps({"trace": trace}, ensure_ascii=False) + "\n")

    combined_rows = BASE_DATASET.read_text(encoding="utf-8").splitlines()
    with combined_out.open("w", encoding="utf-8") as f:
        for row in combined_rows:
            if row.strip():
                f.write(row + "\n")
        for trace in traces:
            f.write(json.dumps({"trace": trace}, ensure_ascii=False) + "\n")

    report = {
        "topup_file": str(TOPUP_OUT.relative_to(ROOT)),
        "combined_file": str(combined_out.relative_to(ROOT)),
        "base_rows": base_rows,
        "topup_rows": len(traces),
        "combined_rows": base_rows + len(traces),
        "counts": counts,
        "exact_prompt_overlap_count": 0,
    }
    REPORT_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
