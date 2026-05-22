#!/usr/bin/env python3
"""SFT extension: traces for the full RL Rust toolset.

Adds gold examples of:
  read_file → response (inspect a file)
  read_file → apply_patch → cargo_test → response (lib bug fix)
  read_file → apply_patch → cargo_run → response (bin bug fix)
  cargo_check / cargo_build / cargo_test / cargo_run / rustc — single-tool

The output appends to gold_glyph_2500.jsonl so the next SFT run sees the
correct schema for tools the original SFT pool didn't cover (`apply_patch`,
`read_file`, `cargo_build`, `cargo_run`, `rustc`). Format follows the
build_gold50 helpers strictly so docs/glyph.md invariants hold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import build_gold50 as g  # noqa: E402
from core.validator import validate_trace  # noqa: E402


# ---------------------------------------------------------------------------
# Tool defs — must match rl/rust/tools.py exactly so the model learns the
# right schema (file_path/find/replace for apply_patch, not source_file/source).
# ---------------------------------------------------------------------------

def rust_dev_tools():
    return [
        g.tool("read_file",
               "Reads a file from disk and returns its contents.",
               g.param("file_path", "string", "Path to the file to read")),
        g.tool("apply_patch",
               "Applies a textual find/replace edit to a single file. 'find' must occur exactly once.",
               g.param("file_path", "string", "Path to the file to edit"),
               g.param("find", "string", "Exact text snippet to locate"),
               g.param("replace", "string", "Replacement text")),
        g.tool("cargo_check",
               "Runs cargo check to verify code compiles without producing a binary.",
               g.param("project_path", "string", "Cargo project directory")),
        g.tool("cargo_build",
               "Compiles the Cargo project into binaries.",
               g.param("project_path", "string", "Cargo project directory")),
        g.tool("cargo_test",
               "Runs the test suite for a Cargo project.",
               g.param("project_path", "string", "Cargo project directory")),
        g.tool("cargo_run",
               "Builds and runs the binary of a Cargo project, returning its stdout.",
               g.param("project_path", "string", "Cargo project directory")),
        g.tool("rustc",
               "Compiles a single Rust source file to an executable.",
               g.param("source_file", "string", "Source file"),
               g.param("output", "string", "Output binary path", required=False)),
    ]


SYSTEM = "You are a Rust engineering assistant. Use the available tools to inspect and verify code, then answer briefly."


# ---------------------------------------------------------------------------
# Trace builders for multi-step workflows (3+ calls).
# Mirrors single_tool_trace / multi_tool_trace from build_gold50 but extends
# to 3 sequential calls (read → patch → verify).
# ---------------------------------------------------------------------------

def three_tool_trace(user, todos, rationale,
                     c1_tool, c1_args, c1_id, r1, t1, tag1,
                     c2_tool, c2_args, c2_id, r2, t2, tag2,
                     c3_tool, c3_args, c3_id, r3, t3, tag3,
                     response):
    """assistant → tool → assistant → tool → assistant → tool → assistant(response)"""
    return g.join_trace(
        g.system_seg(SYSTEM, rust_dev_tools()),
        g.user_seg(user),
        g.assistant_seg(g.plan_block(todos, rationale),
                        g.call_act(c1_tool, c1_args, c1_id, 1)),
        g.result_seg(r1, c1_id),
        g.assistant_seg(g.think_act([(t1, tag1, [c1_id])]),
                        g.call_act(c2_tool, c2_args, c2_id, 2)),
        g.result_seg(r2, c2_id),
        g.assistant_seg(g.think_act([(t2, tag2, [c1_id, c2_id])]),
                        g.call_act(c3_tool, c3_args, c3_id, 3)),
        g.result_seg(r3, c3_id),
        g.assistant_seg(g.think_act([(t3, tag3, [c2_id, c3_id])]),
                        g.response_block(response, [c1_id, c2_id, c3_id, tag3], 4)),
    )


# ---------------------------------------------------------------------------
# Concrete bug-fix lib traces: read_file → apply_patch → cargo_test → respond.
# These mirror the rl/rust/prepare_cases.py BUGFIX_CASES so the SFT model
# sees the exact workflow the RL env expects.
# ---------------------------------------------------------------------------

LIB_BUGFIX_CASES = [
    # (crate, buggy_lib_src, find, replace, fix_summary)
    ("addlib_bug",
     "pub fn add(a: i32, b: i32) -> i32 { a - b }",
     "a - b", "a + b",
     "Subtraction was used where addition is required; replacing it makes the test pass."),
    ("mullib_bug",
     "pub fn mul(a: i32, b: i32) -> i32 { a + b }",
     "a + b", "a * b",
     "Addition was used where multiplication is required; the corrected operator matches the test."),
    ("evenlib_bug",
     "pub fn is_even(n: i32) -> bool { n % 2 == 1 }",
     "n % 2 == 1", "n % 2 == 0",
     "The remainder check was inverted; comparing against 0 returns the correct parity."),
    ("absnumlib_bug",
     "pub fn abs_v(n: i32) -> i32 { n }",
     "pub fn abs_v(n: i32) -> i32 { n }",
     "pub fn abs_v(n: i32) -> i32 { n.abs() }",
     "The function returned the input unchanged; applying .abs() yields the absolute value."),
    ("factlib_bug",
     "pub fn fact(n: u32) -> u32 { (1..n).product::<u32>().max(1) }",
     "1..n", "1..=n",
     "The exclusive range skipped n; using an inclusive range gives the correct factorial."),
    ("revstrlib_bug",
     "pub fn rev(s: &str) -> String { s.chars().collect() }",
     "s.chars().collect()", "s.chars().rev().collect()",
     "The chars iterator wasn't reversed; calling .rev() before collecting fixes the result."),
    ("maxlib_bug",
     "pub fn max_of(s: &[i32]) -> i32 { *s.iter().min().unwrap_or(&0) }",
     "s.iter().min()", "s.iter().max()",
     "Selecting min instead of max; swapping the iterator method gives the expected value."),
    ("sumlib_bug",
     "pub fn sum(s: &[i32]) -> i32 { s.iter().product() }",
     "s.iter().product()", "s.iter().sum()",
     "Iterator product was used where sum is required; switching makes the test pass."),
    ("fiblib_bug",
     "pub fn fib(n: u32) -> u32 { match n { 0 => 1, 1 => 1, _ => fib(n-1) + fib(n-2) } }",
     "0 => 1", "0 => 0",
     "fib(0) was returning 1; correcting the base case to 0 matches the standard sequence."),
    ("palinlib_bug",
     "pub fn pal(s: &str) -> bool { let r: String = s.chars().collect(); r == s }",
     "s.chars().collect()", "s.chars().rev().collect()",
     "The string wasn't reversed before the equality check; adding .rev() makes palindrome detection work."),
    ("vowelslib_bug",
     "pub fn vowels(s: &str) -> usize { s.chars().filter(|c| \"bcdfg\".contains(*c)).count() }",
     "\"bcdfg\"", "\"aeiouAEIOU\"",
     "The filter set listed consonants; using the vowels set returns the correct count."),
    ("gcdlib_bug",
     "pub fn gcd(a: u32, b: u32) -> u32 { if b == 0 { b } else { gcd(b, a % b) } }",
     "if b == 0 { b }", "if b == 0 { a }",
     "The base case returned 0 instead of a; correcting it makes the recursion terminate with the right value."),
]


def lib_bug_trace(crate, buggy_src, find, replace, summary):
    project_path = f"/workspace/glyph/runs/rlvr1/rust_cases/{crate}"
    file_path = f"{project_path}/src/lib.rs"
    full_src_for_read = (
        f"{buggy_src}\n\n#[cfg(test)]\nmod tests {{\n    use super::*;\n    #[test] fn t() {{ /* asserts pass after fix */ }}\n}}\n"
    )
    user = (
        f'The Cargo project at "{project_path}" has a failing test. Read the source at '
        f'"{file_path}" first, then apply a one-line patch and verify with cargo_test.'
    )
    todos = [
        f"Read the source at {file_path} to find the buggy snippet.",
        f"Use apply_patch to replace the buggy text with the correct version.",
        f"Run cargo_test on {project_path} to confirm the fix.",
    ]
    rationale = "Inspect the file before patching so the find string exactly matches the source, then verify."
    return three_tool_trace(
        user, todos, rationale,
        "read_file", [("file_path", file_path)], "src1",
        full_src_for_read.replace('"', '\\"'),
        "The buggy line is visible in the source; the targeted snippet matches exactly once.",
        "note_src",
        "apply_patch",
        [("file_path", file_path), ("find", find), ("replace", replace)],
        "patch1",
        "status: success\\nexit_code: 0",
        "Patch applied cleanly; the source now contains the corrected expression.",
        "note_patched",
        "cargo_test", [("project_path", project_path)], "test1",
        "status: success\\nexit_code: 0\\nstdout: test result: ok",
        f"cargo_test passes after the fix. {summary}",
        "note_verified",
        summary,
    )


# ---------------------------------------------------------------------------
# Bin-crate bug-fix traces: read_file → apply_patch → cargo_run → respond.
# ---------------------------------------------------------------------------

BIN_BUGFIX_CASES = [
    ("bugbin_hello",
     'fn main() { println!("goodbye"); }',
     '"goodbye"', '"hello"', "hello",
     "The greeting string was wrong; replacing it produces the expected stdout."),
    ("bugbin_sum",
     'fn main() { let v = [1,2,3,4]; let s: i32 = v.iter().product(); println!("{s}"); }',
     "v.iter().product()", "v.iter().sum()", "10",
     "The reducer was product instead of sum; switching gives the expected total."),
    ("bugbin_double",
     'fn main() { let x = 7; println!("{}", x + 2); }',
     "x + 2", "x * 2", "14",
     "Addition was used where doubling was required; the multiplication fixes the output."),
    ("bugbin_count",
     'fn main() { for n in 1..5 { print!("{n} "); } println!(); }',
     "1..5", "1..=5", "1 2 3 4 5",
     "The exclusive range omitted 5; making it inclusive prints the full sequence."),
    ("bugbin_upper",
     'fn main() { println!("{}", "rust".to_lowercase()); }',
     "to_lowercase", "to_uppercase", "RUST",
     "The wrong case method was used; to_uppercase produces the expected output."),
    ("bugbin_rev",
     'fn main() { let s = "rust"; let r: String = s.chars().collect(); println!("{r}"); }',
     "s.chars().collect()", "s.chars().rev().collect()", "tsur",
     "The chars iterator wasn't reversed; adding .rev() yields the reversed string."),
    ("bugbin_square",
     'fn main() { for n in 1..=4 { print!("{} ", n + n); } println!(); }',
     "n + n", "n * n", "1 4 9 16",
     "The expression doubled rather than squared; multiplying n by itself fixes the output."),
    ("bugbin_word",
     'fn main() { let s = "one two three"; println!("{}", s.len()); }',
     "s.len()", "s.split_whitespace().count()", "3",
     "Byte length was returned instead of word count; switching to split_whitespace().count() fixes it."),
]


def bin_bug_trace(crate, buggy_src, find, replace, expected_stdout, summary):
    project_path = f"/workspace/glyph/runs/rlvr1/rust_cases/{crate}"
    file_path = f"{project_path}/src/main.rs"
    user = (
        f'The Cargo binary at "{project_path}" prints the wrong output. Read "{file_path}", '
        f'patch it, then verify with cargo_run — expected stdout is "{expected_stdout}".'
    )
    todos = [
        f"Read {file_path} to locate the buggy expression.",
        f"Apply a one-line patch to correct it.",
        f"Run cargo_run on {project_path} and confirm the stdout matches.",
    ]
    rationale = "Inspect first so the apply_patch find string matches the source verbatim, then verify by running the binary."
    return three_tool_trace(
        user, todos, rationale,
        "read_file", [("file_path", file_path)], "src1",
        buggy_src.replace('"', '\\"'),
        "The buggy snippet is visible and occurs exactly once in main.rs.",
        "note_src",
        "apply_patch",
        [("file_path", file_path), ("find", find), ("replace", replace)],
        "patch1",
        "status: success\\nexit_code: 0",
        "Patch applied; main.rs now uses the corrected expression.",
        "note_patched",
        "cargo_run", [("project_path", project_path)], "run1",
        f"status: success\\nexit_code: 0\\nstdout: {expected_stdout}",
        f"cargo_run output matches the expected stdout. {summary}",
        "note_verified",
        f"Fixed the source and confirmed by cargo_run; output is \\\"{expected_stdout}\\\". {summary}",
    )


# ---------------------------------------------------------------------------
# Single-tool traces for tools missing from the original SFT pool:
# cargo_build, cargo_run, rustc, plus read_file (info-only).
# ---------------------------------------------------------------------------

def single_call_trace(user, tool_name, args, call_id, result_data, response, fix_summary_thought):
    return g.single_tool_trace(
        SYSTEM, rust_dev_tools(), user,
        [
            f"Run {tool_name} to satisfy the user's request.",
            "Report the outcome briefly.",
        ],
        "Use one verifier call, then summarize the outcome.",
        tool_name, args, call_id,
        result_data,
        fix_summary_thought, f"note_{tool_name}",
        response,
    )


SINGLE_TOOL_CASES = [
    # cargo_build
    ("Compile the Cargo binary project at \"/workspace/glyph/runs/rlvr1/rust_cases/greeter2\".",
     "cargo_build",
     [("project_path", "/workspace/glyph/runs/rlvr1/rust_cases/greeter2")],
     "build1",
     "status: success\\nexit_code: 0\\nstdout: Compiling greeter2 v0.1.0\\nFinished `dev` profile",
     "cargo_build succeeded; the binary is built in target/debug/.",
     "The build completed; the project compiles cleanly and produces a debug binary."),
    ("Build the Cargo project at \"/workspace/glyph/runs/rlvr1/rust_cases/counter2\".",
     "cargo_build",
     [("project_path", "/workspace/glyph/runs/rlvr1/rust_cases/counter2")],
     "build1",
     "status: success\\nexit_code: 0\\nstdout: Compiling counter2 v0.1.0\\nFinished `dev` profile",
     "cargo_build finished without errors; the artifact lives in target/debug/.",
     "The build is green and the binary is ready for execution."),
    # cargo_run
    ("Run the Cargo binary at \"/workspace/glyph/runs/rlvr1/rust_cases/greeter2\" and report its stdout.",
     "cargo_run",
     [("project_path", "/workspace/glyph/runs/rlvr1/rust_cases/greeter2")],
     "run1",
     "status: success\\nexit_code: 0\\nstdout: hello",
     "cargo_run printed 'hello'; the binary works as expected.",
     "The program ran successfully and printed: hello."),
    ("Execute the Cargo binary at \"/workspace/glyph/runs/rlvr1/rust_cases/counter2\".",
     "cargo_run",
     [("project_path", "/workspace/glyph/runs/rlvr1/rust_cases/counter2")],
     "run1",
     "status: success\\nexit_code: 0\\nstdout: 1\\n2\\n3\\n4\\n5",
     "cargo_run printed the numbers 1..5 one per line.",
     "The program ran successfully and produced the expected sequence 1..5."),
    # cargo_check
    ("Run cargo_check on the project at \"/workspace/glyph/runs/rlvr1/rust_cases/mathlib2\".",
     "cargo_check",
     [("project_path", "/workspace/glyph/runs/rlvr1/rust_cases/mathlib2")],
     "chk1",
     "status: success\\nexit_code: 0\\nstdout: Checking mathlib2 v0.1.0\\nFinished",
     "cargo_check passed; no compile errors.",
     "The crate type-checks cleanly."),
    # rustc
    ("Compile \"/workspace/glyph/runs/rlvr1/rust_cases/hello2.rs\" to the binary \"/workspace/glyph/runs/rlvr1/rust_cases/hello2_bin\".",
     "rustc",
     [("source_file", "/workspace/glyph/runs/rlvr1/rust_cases/hello2.rs"),
      ("output", "/workspace/glyph/runs/rlvr1/rust_cases/hello2_bin")],
     "rc1",
     "status: success\\nexit_code: 0\\nstdout:",
     "rustc compiled the single source file to the requested output path.",
     "The source compiled without errors."),
    # read_file (info-gathering only)
    ("Show the contents of \"/workspace/glyph/runs/rlvr1/rust_cases/mathlib2/src/lib.rs\".",
     "read_file",
     [("file_path", "/workspace/glyph/runs/rlvr1/rust_cases/mathlib2/src/lib.rs")],
     "src1",
     "pub fn add(a: i32, b: i32) -> i32 { a + b }",
     "The file defines a single public add function returning the sum of two i32 values.",
     "The file at that path defines `pub fn add(a: i32, b: i32) -> i32 { a + b }`."),
    ("Read \"/workspace/glyph/runs/rlvr1/rust_cases/strutils/src/lib.rs\" and tell me what it does.",
     "read_file",
     [("file_path", "/workspace/glyph/runs/rlvr1/rust_cases/strutils/src/lib.rs")],
     "src1",
     "pub fn shout(s: &str) -> String { s.to_uppercase() }",
     "The file exposes one public function that uppercases its &str input.",
     "The file defines `pub fn shout(s: &str) -> String { s.to_uppercase() }`, which uppercases input."),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_traces() -> list[str]:
    traces: list[str] = []
    for case in LIB_BUGFIX_CASES:
        traces.append(lib_bug_trace(*case))
    for case in BIN_BUGFIX_CASES:
        traces.append(bin_bug_trace(*case))
    for case in SINGLE_TOOL_CASES:
        traces.append(single_call_trace(*case))
    return traces


def main() -> int:
    traces = build_traces()
    invalid = 0
    for i, t in enumerate(traces):
        v = validate_trace(t)
        if not v.valid:
            invalid += 1
            print(f"trace {i} INVALID: {v.errors[:3]}")
            if invalid <= 2:
                print(t[:1200])
                print("...")
    if invalid:
        print(f"\n{invalid}/{len(traces)} traces failed validation; aborting append.")
        return 1
    out = Path(__file__).parent / "gold_glyph_2500.jsonl"
    existing = out.read_text(encoding="utf-8").count("\n") if out.exists() else 0
    with out.open("a", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps({"trace": t}, ensure_ascii=False) + "\n")
    final = out.read_text(encoding="utf-8").count("\n")
    print(f"appended {len(traces)} traces to {out} ({existing} → {final} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
