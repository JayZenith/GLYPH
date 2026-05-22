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
    # --- extended lib bug families (math, comparison, range, iterators, strings, control flow)
    ("sublib_bug",
     "pub fn sub(a: i32, b: i32) -> i32 { a + b }",
     "a + b", "a - b",
     "Addition was used in place of subtraction; switching the operator restores the difference."),
    ("divlib_bug",
     "pub fn div(a: i32, b: i32) -> i32 { a * b }",
     "a * b", "a / b",
     "Multiplication was used where integer division is required; the operator fix is enough."),
    ("modlib_bug",
     "pub fn rem(a: i32, b: i32) -> i32 { a / b }",
     "a / b", "a % b",
     "Division was used where remainder is needed; switching to % matches the expected result."),
    ("powerlib_bug",
     "pub fn cube(n: i64) -> i64 { n.pow(2) }",
     "n.pow(2)", "n.pow(3)",
     "The exponent was 2 instead of 3; raising to the third power matches the intended cube."),
    ("doublelib_bug",
     "pub fn doubled(n: i32) -> i32 { n + n + 1 }",
     "n + n + 1", "n + n",
     "An off-by-one term was added; removing it yields the correct doubling."),
    ("halflib_bug",
     "pub fn half(n: i32) -> i32 { n * 2 }",
     "n * 2", "n / 2",
     "Multiplication by 2 produced double rather than half; switching to division returns the correct value."),
    ("inclib_bug",
     "pub fn inc(n: i32) -> i32 { n - 1 }",
     "n - 1", "n + 1",
     "Decrement was used where increment is required; flipping the operator fixes it."),
    ("avg2lib_bug",
     "pub fn avg2(a: i32, b: i32) -> i32 { (a + b) * 2 }",
     "(a + b) * 2", "(a + b) / 2",
     "The sum was multiplied instead of halved; dividing by 2 produces the average."),
    ("negatelib_bug",
     "pub fn negate(n: i32) -> i32 { n.abs() }",
     "n.abs()", "-n",
     "abs() was used where negation is required; replacing with the unary minus gives the correct sign."),
    ("squarelib_bug",
     "pub fn square(n: i32) -> i32 { n + n }",
     "n + n", "n * n",
     "Doubling was used where squaring is required; multiplying n by itself returns the square."),
    # comparison
    ("gtlib_bug",
     "pub fn is_pos(n: i32) -> bool { n < 0 }",
     "n < 0", "n > 0",
     "The strict-less check returned positivity inverted; flipping to greater-than fixes it."),
    ("gelib_bug",
     "pub fn at_least(n: i32, k: i32) -> bool { n > k }",
     "n > k", "n >= k",
     "The inclusive boundary case was missing; switching to >= covers equality too."),
    ("lelib_bug",
     "pub fn at_most(n: i32, k: i32) -> bool { n < k }",
     "n < k", "n <= k",
     "Strict-less excluded equality; <= is the right inclusive bound."),
    ("eqlib_bug",
     "pub fn same(a: i32, b: i32) -> bool { a != b }",
     "a != b", "a == b",
     "Inequality was returned where equality is required; switching the operator fixes the predicate."),
    ("nelib_bug",
     "pub fn different(a: i32, b: i32) -> bool { a == b }",
     "a == b", "a != b",
     "Equality was returned where inequality is required; flipping the operator fixes the predicate."),
    # ranges
    ("rangesumlib_bug",
     "pub fn sum_to(n: i32) -> i32 { (1..n).sum() }",
     "(1..n)", "(1..=n)",
     "The exclusive range omitted n itself; using the inclusive form yields the correct sum."),
    ("rangeproductlib_bug",
     "pub fn fact(n: u32) -> u32 { (1..n).product() }",
     "(1..n)", "(1..=n)",
     "Factorial requires multiplying up to and including n; switching to an inclusive range fixes it."),
    ("rangecountlib_bug",
     "pub fn count_up(n: u32) -> u32 { (0..n).count() as u32 + 1 }",
     ".count() as u32 + 1", ".count() as u32",
     "An extra +1 inflated the count; removing it matches the actual element count."),
    ("rangerevlib_bug",
     "pub fn count_down(n: u32) -> Vec<u32> { (0..n).collect() }",
     "(0..n).collect()", "(0..n).rev().collect()",
     "Iteration order was ascending where descending is required; .rev() reverses the sequence."),
    # iterator methods
    ("collecttovec_bug",
     "pub fn evens(n: u32) -> Vec<u32> { (0..n).filter(|x| x % 2 == 1).collect() }",
     "x % 2 == 1", "x % 2 == 0",
     "The filter kept odd numbers instead of even; flipping the remainder check returns the right set."),
    ("filtermaplib_bug",
     "pub fn nonzero(v: &[i32]) -> Vec<i32> { v.iter().filter(|x| **x == 0).copied().collect() }",
     "**x == 0", "**x != 0",
     "Zero values were kept; inverting the predicate yields the nonzero subset."),
    ("foldlib_bug",
     "pub fn product(v: &[i32]) -> i32 { v.iter().fold(0, |acc, x| acc * x) }",
     "fold(0,", "fold(1,",
     "Product folding started from 0 and always produced 0; starting from 1 gives the correct product."),
    ("foldsumlib_bug",
     "pub fn sum(v: &[i32]) -> i32 { v.iter().fold(1, |acc, x| acc + x) }",
     "fold(1,", "fold(0,",
     "Summation folding started from 1, off by one; starting from 0 returns the true sum."),
    ("minunwraplib_bug",
     "pub fn smallest(v: &[i32]) -> i32 { *v.iter().max().unwrap_or(&0) }",
     ".max()", ".min()",
     "max was selected where the smallest element is required; switching iterator methods fixes it."),
    ("maxbylib_bug",
     "pub fn longest<'a>(v: &'a [&'a str]) -> &'a str { v.iter().min_by_key(|s| s.len()).copied().unwrap_or(\"\") }",
     ".min_by_key", ".max_by_key",
     "min_by_key returned the shortest entry; the spec wants the longest, so max_by_key is correct."),
    ("countvslen_bug",
     "pub fn n_items(v: &[i32]) -> usize { v.iter().enumerate().count() + 1 }",
     ".count() + 1", ".count()",
     "An off-by-one extra was added to the count; removing it matches the slice length."),
    ("enumeratelib_bug",
     "pub fn first_at_index(v: &[i32], k: usize) -> Option<i32> { v.iter().nth(k - 1).copied() }",
     "k - 1", "k",
     "Subtracting 1 from the index was a manual off-by-one; nth already takes a 0-based index."),
    ("clonedvscopied_bug",
     "pub fn first_clone(v: &[i32]) -> Option<i32> { v.iter().next().cloned() }",
     ".cloned()", ".copied()",
     "i32 is Copy, so .copied() is the canonical (and slightly cheaper) operation here."),
    # string methods
    ("uppercaselib_bug",
     "pub fn shout(s: &str) -> String { s.to_lowercase() }",
     "to_lowercase", "to_uppercase",
     "The wrong case method was used; to_uppercase produces the expected SHOUTING output."),
    ("trimlib_bug",
     "pub fn trim_input(s: &str) -> &str { s.trim_start() }",
     "trim_start", "trim",
     "trim_start only strips leading whitespace; the spec wants both ends, so trim is right."),
    ("startswithlib_bug",
     "pub fn is_prefixed(s: &str, p: &str) -> bool { s.ends_with(p) }",
     "ends_with", "starts_with",
     "ends_with was used instead of starts_with; the prefix check needs the opposite method."),
    ("endswithlib_bug",
     "pub fn is_suffixed(s: &str, p: &str) -> bool { s.starts_with(p) }",
     "starts_with", "ends_with",
     "starts_with was used instead of ends_with; the suffix check needs the opposite method."),
    ("byteslib_bug",
     "pub fn char_count(s: &str) -> usize { s.len() }",
     "s.len()", "s.chars().count()",
     "Byte length was returned where character count is needed; chars().count() handles multibyte chars."),
    ("splitlib_bug",
     "pub fn n_words(s: &str) -> usize { s.split(',').count() }",
     "split(',')", "split_whitespace()",
     "Splitting on commas only counts comma-separated fields; split_whitespace() returns whitespace-delimited word count."),
    ("joinlib_bug",
     "pub fn join_dash(parts: &[&str]) -> String { parts.join(\",\") }",
     "\",\"", "\"-\"",
     "The wrong separator was used; replacing the comma with a dash matches the expected output."),
    ("replacelib_bug",
     "pub fn shout_oh(s: &str) -> String { s.replace(\"oh\", \"OH\").to_lowercase() }",
     ".to_lowercase()", "",
     "The final to_lowercase() undid the replacement uppercasing; removing it preserves the OH."),
    ("contiainslib_bug",
     "pub fn has_a(s: &str) -> bool { s.contains(\"b\") }",
     "\"b\"", "\"a\"",
     "The wrong substring was searched for; updating it to 'a' matches the function name."),
    ("charcountlib_bug",
     "pub fn count_a(s: &str) -> usize { s.chars().filter(|c| *c == 'b').count() }",
     "*c == 'b'", "*c == 'a'",
     "The filter checked for the wrong letter; switching to 'a' matches the function intent."),
    # control flow
    ("boollib_bug",
     "pub fn both(a: bool, b: bool) -> bool { a || b }",
     "a || b", "a && b",
     "Or was used where logical-and is required; switching the operator fixes the predicate."),
    ("orlib_bug",
     "pub fn either(a: bool, b: bool) -> bool { a && b }",
     "a && b", "a || b",
     "And was used where or is required; the operator switch matches the spec."),
    ("notlib_bug",
     "pub fn is_false(b: bool) -> bool { b }",
     "pub fn is_false(b: bool) -> bool { b }",
     "pub fn is_false(b: bool) -> bool { !b }",
     "The function returned its argument; negating it returns the expected predicate."),
    ("matchlib_bug",
     "pub fn sign(n: i32) -> i32 { match n { x if x < 0 => 1, 0 => 0, _ => -1 } }",
     "x < 0 => 1, 0 => 0, _ => -1",
     "x < 0 => -1, 0 => 0, _ => 1",
     "Positive and negative arms were swapped; restoring conventional sign returns -1 for negatives and 1 for positives."),
    ("optunwraplib_bug",
     "pub fn or_zero(o: Option<i32>) -> i32 { o.unwrap_or(1) }",
     "o.unwrap_or(1)", "o.unwrap_or(0)",
     "The default was 1 where 0 is required; updating the default fixes the fallback."),
    ("optmaplib_bug",
     "pub fn doubled_opt(o: Option<i32>) -> Option<i32> { o.map(|x| x + x) }",
     "x + x", "x * 2",
     "Addition is fine but the spec asks for an explicit multiplication-by-2 expression here."),
    ("ifelselib_bug",
     "pub fn pick(b: bool) -> i32 { if b { 0 } else { 1 } }",
     "if b { 0 } else { 1 }", "if b { 1 } else { 0 }",
     "The if-else branches were swapped; restoring them returns 1 on true and 0 on false."),
    ("recursionbaselib_bug",
     "pub fn fact_rec(n: u32) -> u32 { if n == 0 { 0 } else { n * fact_rec(n - 1) } }",
     "if n == 0 { 0 }", "if n == 0 { 1 }",
     "The factorial base case returned 0, killing the product; returning 1 makes the recursion work."),
    ("whileloopib_bug",
     "pub fn count_to(n: u32) -> u32 { let mut i = 0; while i < n { i += 2; } i }",
     "i += 2", "i += 1",
     "The loop incremented by 2, skipping every other number; stepping by 1 reaches n correctly."),
    ("optsomelib_bug",
     "pub fn always_some() -> Option<i32> { None }",
     "None", "Some(0)",
     "None was returned where Some is required; the simplest fix returns Some(0)."),
    ("returnvallib_bug",
     "pub fn ten() -> i32 { 100 }",
     "100", "10",
     "The literal was off by a factor of 10; replacing it returns the expected ten."),
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
    # --- extended bin bugs
    ("bugbin_max",
     'fn main() { let v = [3, 1, 5, 2]; println!("{}", v.iter().min().unwrap()); }',
     "v.iter().min()", "v.iter().max()", "5",
     "The program reported the minimum instead of the maximum; switching iterator methods fixes the output."),
    ("bugbin_avg",
     'fn main() { let v = [2, 4, 6, 8]; let s: i32 = v.iter().sum(); println!("{}", s); }',
     "println!(\"{}\", s);", "println!(\"{}\", s / v.len() as i32);", "5",
     "The program printed the sum but the spec requires the average; dividing by length fixes it."),
    ("bugbin_evens",
     'fn main() { for n in 1..=5 { if n % 2 == 1 { print!("{} ", n); } } println!(); }',
     "n % 2 == 1", "n % 2 == 0", "2 4",
     "The filter kept odd numbers; flipping the condition prints the evens 2 and 4."),
    ("bugbin_join",
     'fn main() { let parts = ["a", "b", "c"]; println!("{}", parts.join(",")); }',
     "join(\",\")", "join(\"-\")", "a-b-c",
     "The separator was a comma where the spec asks for a dash; switching joins with the right glue."),
    ("bugbin_caps",
     'fn main() { println!("{}", "rust".to_uppercase().to_lowercase()); }',
     ".to_lowercase()", "", "RUST",
     "An unnecessary to_lowercase() undid the uppercasing; removing it leaves RUST."),
    ("bugbin_neg",
     'fn main() { let x = -42; println!("{}", x); }',
     "let x = -42;", "let x = 42;", "42",
     "The literal was negative; the spec asks for the positive 42."),
    ("bugbin_concat",
     'fn main() { let a = "hi"; let b = "there"; println!("{}{}", b, a); }',
     "println!(\"{}{}\", b, a);", "println!(\"{}{}\", a, b);", "hithere",
     "The arguments were in the wrong order; swapping them yields hi-then-there."),
    ("bugbin_format",
     'fn main() { let n = 7; println!("{:b}", n); }',
     "{:b}", "{}", "7",
     "Binary formatting was used where decimal is required; removing the format spec prints the integer."),
    ("bugbin_starsq",
     'fn main() { for n in 1..=3 { println!("{}", n * 2); } }',
     "n * 2", "n * n", "1\n4\n9",
     "Doubling was used where squaring is required; multiplying n by itself fixes the values."),
    ("bugbin_cumsum",
     'fn main() { let v = [1, 2, 3]; let mut s = 0; for x in &v { s = *x; print!("{} ", s); } println!(); }',
     "s = *x;", "s += *x;", "1 3 6",
     "The accumulator was overwritten instead of added to; switching to compound assignment produces the running sum."),
    ("bugbin_decrement",
     'fn main() { let mut n = 5; for _ in 0..3 { n += 1; print!("{} ", n); } println!(); }',
     "n += 1", "n -= 1", "4 3 2",
     "The loop incremented; the expected output counts down, so the operator should be decrement."),
    ("bugbin_charcount",
     'fn main() { let s = "héllo"; println!("{}", s.len()); }',
     "s.len()", "s.chars().count()", "5",
     "Byte length over-counts multibyte chars; chars().count() returns the visible character count."),
    ("bugbin_modpadding",
     'fn main() { for n in 0..5 { let lbl = if n % 2 == 1 { "odd" } else { "even" }; println!("{} {}", n, lbl); } }',
     "n % 2 == 1", "n % 2 == 0", "0 even\n1 odd\n2 even\n3 odd\n4 even",
     "The labels were swapped because the check matched odd instead of even; flipping the equality restores them."),
    ("bugbin_substr",
     'fn main() { let s = "abcdef"; println!("{}", &s[0..3]); }',
     "&s[0..3]", "&s[3..6]", "def",
     "The wrong slice was taken; offsetting to 3..6 yields the last three characters."),
    ("bugbin_format_decimal",
     'fn main() { let pi: f64 = 3.14159; println!("{}", pi); }',
     "println!(\"{}\", pi);", "println!(\"{:.2}\", pi);", "3.14",
     "Default formatting prints too many digits; the {:.2} spec rounds to two decimals."),
    ("bugbin_indexing",
     'fn main() { let v = vec![10, 20, 30]; println!("{}", v[0]); }',
     "v[0]", "v[2]", "30",
     "The wrong index was used; reading v[2] returns the last element 30."),
    ("bugbin_min",
     'fn main() { let v = [3, 1, 5, 2]; println!("{}", v.iter().max().unwrap()); }',
     "v.iter().max()", "v.iter().min()", "1",
     "The program reported the maximum where the minimum is required; switching iterator methods fixes the output."),
    ("bugbin_filteralpha",
     'fn main() { let s = "abc123"; let r: String = s.chars().filter(|c| c.is_alphabetic()).collect(); println!("{}", r); }',
     "is_alphabetic", "is_numeric", "123",
     "The filter kept letters where the spec asks for digits; switching to is_numeric returns the numeric substring."),
    ("bugbin_loopprint",
     'fn main() { for i in (1..=5).rev() { print!("{} ", i); } println!(); }',
     "(1..=5).rev()", "(1..=5)", "1 2 3 4 5",
     "The sequence was emitted in reverse; removing .rev() prints ascending values."),
    ("bugbin_assign",
     'fn main() { let mut x = 0; x = x + 1; x = x + 1; println!("{}", x); }',
     "let mut x = 0;", "let mut x = 3;", "5",
     "The starting value was 0; setting it to 3 makes the two increments land on 5."),
    ("bugbin_pow",
     'fn main() { let n: i32 = 2; println!("{}", n.pow(2)); }',
     "n.pow(2)", "n.pow(8)", "256",
     "The exponent was 2 instead of 8; updating it produces 2^8 = 256."),
    ("bugbin_chars",
     'fn main() { let s = "rust"; println!("{}", s.chars().nth(0).unwrap()); }',
     ".nth(0)", ".nth(3)", "t",
     "The first character was selected instead of the fourth; nth(3) returns the last char."),
    ("bugbin_emptycheck",
     'fn main() { let v: Vec<i32> = vec![]; println!("{}", if v.is_empty() { "no" } else { "yes" }); }',
     "if v.is_empty() { \"no\" } else { \"yes\" }",
     "if v.is_empty() { \"yes\" } else { \"no\" }",
     "yes",
     "The labels were inverted; flipping them lets is_empty() print yes for an empty vector."),
    ("bugbin_truthy",
     'fn main() { let x = 10; if x > 0 { println!("non-positive"); } else { println!("positive"); } }',
     "if x > 0 { println!(\"non-positive\"); } else { println!(\"positive\"); }",
     "if x > 0 { println!(\"positive\"); } else { println!(\"non-positive\"); }",
     "positive",
     "The branches' labels were swapped; restoring them prints the right description for x = 10."),
    ("bugbin_uppercase_only_first",
     'fn main() { let s = "hello"; let mut chars = s.chars(); let first = chars.next().unwrap().to_lowercase().next().unwrap(); println!("{}{}", first, chars.as_str()); }',
     "to_lowercase()", "to_uppercase()", "Hello",
     "The first character was being lowercased instead of uppercased; the fix produces Hello."),
    ("bugbin_collectvecstr",
     'fn main() { let v = vec!["a", "b", "c"]; let s: String = v.into_iter().collect::<Vec<&str>>().concat(); println!("{}", s); }',
     ".collect::<Vec<&str>>().concat()", ".collect::<String>()",
     "abc",
     "An intermediate Vec collect-then-concat was used; collecting directly into a String is simpler and produces the same result."),
    ("bugbin_truthycheck",
     'fn main() { let n = 5; println!("{}", n == 0); }',
     "n == 0", "n != 0", "true",
     "Equality-with-zero was returned where non-zero is intended; flipping the operator yields true for n = 5."),
    ("bugbin_iterpattern",
     'fn main() { let v = [10, 20, 30]; for x in v.iter().rev() { print!("{} ", x); } println!(); }',
     "v.iter().rev()", "v.iter()", "10 20 30",
     "The slice was iterated in reverse; removing .rev() emits the natural order."),
    ("bugbin_iterzip",
     'fn main() { let a = [1, 2, 3]; let b = ["x", "y", "z"]; for (x, y) in b.iter().zip(a.iter()) { println!("{}{}", x, y); } }',
     "b.iter().zip(a.iter())",
     "a.iter().zip(b.iter())",
     "1x\n2y\n3z",
     "Zipping order was reversed so the format args came out swapped; placing a first matches the intent."),
    ("bugbin_loopaccum",
     'fn main() { let v = [1, 2, 3, 4]; let mut s = 0; for x in v.iter() { s += *x * 2; } println!("{}", s); }',
     "s += *x * 2;", "s += *x;", "10",
     "The accumulator added twice each element; removing the *2 produces the plain sum."),
    ("bugbin_optunwrap",
     'fn main() { let o: Option<i32> = Some(7); println!("{}", o.unwrap_or(-1)); }',
     "Some(7)", "None", "-1",
     "The Option carried a value where the spec needs None so the default of -1 prints."),
    ("bugbin_resultok",
     'fn main() { let r: Result<i32, &str> = Err("nope"); println!("{}", r.unwrap_or(0)); }',
     "Err(\"nope\")", "Ok(42)", "42",
     "The Result was Err so unwrap_or returned its default; switching to Ok(42) prints the inner value."),
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


