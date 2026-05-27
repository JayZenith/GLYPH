#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sft.evals.prompt_loader import build_prompt


SYSTEM_PROMPT = "You are a Rust coding agent. Use tools when needed. After FINAL, stop immediately."


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def cargo_toml(name: str) -> str:
    return f'[package]\nname = "{name}"\nversion = "0.1.0"\nedition = "2021"\n'


def materialize_patch_test_pass(root: Path) -> dict:
    project = root / "addlib_bug"
    write(project / "Cargo.toml", cargo_toml("addlib_bug"))
    write(
        project / "src" / "lib.rs",
        (
            "pub fn add(a: i32, b: i32) -> i32 { a - b }\n\n"
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    use super::add;\n"
            "    #[test]\n"
            "    fn adds_two_numbers() {\n"
            "        assert_eq!(add(2, 3), 5);\n"
            "    }\n"
            "}\n"
        ),
    )
    return {
        "kind": "patch_test_pass",
        "prompt": build_prompt(
            f"Fix the failing crate at {project}. Read src/lib.rs, patch the bug, run cargo_test, then answer once.",
            SYSTEM_PROMPT,
        ),
        "expected_tool": "read_file",
        "expected_args": {"file_path": str(project / "src" / "lib.rs")},
        "expected_tool_sequence": ["read_file", "apply_patch", "cargo_test"],
        "blueprint_root": str(project),
    }


def materialize_patch_run_pass(root: Path) -> dict:
    project = root / "greeter_bug"
    write(project / "Cargo.toml", cargo_toml("greeter_bug"))
    write(project / "src" / "main.rs", 'fn main() { println!("Helo, world!"); }\n')
    return {
        "kind": "patch_run_pass",
        "prompt": build_prompt(
            f"Fix the crate at {project}. Read src/main.rs, patch the greeting bug, run cargo_run, then answer once.",
            SYSTEM_PROMPT,
        ),
        "expected_tool": "read_file",
        "expected_args": {"file_path": str(project / "src" / "main.rs")},
        "expected_tool_sequence": ["read_file", "apply_patch", "cargo_run"],
        "blueprint_root": str(project),
        "expected_output": "Hello, world!",
    }


def materialize_patch_test_recover_once(root: Path) -> dict:
    project = root / "range_bug"
    write(project / "Cargo.toml", cargo_toml("range_bug"))
    write(
        project / "src" / "lib.rs",
        (
            "pub fn sum_to(n: i32) -> i32 { (0..n).sum() }\n\n"
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    use super::sum_to;\n"
            "    #[test]\n"
            "    fn sum_to_includes_n() {\n"
            "        assert_eq!(sum_to(5), 15);\n"
            "    }\n"
            "}\n"
        ),
    )
    return {
        "kind": "patch_test_recover_once",
        "prompt": build_prompt(
            f"Fix the crate at {project}. Read src/lib.rs, patch the bug, run cargo_test, and keep going until tests pass, then answer once.",
            SYSTEM_PROMPT,
        ),
        "expected_tool": "read_file",
        "expected_args": {"file_path": str(project / "src" / "lib.rs")},
        "expected_tool_sequence": ["read_file", "apply_patch", "cargo_test", "read_file", "apply_patch", "cargo_test"],
        "blueprint_root": str(project),
    }


def materialize_patch_run_recover_once(root: Path) -> dict:
    project = root / "banner_bug"
    write(project / "Cargo.toml", cargo_toml("banner_bug"))
    write(project / "src" / "main.rs", 'fn main() { println!("welcom"); }\n')
    return {
        "kind": "patch_run_recover_once",
        "prompt": build_prompt(
            f"Fix the crate at {project}. Read src/main.rs, patch the bug, run cargo_run, and keep going until the output is correct, then answer once.",
            SYSTEM_PROMPT,
        ),
        "expected_tool": "read_file",
        "expected_args": {"file_path": str(project / "src" / "main.rs")},
        "expected_tool_sequence": ["read_file", "apply_patch", "cargo_run", "read_file", "apply_patch", "cargo_run"],
        "blueprint_root": str(project),
        "expected_output": "Welcome!",
    }


def materialize_patch_test_recover_twice(root: Path) -> dict:
    project = root / "parser_bug"
    write(project / "Cargo.toml", cargo_toml("parser_bug"))
    write(
        project / "src" / "lib.rs",
        (
            "pub fn parse_num(s: &str) -> i32 { s.parse::<u32>().unwrap_or(1) as i32 }\n\n"
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    use super::parse_num;\n"
            "    #[test]\n"
            "    fn parse_default() { assert_eq!(parse_num(\"nope\"), 0); }\n"
            "    #[test]\n"
            "    fn parse_trimmed() { assert_eq!(parse_num(\" 7 \"), 7); }\n"
            "    #[test]\n"
            "    fn parse_signed() { assert_eq!(parse_num(\"-7\"), -7); }\n"
            "}\n"
        ),
    )
    return {
        "kind": "patch_test_recover_twice",
        "prompt": build_prompt(
            f"Fix the crate at {project}. Read src/lib.rs, patch the bug, run cargo_test, and keep iterating until tests pass, then answer once.",
            SYSTEM_PROMPT,
        ),
        "expected_tool": "read_file",
        "expected_args": {"file_path": str(project / "src" / "lib.rs")},
        "expected_tool_sequence": [
            "read_file",
            "apply_patch",
            "cargo_test",
            "read_file",
            "apply_patch",
            "cargo_test",
            "read_file",
            "apply_patch",
            "cargo_test",
        ],
        "blueprint_root": str(project),
    }


