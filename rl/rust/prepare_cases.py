#!/usr/bin/env python3
"""Generate Rust tool-use RL cases (real cargo/rustc execution) + optional
structure-only prompts from the SFT gold pool.

Each Rust case is materialized as a Cargo project (or .rs file) under --root,
and emitted as one or more prompt JSONL rows carrying `expected_tool` and
`expected_args`. The reward path with those fields hits real `compute_tool_reward`.

Structure-only rows come from gold_glyph_3000.jsonl with no `expected_tool` and
are scored by the validator term only. They are NEVER from prompts_125.yaml.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from sft.evals.prompt_loader import build_prompt
from rl.rust.tools import RUST_TOOLS as _RUST_TOOLS


RUST_TOOLS: list[dict] = [
    {"name": t.name, "description": t.description, "params": t.params}
    for t in _RUST_TOOLS
]


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def cargo_toml(name: str) -> str:
    return f'[package]\nname = "{name}"\nversion = "0.1.0"\nedition = "2021"\n'


# ---------------------------------------------------------------------------
# Per-tool case definitions
# ---------------------------------------------------------------------------

# Small coverage pool — bug-free crates so the model practices the other
# Rust tools (cargo_check, cargo_build, rustc). Bug-fix lib cases already
# exercise cargo_test, so we don't ship a separate passing-test pool here.

# (crate_name, lib body) — lib-only crates for cargo_check.
CARGO_CHECK_LIBS: list[tuple[str, str]] = [
    ("mathlib2", "pub fn add(a: i32, b: i32) -> i32 { a + b }"),
    ("parserlib2", "pub fn first_word(s: &str) -> &str { s.split_whitespace().next().unwrap_or(\"\") }"),
    ("strutils", "pub fn shout(s: &str) -> String { s.to_uppercase() }"),
    ("optionlib", "pub fn maybe_first(s: &[i32]) -> Option<i32> { s.first().copied() }"),
    ("sortlib2", "pub fn sorted(mut v: Vec<i32>) -> Vec<i32> { v.sort(); v }"),
]


# (crate_name, main body) — bin crates for cargo_build.
CARGO_BUILD_BINS: list[tuple[str, str]] = [
    ("greeter2", 'fn main() { println!("hello"); }'),
    ("counter2", 'fn main() { for v in 1..=5 { println!("{v}"); } }'),
    ("calcbin", 'fn main() { let (a, b) = (12, 30); println!("{}", a + b); }'),
    ("squarebin", 'fn main() { for n in 1..=5 { println!("{}", n * n); } }'),
    ("uppercase", 'fn main() { let s = "hello world"; println!("{}", s.to_uppercase()); }'),
]


# (crate, buggy_lib, test, find_snippet, replace_snippet, bug_hint)
# Each case ships a crate whose test FAILS until apply_patch replaces `find` with
# `replace`. After patching, cargo_test should pass. Reward gets the apply_patch
# success + the subsequent cargo_test success.
BUGFIX_CASES: list[tuple[str, str, str, str, str, str]] = [
    ("bugadd", "pub fn add(a: i32, b: i32) -> i32 { a - b }",
     "use super::add; #[test] fn t() { assert_eq!(add(2, 3), 5); }",
     "a - b", "a + b", "subtraction used where addition is needed"),
    ("bugmul", "pub fn mul(a: i32, b: i32) -> i32 { a + b }",
     "use super::mul; #[test] fn t() { assert_eq!(mul(4, 5), 20); }",
     "a + b", "a * b", "addition used where multiplication is needed"),
    ("bugeven", "pub fn is_even(n: i32) -> bool { n % 2 == 1 }",
     "use super::is_even; #[test] fn t() { assert!(is_even(4) && !is_even(3)); }",
     "n % 2 == 1", "n % 2 == 0", "wrong remainder check"),
    ("bugabs", "pub fn abs_v(n: i32) -> i32 { n }",
     "use super::abs_v; #[test] fn t() { assert_eq!(abs_v(-7), 7); }",
     "pub fn abs_v(n: i32) -> i32 { n }",
     "pub fn abs_v(n: i32) -> i32 { n.abs() }",
     "abs not applied"),
    ("bugfact", "pub fn fact(n: u32) -> u32 { (1..n).product::<u32>().max(1) }",
     "use super::fact; #[test] fn t() { assert_eq!(fact(5), 120); }",
     "1..n", "1..=n", "exclusive range used instead of inclusive"),
    ("bugrev", "pub fn rev(s: &str) -> String { s.chars().collect() }",
     "use super::rev; #[test] fn t() { assert_eq!(rev(\"abc\"), \"cba\"); }",
     "s.chars().collect()", "s.chars().rev().collect()", "rev() missing"),
    ("bugmaxslice", "pub fn max_of(s: &[i32]) -> i32 { *s.iter().min().unwrap_or(&0) }",
     "use super::max_of; #[test] fn t() { assert_eq!(max_of(&[3,1,5,2]), 5); }",
     "s.iter().min()", "s.iter().max()", "min used instead of max"),
    ("bugsum", "pub fn sum(s: &[i32]) -> i32 { s.iter().product() }",
     "use super::sum; #[test] fn t() { assert_eq!(sum(&[1,2,3,4]), 10); }",
     "s.iter().product()", "s.iter().sum()", "product used instead of sum"),
    ("bugfib", "pub fn fib(n: u32) -> u32 { match n { 0 => 1, 1 => 1, _ => fib(n-1) + fib(n-2) } }",
     "use super::fib; #[test] fn t() { assert_eq!(fib(10), 55); }",
     "0 => 1", "0 => 0", "wrong base case for fib(0)"),
    ("bugpalin", "pub fn pal(s: &str) -> bool { let r: String = s.chars().collect(); r == s }",
     "use super::pal; #[test] fn t() { assert!(pal(\"racecar\") && !pal(\"rust\")); }",
     "s.chars().collect()", "s.chars().rev().collect()", "rev() missing"),
    ("bugvowels", "pub fn vowels(s: &str) -> usize { s.chars().filter(|c| \"bcdfg\".contains(*c)).count() }",
     "use super::vowels; #[test] fn t() { assert_eq!(vowels(\"hello\"), 2); }",
     "\"bcdfg\"", "\"aeiouAEIOU\"", "consonants used instead of vowels"),
    ("buggcd", "pub fn gcd(a: u32, b: u32) -> u32 { if b == 0 { b } else { gcd(b, a % b) } }",
     "use super::gcd; #[test] fn t() { assert_eq!(gcd(48, 18), 6); }",
     "if b == 0 { b }", "if b == 0 { a }", "wrong base-case return"),
    ("bugclamp", "pub fn clamp(v: i32, lo: i32, hi: i32) -> i32 { v.min(lo).max(hi) }",
     "use super::clamp; #[test] fn t() { assert_eq!(clamp(10, 0, 5), 5); }",
     "v.min(lo).max(hi)", "v.max(lo).min(hi)", "min/max swapped"),
    ("bugpow2", "pub fn is_pow2(n: u32) -> bool { n > 0 && (n & n) == 0 }",
     "use super::is_pow2; #[test] fn t() { assert!(is_pow2(16) && !is_pow2(18)); }",
     "(n & n)", "(n & (n-1))", "wrong bit trick"),
    ("bugcube", "pub fn cube(n: i64) -> i64 { n * n }",
     "use super::cube; #[test] fn t() { assert_eq!(cube(3), 27); }",
     "pub fn cube(n: i64) -> i64 { n * n }",
     "pub fn cube(n: i64) -> i64 { n * n * n }",
     "squared instead of cubed"),
    ("bugwc", "pub fn wc(s: &str) -> usize { s.len() }",
     "use super::wc; #[test] fn t() { assert_eq!(wc(\"a b c d\"), 4); }",
     "s.len()", "s.split_whitespace().count()", "byte length used instead of word count"),
    ("bugavg", "pub fn avg(s: &[f64]) -> f64 { s.iter().sum::<f64>() }",
     "use super::avg; #[test] fn t() { assert!((avg(&[1.0,2.0,3.0]) - 2.0).abs() < 1e-9); }",
     "s.iter().sum::<f64>()", "s.iter().sum::<f64>() / s.len() as f64", "forgot to divide by length"),
    ("bugfizz", "pub fn fizz(n: u32) -> String { match (n%3, n%5) { (0,0) => \"FizzBuzz\".into(), (0,_) => \"Buzz\".into(), (_,0) => \"Fizz\".into(), _ => n.to_string() } }",
     "use super::fizz; #[test] fn t() { assert_eq!(fizz(15), \"FizzBuzz\"); assert_eq!(fizz(3), \"Fizz\"); }",
     "(0,_) => \"Buzz\".into(), (_,0) => \"Fizz\".into()",
     "(0,_) => \"Fizz\".into(), (_,0) => \"Buzz\".into()",
     "Fizz and Buzz swapped"),
    ("bugsortlib", "pub fn sorted(mut v: Vec<i32>) -> Vec<i32> { v }",
     "use super::sorted; #[test] fn t() { assert_eq!(sorted(vec![3,1,2]), vec![1,2,3]); }",
     "pub fn sorted(mut v: Vec<i32>) -> Vec<i32> { v }",
     "pub fn sorted(mut v: Vec<i32>) -> Vec<i32> { v.sort(); v }",
     "sort() call missing"),
    ("bugdedup", "pub fn dedup(mut v: Vec<i32>) -> Vec<i32> { v.dedup(); v }",
     "use super::dedup; #[test] fn t() { assert_eq!(dedup(vec![3,1,2,1,3]), vec![1,2,3]); }",
     "v.dedup(); v", "v.sort(); v.dedup(); v",
     "sort() missing — dedup only removes adjacent duplicates"),
    ("bugfirst", "pub fn first_word(s: &str) -> &str { s.split_whitespace().last().unwrap_or(\"\") }",
     "use super::first_word; #[test] fn t() { assert_eq!(first_word(\"alpha beta\"), \"alpha\"); }",
     ".last()", ".next()", "last used instead of next"),
    ("bugrange", "pub fn in_range(v: i32, lo: i32, hi: i32) -> bool { v > lo && v < hi }",
     "use super::in_range; #[test] fn t() { assert!(in_range(5, 0, 5) && !in_range(6, 0, 5)); }",
     "v > lo && v < hi", "v >= lo && v <= hi", "exclusive bounds used instead of inclusive"),
    ("bugparseu", "pub fn parse_u(s: &str) -> Result<u32, std::num::ParseIntError> { Ok(0) }",
     "use super::parse_u; #[test] fn t() { assert_eq!(parse_u(\"42\").unwrap(), 42); }",
     "Ok(0)", "s.parse()", "stub return — never actually parses"),
    ("bugarea", "pub enum Shape { Circle(f64), Square(f64) } pub fn area(s: &Shape) -> f64 { match s { Shape::Circle(r) => 2.0 * std::f64::consts::PI * r, Shape::Square(a) => a * a } }",
     "use super::{Shape, area}; #[test] fn t() { assert!((area(&Shape::Circle(2.0)) - 4.0 * std::f64::consts::PI).abs() < 1e-9); }",
     "2.0 * std::f64::consts::PI * r", "std::f64::consts::PI * r * r",
     "circumference formula used instead of area"),
]


# Bin-crate bug-fix cases: buggy main.rs prints the wrong thing; canonical patch
# fixes it; verifier is `cargo_run` with expected stdout.
# (crate, buggy_main, find, replace, expected_stdout, bug_hint)
BUGFIX_BIN_CASES: list[tuple[str, str, str, str, str, str]] = [
    ("bugbin_hello", 'fn main() { println!("goodbye"); }',
     '"goodbye"', '"hello"', "hello", "prints wrong greeting"),
    ("bugbin_sum", 'fn main() { let v = [1,2,3,4]; let s: i32 = v.iter().product(); println!("{s}"); }',
     "v.iter().product()", "v.iter().sum()", "10", "product used instead of sum"),
    ("bugbin_double", 'fn main() { let x = 7; println!("{}", x + 2); }',
     "x + 2", "x * 2", "14", "addition used where multiplication is needed"),
    ("bugbin_count", 'fn main() { for n in 1..5 { print!("{n} "); } println!(); }',
     "1..5", "1..=5", "1 2 3 4 5", "exclusive range used instead of inclusive"),
    ("bugbin_upper", 'fn main() { println!("{}", "rust".to_lowercase()); }',
     "to_lowercase", "to_uppercase", "RUST", "wrong case method"),
    ("bugbin_rev", 'fn main() { let s = "rust"; let r: String = s.chars().collect(); println!("{r}"); }',
     "s.chars().collect()", "s.chars().rev().collect()", "tsur", "rev() missing"),
    ("bugbin_square", 'fn main() { for n in 1..=4 { print!("{} ", n + n); } println!(); }',
     "n + n", "n * n", "1 4 9 16", "addition used where squaring is needed"),
    ("bugbin_range", 'fn main() { let s: i32 = (1..10).sum(); println!("{s}"); }',
     "(1..10)", "(1..=10)", "55", "exclusive range used instead of inclusive"),
    ("bugbin_word", 'fn main() { let s = "one two three"; println!("{}", s.len()); }',
     "s.len()", "s.split_whitespace().count()", "3", "byte length used instead of word count"),
    ("bugbin_fib", 'fn main() { let (mut a, mut b) = (1u64, 1u64); for _ in 0..6 { print!("{a} "); let t = a + b; a = b; b = t; } println!(); }',
     "(1u64, 1u64)", "(0u64, 1u64)", "0 1 1 2 3 5", "wrong fib starting values"),
]


# (filename without extension, source body) — standalone .rs files for rustc.
RUSTC_FILES: list[tuple[str, str]] = [
    ("hello2", 'fn main() { println!("hi"); }'),
    ("sum2", 'fn main() { let v = [1,2,3,4]; let s: i32 = v.iter().sum(); println!("{s}"); }'),
    ("doublerust", 'fn main() { let x = 7; println!("{}", x * 2); }'),
    ("uppercasers", 'fn main() { println!("{}", "hello".to_uppercase()); }'),
    ("matchrust", 'fn main() { let n = 4; let lbl = if n % 2 == 0 { "even" } else { "odd" }; println!("{lbl}"); }'),
]


# ---------------------------------------------------------------------------
# Materialize cases on disk
# ---------------------------------------------------------------------------

def emit_check_case(root: Path, name: str, lib: str) -> dict:
    project = root / name
    write(project / "Cargo.toml", cargo_toml(name))
    write(project / "src" / "lib.rs", lib + "\n")
    return {
        "expected_tool": "cargo_check",
        "expected_args": {"project_path": str(project)},
        "_path": str(project),
    }


def emit_build_case(root: Path, name: str, main_src: str) -> dict:
    project = root / name
    write(project / "Cargo.toml", cargo_toml(name))
    write(project / "src" / "main.rs", main_src + "\n")
    return {
        "expected_tool": "cargo_build",
        "expected_args": {"project_path": str(project)},
        "_path": str(project),
    }


def emit_bugfix_case(
    root: Path, name: str, buggy_lib: str, test: str,
    find: str, replace: str, hint: str,
) -> dict:
    project = root / name
    write(project / "Cargo.toml", cargo_toml(name))
    write(
        project / "src" / "lib.rs",
        f"{buggy_lib}\n\n#[cfg(test)]\nmod tests {{\n    {test}\n}}\n",
    )
    return {
        "expected_tool": "apply_patch",
        "expected_args": {
            "file_path": str(project / "src" / "lib.rs"),
            "find": find,
            "replace": replace,
        },
        "blueprint_root": str(project),
        "bug_hint": hint,
        "_path": str(project),
    }


def emit_bugfix_bin_case(
    root: Path, name: str, buggy_main: str, find: str, replace: str,
    expected_stdout: str, hint: str,
) -> dict:
    project = root / name
    write(project / "Cargo.toml", cargo_toml(name))
    write(project / "src" / "main.rs", buggy_main + "\n")
    return {
        "expected_tool": "apply_patch",
        "expected_args": {
            "file_path": str(project / "src" / "main.rs"),
            "find": find,
            "replace": replace,
        },
        "expected_output": expected_stdout,
        "blueprint_root": str(project),
        "bug_hint": hint,
        "_path": str(project),
    }


def emit_rustc_case(root: Path, name: str, body: str) -> dict:
    src = root / f"{name}.rs"
    out = root / f"{name}_bin"
    write(src, body + "\n")
    return {
        "expected_tool": "rustc",
        "expected_args": {"source_file": str(src), "output": str(out)},
        "_path": str(src),
    }


# ---------------------------------------------------------------------------
# Phrasing templates per tool — vary surface form without changing the answer
# ---------------------------------------------------------------------------

PHRASINGS: dict[str, list[str]] = {
    "cargo_test": [
        'Verify whether the Cargo project at "{path}" passes its tests.',
        'Run the correct verification call so we can confirm the Cargo project at "{path}" is green.',
        'Execute the test suite of the Rust crate at "{path}" and report the outcome.',
    ],
    "cargo_check": [
        'Check whether the Rust project at "{path}" compiles cleanly without producing a binary.',
        'Issue the compile-only verification call for the Cargo project at "{path}".',
        'Confirm that the crate at "{path}" type-checks without performing a full build.',
    ],
    "cargo_build": [
        'Build the Cargo binary project at "{path}" using the correct Rust build tool.',
        'Compile the Cargo app at "{path}" into a binary using the right build tool.',
        'Produce the executable for the Rust binary crate at "{path}".',
    ],
    "rustc": [
        'Compile the single Rust source file at "{src}" to the binary "{out}".',
        'Use rustc to compile "{src}" to the binary "{out}".',
        'Invoke the Rust compiler directly on "{src}" and write the binary to "{out}".',
    ],
    "apply_patch": [
        ('The Cargo project at "{path}" has a failing test. The bug is in "{file_path}" '
         '({hint}). Use apply_patch to replace the buggy snippet with the correct one, '
         'then run cargo_test on "{path}" to verify the fix.'),
        ('Fix the failing test in the Cargo project at "{path}". The source file "{file_path}" '
         'contains a bug: {hint}. Patch the file, then verify with cargo_test.'),
    ],
    "apply_patch_bin": [
        ('The Cargo binary at "{path}" has a bug ({hint}) in "{file_path}". Use apply_patch '
         'to correct it, then run cargo_run on "{path}" — the expected stdout is "{out}".'),
        ('Patch the buggy source "{file_path}" of the Cargo binary at "{path}" ({hint}), '
         'then verify with cargo_run; the program should print "{out}".'),
    ],
}


def render_task(case: dict, phrasing: str) -> str:
    tool = case["expected_tool"]
    if tool == "rustc":
        return phrasing.format(src=case["expected_args"]["source_file"],
                               out=case["expected_args"]["output"])
    if tool == "apply_patch":
        return phrasing.format(
            path=case["blueprint_root"],
            file_path=case["expected_args"]["file_path"],
            hint=case.get("bug_hint", "see source"),
            out=case.get("expected_output", ""),
        )
    return phrasing.format(path=case["expected_args"]["project_path"])


def phrasings_for(case: dict, n: int) -> list[str]:
    """Bug-fix cases get full phrasing variety; coverage pool gets just one
    surface form (they exist for tool coverage, not signal strength)."""
    if case["expected_tool"] == "apply_patch":
        key = "apply_patch_bin" if "expected_output" in case else "apply_patch"
        return PHRASINGS[key][:n]
    return PHRASINGS[case["expected_tool"]][:1]


def prompt_for(task: str) -> str:
    return build_prompt(task, RUST_TOOLS)


# ---------------------------------------------------------------------------
# Structure-only rows from gold pool (no expected_tool)
# ---------------------------------------------------------------------------

USER_RE = re.compile(r"user「(.*?)」", re.DOTALL)


def load_gold_prefixes(gold_jsonl: Path, exclude_users: set[str], limit: int) -> list[str]:
    """Extract prompt prefixes (system+tools+user, up to assistant header) from
    a full-trace SFT JSONL, skipping any whose user string appears in
    `exclude_users` (the held-out eval prompts)."""
    out: list[str] = []
    with gold_jsonl.open(encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            trace = row.get("trace", "")
            m = USER_RE.search(trace)
            if not m:
                continue
            user_str = m.group(1).strip()
            if user_str in exclude_users:
                continue
            split = trace.split("<|im_start|>assistant", 1)
            if len(split) != 2:
                continue
            prefix = split[0] + "<|im_start|>assistant\n"
            out.append(prefix)
            if len(out) >= limit:
                break
    return out


def load_eval_user_strings(eval_yaml: Path) -> set[str]:
    import yaml
    data = yaml.safe_load(eval_yaml.read_text())
    return {p["user"].strip() for p in data.get("formal_eval", [])}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_cases(root: Path) -> list[dict]:
    cases: list[dict] = []
    for name, lib in CARGO_CHECK_LIBS:
        cases.append(emit_check_case(root, name, lib))
    for name, main_src in CARGO_BUILD_BINS:
        cases.append(emit_build_case(root, name, main_src))
    for name, body in RUSTC_FILES:
        cases.append(emit_rustc_case(root, name, body))
    for name, lib, test, find, repl, hint in BUGFIX_CASES:
        cases.append(emit_bugfix_case(root, name, lib, test, find, repl, hint))
    for name, main_src, find, repl, out, hint in BUGFIX_BIN_CASES:
        cases.append(emit_bugfix_bin_case(root, name, main_src, find, repl, out, hint))
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare RLVR prompt JSONL: Rust execution cases + optional structure-only gold prompts.")
    parser.add_argument("--root", type=Path, default=Path("runs/rlvr1/rust_cases"))
    parser.add_argument("--output", type=Path, default=Path("runs/rlvr1/prompts.jsonl"))
    parser.add_argument("--phrasings", type=int, default=2,
                        help="Surface-form variants per Rust case (1-3).")
    parser.add_argument("--gold-jsonl", type=Path, default=Path("synthetic_data/gold_glyph_3000.jsonl"),
                        help="SFT pool for structure-only rows.")
    parser.add_argument("--gold-count", type=int, default=50,
                        help="Number of structure-only rows to include (0 to skip).")
    parser.add_argument("--eval-yaml", type=Path, default=Path("sft/evals/prompts_125.yaml"),
                        help="Held-out eval prompts to EXCLUDE from gold extraction.")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    rng = random.Random(args.seed)

    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    cases = build_cases(root)

    n_phrasings = max(1, min(args.phrasings, 3))
    rust_rows: list[dict] = []
    for case in cases:
        tool = case["expected_tool"]
        for phrase in phrasings_for(case, n_phrasings):
            task = render_task(case, phrase)
            row = {
                "prompt": prompt_for(task),
                "expected_tool": tool,
                "expected_args": case["expected_args"],
            }
            if "blueprint_root" in case:
                row["blueprint_root"] = case["blueprint_root"]
            if "expected_output" in case:
                row["expected_output"] = case["expected_output"]
            rust_rows.append(row)

    structure_rows: list[dict] = []
    if args.gold_count > 0 and args.gold_jsonl.exists():
        exclude = load_eval_user_strings(args.eval_yaml) if args.eval_yaml.exists() else set()
        prefixes = load_gold_prefixes(args.gold_jsonl, exclude, args.gold_count * 4)
        rng.shuffle(prefixes)
        for prefix in prefixes[: args.gold_count]:
            structure_rows.append({"prompt": prefix})

    mixed = rust_rows + structure_rows
    rng.shuffle(mixed)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for row in mixed:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(mixed)} rows to {args.output}")
    print(f"  Rust execution rows: {len(rust_rows)} ({len(cases)} unique cases × {n_phrasings} phrasings)")
    print(f"  Structure-only rows: {len(structure_rows)}")
    print(f"  Rust fraction: {len(rust_rows) / max(1, len(mixed)):.1%}")
    print(f"Materialized Rust cases under {root}")


if __name__ == "__main__":
    main()