# Programmatic bulk generators for single-tool examples — varied projects,
# small phrasing differences, each trace fully formatted.
BULK_PROJECTS = [
    # (name, kind, src) where kind ∈ {lib, bin}
    ("addlib_pos", "lib", "pub fn add(a: i32, b: i32) -> i32 { a + b }"),
    ("sublib_pos", "lib", "pub fn sub(a: i32, b: i32) -> i32 { a - b }"),
    ("evenlib_pos", "lib", "pub fn is_even(n: i32) -> bool { n % 2 == 0 }"),
    ("sumlib_pos", "lib", "pub fn sum(s: &[i32]) -> i32 { s.iter().sum() }"),
    ("maxlib_pos", "lib", "pub fn maxv(s: &[i32]) -> i32 { *s.iter().max().unwrap_or(&0) }"),
    ("revstrlib_pos", "lib", "pub fn rev(s: &str) -> String { s.chars().rev().collect() }"),
    ("strutils2", "lib", "pub fn shout(s: &str) -> String { s.to_uppercase() }"),
    ("rangelib_pos", "lib", "pub fn in_range(v: i32, lo: i32, hi: i32) -> bool { v >= lo && v <= hi }"),
    ("optionlib_pos", "lib", "pub fn first_or(s: &[i32], d: i32) -> i32 { s.first().copied().unwrap_or(d) }"),
    ("dedup_lib", "lib", "pub fn dedup(mut v: Vec<i32>) -> Vec<i32> { v.sort(); v.dedup(); v }"),
    ("fizz_lib", "lib", 'pub fn fizz(n: u32) -> String { if n % 15 == 0 { "FizzBuzz".into() } else if n % 3 == 0 { "Fizz".into() } else if n % 5 == 0 { "Buzz".into() } else { n.to_string() } }'),
    ("hello_bin", "bin", 'fn main() { println!("hello"); }'),
    ("greet_bin", "bin", 'fn main() { let who = "world"; println!("hello, {who}!"); }'),
    ("count_bin", "bin", 'fn main() { for v in 1..=5 { println!("{v}"); } }'),
    ("square_bin", "bin", 'fn main() { for n in 1..=4 { println!("{}", n * n); } }'),
    ("calc_bin", "bin", 'fn main() { let (a, b) = (12, 30); println!("{}", a + b); }'),
    ("rev_bin", "bin", 'fn main() { let s = "hello"; let r: String = s.chars().rev().collect(); println!("{r}"); }'),
    ("fib_bin", "bin", 'fn main() { let (mut a, mut b) = (0u32, 1u32); for _ in 0..6 { print!("{a} "); let t = a + b; a = b; b = t; } println!(); }'),
    ("upper_bin", "bin", 'fn main() { println!("{}", "hello".to_uppercase()); }'),
    ("primes_bin", "bin", 'fn main() { for n in 2..15 { if (2..n).all(|d| n % d != 0) { print!("{n} "); } } println!(); }'),
    # extended pool
    ("absv_lib", "lib", "pub fn absv(n: i32) -> i32 { n.abs() }"),
    ("min_of_lib", "lib", "pub fn min_of(s: &[i32]) -> i32 { *s.iter().min().unwrap_or(&0) }"),
    ("avg_lib", "lib", "pub fn avg(s: &[f64]) -> f64 { if s.is_empty() { 0.0 } else { s.iter().sum::<f64>() / s.len() as f64 } }"),
    ("palin_lib", "lib", "pub fn pal(s: &str) -> bool { let r: String = s.chars().rev().collect(); r == s }"),
    ("vowels_lib", "lib", "pub fn vowels(s: &str) -> usize { s.chars().filter(|c| \"aeiouAEIOU\".contains(*c)).count() }"),
    ("wc_lib", "lib", "pub fn wc(s: &str) -> usize { s.split_whitespace().count() }"),
    ("cap_lib", "lib", "pub fn cap(s: &str) -> String { let mut c = s.chars(); match c.next() { Some(f) => f.to_uppercase().collect::<String>() + c.as_str(), None => String::new() } }"),
    ("clamp_lib", "lib", "pub fn clamp(v: i32, lo: i32, hi: i32) -> i32 { v.max(lo).min(hi) }"),
    ("gcd_lib", "lib", "pub fn gcd(a: u32, b: u32) -> u32 { if b == 0 { a } else { gcd(b, a % b) } }"),
    ("fact_lib", "lib", "pub fn fact(n: u32) -> u32 { (1..=n).product::<u32>().max(1) }"),
    ("fib_lib2", "lib", "pub fn fib(n: u32) -> u32 { match n { 0 => 0, 1 => 1, _ => fib(n-1) + fib(n-2) } }"),
    ("pair_lib", "lib", "pub fn pair<T: Clone>(x: T) -> (T, T) { (x.clone(), x) }"),
    ("first_word_lib", "lib", "pub fn first_word(s: &str) -> &str { s.split_whitespace().next().unwrap_or(\"\") }"),
    ("trim_lib", "lib", "pub fn trim_both(s: &str) -> &str { s.trim() }"),
    ("split_lib", "lib", "pub fn split_csv(s: &str) -> Vec<&str> { s.split(',').collect() }"),
    ("join_lib", "lib", "pub fn join_dash(parts: &[&str]) -> String { parts.join(\"-\") }"),
    ("sorted_lib", "lib", "pub fn sorted(mut v: Vec<i32>) -> Vec<i32> { v.sort(); v }"),
    ("minmax_lib", "lib", "pub fn min_max(s: &[i32]) -> Option<(i32, i32)> { Some((*s.iter().min()?, *s.iter().max()?)) }"),
    ("pow2_lib", "lib", "pub fn is_pow2(n: u32) -> bool { n > 0 && (n & (n-1)) == 0 }"),
    ("cube_lib", "lib", "pub fn cube(n: i64) -> i64 { n * n * n }"),
    ("parseu_lib", "lib", "pub fn parse_u(s: &str) -> Result<u32, std::num::ParseIntError> { s.parse() }"),
    ("optfirst_lib", "lib", "pub fn maybe_first(s: &[i32]) -> Option<i32> { s.first().copied() }"),
    ("hashfreq_lib", "lib", "use std::collections::HashMap; pub fn freq(s: &str) -> HashMap<char, usize> { let mut h = HashMap::new(); for c in s.chars() { *h.entry(c).or_insert(0) += 1; } h }"),
    ("area_lib", "lib", "pub enum Shape { Circle(f64), Square(f64) } pub fn area(s: &Shape) -> f64 { match s { Shape::Circle(r) => std::f64::consts::PI * r * r, Shape::Square(a) => a * a } }"),
    ("trait_lib", "lib", "pub trait Greet { fn hello(&self) -> String; } pub struct P; impl Greet for P { fn hello(&self) -> String { \"hi\".into() } }"),
    ("count_vowels_lib", "lib", "pub fn vow(s: &str) -> usize { s.chars().filter(|c| \"aeiou\".contains(*c)).count() }"),
    ("evenodd_bin", "bin", 'fn main() { for n in 1..=6 { println!("{n}: {}", if n % 2 == 0 { "even" } else { "odd" }); } }'),
    ("collect_bin", "bin", 'fn main() { let v: Vec<i32> = (1..=5).collect(); println!("{v:?}"); }'),
    ("zip_bin", "bin", 'fn main() { for (i, c) in "abcd".chars().enumerate() { println!("{i}: {c}"); } }'),
    ("fizzbuzz_bin", "bin", 'fn main() { for n in 1..=15 { match (n%3, n%5) { (0,0)=>println!("FizzBuzz"), (0,_)=>println!("Fizz"), (_,0)=>println!("Buzz"), _=>println!("{n}") } } }'),
]


