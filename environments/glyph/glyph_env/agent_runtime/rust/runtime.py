from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from .executor import ExecutionResult, RustExecutor


SUPPORTED_RUST_TOOLS = {"cargo_test", "cargo_run", "read_file", "apply_patch"}


def execute_rust_tool(
    executor: RustExecutor,
    tool_name: str,
    params: dict,
    expected_output: str | None = None,
) -> ExecutionResult:
    if tool_name == "cargo_test":
        return executor.cargo_test(params.get("project_path", "."))
    if tool_name == "cargo_run":
        result = executor.cargo_run(params.get("project_path", "."))
        if result.success and expected_output is not None and result.stdout.strip() != expected_output.strip():
            return ExecutionResult(
                False,
                result.stdout,
                f'expected exact output "{expected_output}"',
                result.exit_code,
                timed_out=result.timed_out,
            )
        return result
    if tool_name == "read_file":
        file_path = params.get("file_path")
        if not file_path:
            return ExecutionResult(False, "", "missing file_path", -1)
        return executor.read_file(file_path)
    if tool_name == "apply_patch":
        file_path = params.get("file_path")
        find = params.get("find")
        replace = params.get("replace")
        if not file_path or find is None or replace is None:
            return ExecutionResult(False, "", "apply_patch needs file_path, find, replace", -1)
        return executor.apply_patch(file_path, find, replace)
    return ExecutionResult(False, "", f"unknown tool: {tool_name}", -1)


def rewrite_path(value: str, blueprint_root: str, sandbox_root: str) -> str:
    if isinstance(value, str) and value.startswith(blueprint_root):
        return sandbox_root + value[len(blueprint_root):]
    return value


def rewrite_params_for_sandbox(params: dict, blueprint_root: str, sandbox_root: str) -> dict:
    return {
        key: rewrite_path(value, blueprint_root, sandbox_root) if isinstance(value, str) else value
        for key, value in params.items()
    }


def ensure_sandbox_copy(
    blueprint_root: str,
    sandbox_root: Path,
    run_id: str | None = None,
) -> tuple[str, str]:
    blueprint = Path(blueprint_root)
    rollout_id = run_id or uuid.uuid4().hex[:12]
    sandbox = sandbox_root / rollout_id / blueprint.name
    sandbox.parent.mkdir(parents=True, exist_ok=True)
    if blueprint.is_dir():
        shutil.copytree(blueprint, sandbox, dirs_exist_ok=True)
    else:
        shutil.copy2(blueprint, sandbox)
    return rollout_id, str(sandbox)
