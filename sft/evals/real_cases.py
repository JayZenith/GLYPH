from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RealEvalCase:
    name: str
    blueprint_root: str
    expected_output: str | None = None


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _cargo_toml(name: str) -> str:
    return f'[package]\nname = "{name}"\nversion = "0.1.0"\nedition = "2021"\n'


def _patch_test_pass(root: Path) -> RealEvalCase:
    project = root
    _write(project / "Cargo.toml", _cargo_toml("sumswap_eval"))
    _write(
        project / "src" / "lib.rs",
        (
            "pub fn sum_pair(a: i32, b: i32) -> i32 { a - b }\n\n"
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    use super::sum_pair;\n"
            "    #[test]\n"
            "    fn sums_values() {\n"
            "        assert_eq!(sum_pair(4, 6), 10);\n"
            "    }\n"
            "}\n"
        ),
    )
    return RealEvalCase("patch_test_pass_sumswap", str(project))


def _patch_run_pass(root: Path) -> RealEvalCase:
    project = root
    _write(project / "Cargo.toml", _cargo_toml("welcome_eval"))
    _write(project / "src" / "main.rs", 'fn main() { println!("Welcom, team!"); }\n')
    return RealEvalCase("patch_run_pass_welcome", str(project), "Welcome, team!")


def _patch_test_recover_once(root: Path) -> RealEvalCase:
    project = root
    _write(project / "Cargo.toml", _cargo_toml("triangle_eval"))
    _write(
        project / "src" / "lib.rs",
        (
            "pub fn triangle(n: i32) -> i32 { (1..n).sum() }\n\n"
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    use super::triangle;\n"
            "    #[test]\n"
            "    fn sums_inclusive_range() {\n"
            "        assert_eq!(triangle(5), 15);\n"
            "    }\n"
            "}\n"
        ),
    )
    return RealEvalCase("patch_test_recover_once_triangle", str(project))


def _patch_run_recover_once(root: Path) -> RealEvalCase:
    project = root
    _write(project / "Cargo.toml", _cargo_toml("banner_eval"))
    _write(project / "src" / "main.rs", 'fn main() { println!("ready"); }\n')
    return RealEvalCase("patch_run_recover_once_banner", str(project), "Ready!")


def _patch_test_recover_twice(root: Path) -> RealEvalCase:
    project = root
    _write(project / "Cargo.toml", _cargo_toml("signed_parse_eval"))
    _write(
        project / "src" / "lib.rs",
        (
            "pub fn parse_score(s: &str) -> i32 { s.parse::<u32>().unwrap_or(1) as i32 }\n\n"
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    use super::parse_score;\n"
            "    #[test]\n"
            "    fn invalid_defaults_to_zero() { assert_eq!(parse_score(\"oops\"), 0); }\n"
            "    #[test]\n"
            "    fn trims_input() { assert_eq!(parse_score(\" 12 \"), 12); }\n"
            "    #[test]\n"
            "    fn parses_signed_values() { assert_eq!(parse_score(\"-4\"), -4); }\n"
            "}\n"
        ),
    )
    return RealEvalCase("patch_test_recover_twice_signed_parse", str(project))


def _patch_run_recover_twice(root: Path) -> RealEvalCase:
    project = root
    _write(project / "Cargo.toml", _cargo_toml("counter_eval"))
    _write(project / "src" / "main.rs", 'fn main() { for n in 1..4 { print!("count {n} "); } }\n')
    return RealEvalCase("patch_run_recover_twice_counter", str(project), "Count: 1\nCount: 2\nCount: 3\nCount: 4")


def _test_only(root: Path) -> RealEvalCase:
    project = root
    _write(project / "Cargo.toml", _cargo_toml("passing_eval_suite"))
    _write(
        project / "src" / "lib.rs",
        (
            "pub fn square(n: i32) -> i32 { n * n }\n"
            "pub fn cube(n: i32) -> i32 { n * n * n }\n\n"
            "#[cfg(test)]\n"
            "mod tests {\n"
            "    use super::{cube, square};\n"
            "    #[test]\n"
            "    fn square_works() { assert_eq!(square(5), 25); }\n"
            "    #[test]\n"
            "    fn cube_works() { assert_eq!(cube(3), 27); }\n"
            "}\n"
        ),
    )
    return RealEvalCase("test_only_passing_suite", str(project))


def _run_only(root: Path) -> RealEvalCase:
    project = root
    _write(project / "Cargo.toml", _cargo_toml("run_eval"))
    _write(project / "src" / "main.rs", 'fn main() { println!("total={}", 4 + 5); }\n')
    return RealEvalCase("run_only_total", str(project), "total=9")


def _read_only(root: Path) -> RealEvalCase:
    project = root
    _write(project / "Cargo.toml", _cargo_toml("read_eval_lib"))
    _write(
        project / "src" / "lib.rs",
        'pub fn headline(name: &str) -> String { format!("Headline: {name}") }\n',
    )
    return RealEvalCase("read_only_headline", str(project))


BUILDERS = {
    "patch_test_pass_sumswap": _patch_test_pass,
    "patch_run_pass_welcome": _patch_run_pass,
    "patch_test_recover_once_triangle": _patch_test_recover_once,
    "patch_run_recover_once_banner": _patch_run_recover_once,
    "patch_test_recover_twice_signed_parse": _patch_test_recover_twice,
    "patch_run_recover_twice_counter": _patch_run_recover_twice,
    "test_only_passing_suite": _test_only,
    "run_only_total": _run_only,
    "read_only_headline": _read_only,
}


def materialize_case(case_name: str, root: Path) -> RealEvalCase:
    builder = BUILDERS.get(case_name)
    if builder is None:
        raise KeyError(f"Unknown real eval case: {case_name}")
    root.mkdir(parents=True, exist_ok=True)
    return builder(root)