def _project_path(name: str) -> str:
    return f"/workspace/glyph/runs/rlvr1/rust_cases/{name}"


def _file_path(name: str, kind: str) -> str:
    sub = "src/lib.rs" if kind == "lib" else "src/main.rs"
    return f"{_project_path(name)}/{sub}"


def bulk_read_traces() -> list[str]:
    """Two read_file → response traces per project — varied phrasings."""
    out = []
    phrasings = [
        'Show me the contents of "{fp}".',
        'Read "{fp}" and summarize what the code does.',
        'Open the source at "{fp}" and describe it briefly.',
        'I need to see "{fp}"; read it and explain the public API in one sentence.',
    ]
    for i, (name, kind, src) in enumerate(BULK_PROJECTS):
        fp = _file_path(name, kind)
        result = src.replace('"', '\\"')
        if kind == "lib":
            response = f"The file at `{fp}` defines `{src}`."
        else:
            response = f"The binary's `main.rs` at `{fp}` runs: `{src}`."
        for j in (0, 2):
            user = phrasings[(i + j) % len(phrasings)].format(fp=fp)
            out.append(single_call_trace(
                user, "read_file", [("file_path", fp)], "src1", result,
                f"The file contents are visible; the code exposes a single tight implementation.",
                response,
            ))
    return out


