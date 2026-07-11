import os
from pathlib import Path

import pytest

from agent_runtime.rust.executor import RustExecutor
from agent_runtime.rust.runtime import execute_rust_tool


def _crate(tmp_path: Path) -> Path:
    root = tmp_path / "crate"
    (root / "src").mkdir(parents=True)
    (root / "Cargo.toml").write_text('[package]\nname="secure"\nversion="0.1.0"\nedition="2021"\n')
    (root / "src/lib.rs").write_text(
        "pub fn value() -> u8 { 1 }\n\n"
        "#[cfg(test)]\nmod tests {\n"
        "    #[test]\n    fn value_is_one() { assert_eq!(super::value(), 1); }\n}\n"
    )
    return root


def test_file_access_is_confined_and_symlinks_cannot_escape(tmp_path: Path) -> None:
    root = _crate(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    (root / "escape").symlink_to(outside)
    executor = RustExecutor()

    assert execute_rust_tool(
        executor, "read_file", {"file_path": "src/lib.rs"}, allowed_root=root
    ).success
    assert not execute_rust_tool(
        executor, "read_file", {"file_path": str(outside)}, allowed_root=root
    ).success
    assert not execute_rust_tool(
        executor, "read_file", {"file_path": "escape"}, allowed_root=root
    ).success


def test_grading_and_build_files_are_immutable(tmp_path: Path) -> None:
    root = _crate(tmp_path)
    executor = RustExecutor()
    source = (root / "src/lib.rs").read_text()
    tests = source[source.index("#[cfg(test)]"):]

    test_edit = execute_rust_tool(
        executor,
        "apply_patch",
        {"file_path": "src/lib.rs", "find": tests, "replace": tests.replace("1);", "2);", 1)},
        allowed_root=root,
    )
    manifest_edit = execute_rust_tool(
        executor,
        "apply_patch",
        {"file_path": "Cargo.toml", "find": 'name="secure"', "replace": 'name="cheat"'},
        allowed_root=root,
    )
    production_edit = execute_rust_tool(
        executor,
        "apply_patch",
        {"file_path": "src/lib.rs", "find": "{ 1 }", "replace": "{ 2 }"},
        allowed_root=root,
    )

    assert not test_edit.success
    assert not manifest_edit.success
    assert production_edit.success


def test_host_execution_requires_explicit_unsafe_opt_in(tmp_path: Path) -> None:
    root = _crate(tmp_path)
    refused = RustExecutor(sandbox_backend="host").execute(
        ["/bin/true"], working_dir=".", allowed_root=root
    )
    auto_does_not_fallback = RustExecutor(allow_unsafe_host_execution=True)
    auto_does_not_fallback._resolved_backend = lambda: None
    auto_refused = auto_does_not_fallback.execute(
        ["/bin/true"], working_dir=".", allowed_root=root
    )
    allowed = RustExecutor(
        sandbox_backend="host", allow_unsafe_host_execution=True
    ).execute(["/bin/true"], working_dir=".", allowed_root=root)

    assert not refused.success
    assert "refusing unsafe host execution" in refused.stderr
    assert not auto_refused.success
    assert allowed.success


def test_external_test_mutation_is_detected_before_cargo(tmp_path: Path) -> None:
    root = _crate(tmp_path)
    executor = RustExecutor(sandbox_backend="host", allow_unsafe_host_execution=True)
    assert execute_rust_tool(
        executor, "read_file", {"file_path": "src/lib.rs"}, allowed_root=root
    ).success
    source = (root / "src/lib.rs").read_text()
    (root / "src/lib.rs").write_text(source.replace("assert_eq!(super::value(), 1)", "assert!(true)"))

    result = execute_rust_tool(
        executor, "cargo_test", {"project_path": "."}, allowed_root=root
    )
    assert not result.success
    assert "protected test content changed" in result.stderr


def test_new_external_test_file_is_detected_before_cargo(tmp_path: Path) -> None:
    root = _crate(tmp_path)
    executor = RustExecutor(sandbox_backend="host", allow_unsafe_host_execution=True)
    assert execute_rust_tool(
        executor, "read_file", {"file_path": "src/lib.rs"}, allowed_root=root
    ).success
    (root / "tests").mkdir()
    (root / "tests/cheat.rs").write_text("#[test] fn cheat() { assert!(true); }")

    result = execute_rust_tool(
        executor, "cargo_test", {"project_path": "."}, allowed_root=root
    )
    assert not result.success
    assert "file set changed" in result.stderr


def test_bubblewrap_mount_excludes_cargo_credentials(tmp_path: Path) -> None:
    root = _crate(tmp_path)
    cargo_home = tmp_path / "cargo"
    rustup_home = tmp_path / "rustup"
    for name in ("bin", "registry", "git"):
        (cargo_home / name).mkdir(parents=True)
    rustup_home.mkdir()
    (cargo_home / "credentials.toml").write_text('[registry]\ntoken="secret"\n')

    args, _, _ = RustExecutor._bubblewrap_command(
        ["/bin/true"], root, root, cargo_home, rustup_home
    )
    sources = [
        args[index + 1]
        for index, value in enumerate(args[:-2])
        if value in {"--bind", "--ro-bind"}
    ]

    assert str(cargo_home) not in sources
    assert str(cargo_home / "bin") in sources
    assert str(cargo_home / "registry") in sources
    assert str(cargo_home / "git") in sources
    assert all("credentials" not in source for source in sources)


def test_bubblewrap_runs_cargo_integration(tmp_path: Path) -> None:
    root = _crate(tmp_path)
    result = RustExecutor(timeout=60).cargo_test(".", allowed_root=root)
    required = os.environ.get("GLYPH_REQUIRE_BWRAP_TEST") == "1"
    if not required and not result.success and "bwrap:" in result.stderr:
        pytest.skip(f"Bubblewrap unavailable in this host environment: {result.stderr.strip()}")
    assert result.success, result.stderr