def materialize_patch_run_recover_twice(root: Path) -> dict:
    project = root / "counter_bug"
    write(project / "Cargo.toml", cargo_toml("counter_bug"))
    write(
        project / "src" / "main.rs",
        'fn main() { for n in 1..4 { print!("count {n} "); } }\n',
    )
    return {
        "kind": "patch_run_recover_twice",
        "prompt": build_prompt(
            f"Fix the crate at {project}. Read src/main.rs, patch the bug, run cargo_run, and keep iterating until the output is correct, then answer once.",
            SYSTEM_PROMPT,
        ),
        "expected_tool": "read_file",
        "expected_args": {"file_path": str(project / "src" / "main.rs")},
        "expected_tool_sequence": [
            "read_file",
            "apply_patch",
            "cargo_run",
            "read_file",
            "apply_patch",
            "cargo_run",
            "read_file",
            "apply_patch",
            "cargo_run",
        ],
        "blueprint_root": str(project),
        "expected_output": "Count: 1\nCount: 2\nCount: 3\nCount: 4",
    }


def materialize_test_only(root: Path) -> dict:
    project = root / "passing_suite"
    write(project / "Cargo.toml", cargo_toml("passing_suite"))
    write(
        project / "src" / "lib.rs",
        (
            "pub fn add(a: i32, b: i32) -> i32 { a + b }\n"
            "pub fn mul(a: i32, b: i32) -> i32 { a * b }\n\n"
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    use super::{add, mul};\n"
            "    #[test]\n"
            "    fn add_works() { assert_eq!(add(2, 3), 5); }\n"
            "    #[test]\n"
            "    fn mul_works() { assert_eq!(mul(4, 5), 20); }\n"
            "}\n"
        ),
    )
    return {
        "kind": "test_only",
        "prompt": build_prompt(
            f"Run cargo_test on {project} and report the result in one final answer.",
            SYSTEM_PROMPT,
        ),
        "expected_tool": "cargo_test",
        "expected_args": {"project_path": str(project)},
        "expected_tool_sequence": ["cargo_test"],
    }


def materialize_run_only(root: Path) -> dict:
    project = root / "run_eval"
    write(project / "Cargo.toml", cargo_toml("run_eval"))
    write(project / "src" / "main.rs", 'fn main() { println!("total={}", 4 + 5); }\n')
    return {
        "kind": "run_only",
        "prompt": build_prompt(
            f"Run cargo_run on {project} and report the result in one final answer.",
            SYSTEM_PROMPT,
        ),
        "expected_tool": "cargo_run",
        "expected_args": {"project_path": str(project)},
        "expected_tool_sequence": ["cargo_run"],
        "expected_output": "total=9",
    }


def materialize_read_only(root: Path) -> dict:
    project = root / "showcase_lib"
    write(project / "Cargo.toml", cargo_toml("showcase_lib"))
    write(
        project / "src" / "lib.rs",
        'pub fn greet(name: &str) -> String { format!("Hello, {name}!") }\n',
    )
    return {
        "kind": "read_only",
        "prompt": build_prompt(
            f"Read {project / 'src' / 'lib.rs'} and summarize what it does in one final answer.",
            SYSTEM_PROMPT,
        ),
        "expected_tool": "read_file",
        "expected_args": {"file_path": str(project / "src" / "lib.rs")},
        "expected_tool_sequence": ["read_file"],
    }


def build_cases(root: Path) -> list[dict]:
    return [
        materialize_patch_test_pass(root),
        materialize_patch_run_pass(root),
        materialize_patch_test_recover_once(root),
        materialize_patch_run_recover_once(root),
        materialize_patch_test_recover_twice(root),
        materialize_patch_run_recover_twice(root),
        materialize_test_only(root),
        materialize_run_only(root),
        materialize_read_only(root),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare one RL prompt for each active Rust case family.")
    parser.add_argument("--root", type=Path, default=Path("runs/rlvr1/rust_cases"))
    parser.add_argument("--output", type=Path, default=Path("runs/rlvr1/prompts.jsonl"))
    args = parser.parse_args()

    root = args.root
    root.mkdir(parents=True, exist_ok=True)
    rows = build_cases(root)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Wrote {len(rows)} RL cases to {args.output}")
    for row in rows:
        print(f"  - {row['kind']}: {row['expected_tool_sequence']}")


if __name__ == "__main__":
    main()