def bulk_check_traces() -> list[str]:
    """Two cargo_check traces per lib project."""
    out = []
    libs = [(n, k, s) for n, k, s in BULK_PROJECTS if k == "lib"]
    phrasings = [
        'Run cargo_check on the project at "{pp}".',
        'Check whether "{pp}" type-checks cleanly.',
        'Issue a compile-only verification call against "{pp}".',
        'Confirm "{pp}" passes cargo_check.',
    ]
    for i, (name, _kind, _src) in enumerate(libs):
        pp = _project_path(name)
        for j in (0, 2):
            out.append(single_call_trace(
                phrasings[(i + j) % len(phrasings)].format(pp=pp),
                "cargo_check", [("project_path", pp)], "chk1",
                f"status: success\\nexit_code: 0\\nstdout: Checking {name} v0.1.0\\nFinished",
                "cargo_check returned success; the crate type-checks without errors.",
                f"`{name}` type-checks cleanly via cargo_check; no errors reported.",
            ))
    return out


def bulk_build_traces() -> list[str]:
    out = []
    bins = [(n, k, s) for n, k, s in BULK_PROJECTS if k == "bin"]
    phrasings = [
        'Build the Cargo binary at "{pp}".',
        'Run cargo_build on "{pp}".',
        'Compile the project at "{pp}" into a binary.',
        'Produce the debug binary for the bin crate at "{pp}".',
    ]
    for i, (name, _kind, _src) in enumerate(bins):
        pp = _project_path(name)
        for j in (0, 2):
            out.append(single_call_trace(
                phrasings[(i + j) % len(phrasings)].format(pp=pp),
                "cargo_build", [("project_path", pp)], "bld1",
                f"status: success\\nexit_code: 0\\nstdout: Compiling {name} v0.1.0\\nFinished `dev` profile",
                "cargo_build succeeded; the artifact lives in target/debug/.",
                f"`{name}` compiles cleanly via cargo_build; the binary is in target/debug/.",
            ))
    return out


def bulk_run_traces() -> list[str]:
    out = []
    # Pair each bin project with a plausible stdout from its main.
    plausible_stdout = {
        "hello_bin": "hello",
        "greet_bin": "hello, world!",
        "count_bin": "1\\n2\\n3\\n4\\n5",
        "square_bin": "1\\n4\\n9\\n16",
        "calc_bin": "42",
        "rev_bin": "olleh",
        "fib_bin": "0 1 1 2 3 5",
        "upper_bin": "HELLO",
        "primes_bin": "2 3 5 7 11 13",
    }
    phrasings = [
        'Run the binary at "{pp}" and report its stdout.',
        'Execute the Cargo project at "{pp}" and tell me what it prints.',
        'cargo_run on "{pp}"; report the output.',
        'Verify the binary at "{pp}" by running it.',
    ]
    bins = [(n, k, s) for n, k, s in BULK_PROJECTS if k == "bin"]
    for i, (name, _kind, _src) in enumerate(bins):
        pp = _project_path(name)
        stdout = plausible_stdout.get(name, "")
        for j in (0, 2):
            out.append(single_call_trace(
                phrasings[(i + j) % len(phrasings)].format(pp=pp),
                "cargo_run", [("project_path", pp)], "run1",
                f"status: success\\nexit_code: 0\\nstdout: {stdout}",
                "cargo_run printed the expected output; the binary works as designed.",
                f"`{name}` ran successfully and printed: {stdout.replace(chr(92)+'n', '; ')}",
            ))
    return out


def bulk_test_traces() -> list[str]:
    """cargo_test against pre-built lib variants (bug-free passing tests)."""
    out = []
    libs = [(n, k, s) for n, k, s in BULK_PROJECTS if k == "lib"]
    phrasings = [
        'Verify the tests pass for "{pp}".',
        'Run cargo_test on "{pp}".',
        'Confirm the test suite at "{pp}" is green.',
        'Execute the tests for the crate at "{pp}".',
    ]
    for i, (name, _kind, _src) in enumerate(libs):
        pp = _project_path(name)
        for j in (0, 2):
            out.append(single_call_trace(
                phrasings[(i + j) % len(phrasings)].format(pp=pp),
                "cargo_test", [("project_path", pp)], "tst1",
                f"status: success\\nexit_code: 0\\nstdout: running 1 test\\ntest tests::t ... ok\\n\\ntest result: ok. 1 passed; 0 failed",
                "cargo_test reported all tests passing.",
                f"The test suite for `{name}` is green; cargo_test passes cleanly.",
            ))
    return out


def bulk_rustc_traces() -> list[str]:
    """rustc on standalone .rs files."""
    out = []
    files = [
        ("hello2", 'fn main() { println!("hi"); }'),
        ("sum2", 'fn main() { let v = [1,2,3,4]; let s: i32 = v.iter().sum(); println!("{s}"); }'),
        ("double", 'fn main() { let x = 7; println!("{}", x * 2); }'),
        ("upper", 'fn main() { println!("{}", "hello".to_uppercase()); }'),
        ("match2", 'fn main() { let n = 4; let lbl = if n % 2 == 0 { "even" } else { "odd" }; println!("{lbl}"); }'),
        ("rev2", 'fn main() { let s = "rust"; let r: String = s.chars().rev().collect(); println!("{r}"); }'),
        ("square2", 'fn main() { for n in 1..=4 { print!("{} ", n * n); } println!(); }'),
        ("range_sum", 'fn main() { let s: i32 = (1..=10).sum(); println!("{s}"); }'),
    ]
    phrasings = [
        'Compile "{src}" with rustc to "{out}".',
        'Use rustc to build "{src}" into the binary "{out}".',
        'Invoke rustc on "{src}", writing the binary to "{out}".',
        'Produce the standalone binary "{out}" from "{src}" via rustc.',
    ]
    for i, (name, _body) in enumerate(files):
        src = f"/workspace/glyph/runs/rlvr1/rust_cases/{name}.rs"
        out_bin = f"/workspace/glyph/runs/rlvr1/rust_cases/{name}_bin"
        out.append(single_call_trace(
            phrasings[i % len(phrasings)].format(src=src, out=out_bin),
            "rustc", [("source_file", src), ("output", out_bin)], "rc1",
            "status: success\\nexit_code: 0\\nstdout:",
            "rustc compiled the source to the requested output without errors.",
            f"`{src}` compiled cleanly; the binary is at `{out_bin}`.",
        ))
    return out


def bulk_inspect_then_test_traces() -> list[str]:
    """Multi-step: read_file → cargo_test → response (lib, no patch)."""
    out = []
    libs = [(n, k, s) for n, k, s in BULK_PROJECTS if k == "lib"]
    for name, _kind, src in libs:
        pp = _project_path(name)
        fp = _file_path(name, "lib")
        user = (
            f'Look at the source at "{fp}", then run cargo_test on "{pp}" to confirm its tests pass.'
        )
        todos = [
            f"Read {fp} to confirm the public API.",
            f"Run cargo_test on {pp} to verify behavior.",
        ]
        rationale = "Inspect first so the answer cites concrete code, then verify via the test suite."
        out.append(g.multi_tool_trace(
            SYSTEM, rust_dev_tools(), user, todos, rationale,
            "read_file", [("file_path", fp)], "src1",
            src.replace('"', '\\"'),
            "The source defines a small public surface; tests should exercise it directly.",
            "note_src",
            "cargo_test", [("project_path", pp)], "tst1",
            f"status: success\\nexit_code: 0\\nstdout: running 1 test\\ntest tests::t ... ok\\n\\ntest result: ok. 1 passed; 0 failed",
            "cargo_test reports the test suite green.",
            "note_test",
            f"The source at `{fp}` is `{src}` and the test suite at `{pp}` passes cargo_test cleanly.",
        ))
    return out


def bulk_inspect_then_run_traces() -> list[str]:
    """Multi-step: read_file → cargo_run → response (bin, no patch)."""
    plausible_stdout = {
        "hello_bin": "hello",
        "greet_bin": "hello, world!",
        "count_bin": "1\\n2\\n3\\n4\\n5",
        "square_bin": "1\\n4\\n9\\n16",
        "calc_bin": "42",
        "rev_bin": "olleh",
        "fib_bin": "0 1 1 2 3 5",
        "upper_bin": "HELLO",
        "primes_bin": "2 3 5 7 11 13",
        "evenodd_bin": "1: odd\\n2: even\\n3: odd\\n4: even\\n5: odd\\n6: even",
        "collect_bin": "[1, 2, 3, 4, 5]",
        "zip_bin": "0: a\\n1: b\\n2: c\\n3: d",
        "fizzbuzz_bin": "1\\n2\\nFizz\\n4\\nBuzz\\nFizz\\n7\\n8\\nFizz\\nBuzz\\n11\\nFizz\\n13\\n14\\nFizzBuzz",
    }
    out = []
    bins = [(n, k, s) for n, k, s in BULK_PROJECTS if k == "bin"]
    for name, _kind, src in bins:
        pp = _project_path(name)
        fp = _file_path(name, "bin")
        stdout = plausible_stdout.get(name, "")
        user = (
            f'Inspect "{fp}", then run cargo_run on "{pp}" and report the output.'
        )
        todos = [
            f"Read {fp} to see what main does.",
            f"Run cargo_run on {pp} and capture the stdout.",
        ]
        rationale = "Inspect first so the answer cites the actual main, then verify by running the binary."
        out.append(g.multi_tool_trace(
            SYSTEM, rust_dev_tools(), user, todos, rationale,
            "read_file", [("file_path", fp)], "src1",
            src.replace('"', '\\"'),
            "The main function is short and self-contained; running it should produce the expected output.",
            "note_src",
            "cargo_run", [("project_path", pp)], "run1",
            f"status: success\\nexit_code: 0\\nstdout: {stdout}",
            "cargo_run printed the expected stdout for this binary.",
            "note_run",
            f"`{fp}` runs `{src}` and cargo_run prints: {stdout.replace(chr(92)+'n', '; ')}.",
        ))
    return out


def bulk_inspect_then_check_traces() -> list[str]:
    """Multi-step: read_file → cargo_check → response (no patch needed)."""
    out = []
    libs = [(n, k, s) for n, k, s in BULK_PROJECTS if k == "lib"]
    for name, _kind, src in libs:
        pp = _project_path(name)
        fp = _file_path(name, "lib")
        user = (
            f'Look at the source at "{fp}", then run cargo_check on "{pp}" to confirm it compiles cleanly.'
        )
        todos = [
            f"Read the source at {fp} to confirm the public API.",
            f"Run cargo_check on {pp} to verify compilation.",
        ]
        rationale = "Inspect first to ground the answer, then verify the crate type-checks."
        out.append(g.multi_tool_trace(
            SYSTEM, rust_dev_tools(), user, todos, rationale,
            "read_file", [("file_path", fp)], "src1",
            src.replace('"', '\\"'),
            "The file exposes a small public function; no compile-time concerns visible from the source alone.",
            "note_src",
            "cargo_check", [("project_path", pp)], "chk1",
            f"status: success\\nexit_code: 0\\nstdout: Checking {name} v0.1.0\\nFinished",
            "cargo_check passed; the crate type-checks cleanly.",
            "note_check",
            f"The source at `{fp}` defines `{src}` and the crate passes cargo_check cleanly.",
        ))
    return out


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
    traces.extend(bulk_read_traces())
    traces.extend(bulk_check_traces())
    traces.extend(bulk_build_traces())
    traces.extend(bulk_run_traces())
    traces.extend(bulk_test_traces())
    traces.extend(bulk_rustc_traces())
    traces.extend(bulk_inspect_then_check_traces())
    traces.extend(bulk_inspect_then_test_traces())
    traces.extend(bulk_inspect_then_run_traces())
    # Replicate each bulk multi-step trace with a second phrasing so the SFT
    # signal isn't too narrow. Combined with the static bugfix cases we land
    # near the 3000-row target.
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
