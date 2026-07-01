from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False


class RustExecutor:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def _sanitize_output(self, text: str) -> str:
        cwd = str(Path.cwd())
        return text.replace(cwd + "/", "")

    def execute(
        self,
        command: list[str],
        working_dir: str | None = None,
    ) -> ExecutionResult:
        cargo_home = os.environ.get("CARGO_HOME", os.path.expanduser("~/.cargo"))
        rustup_home = os.environ.get("RUSTUP_HOME", os.path.expanduser("~/.rustup"))
        run_env = {
            "LANG": "en_US.UTF-8",
            "HOME": "/tmp",
            "TMPDIR": "/tmp",
            "CARGO_HOME": cargo_home,
            "RUSTUP_HOME": rustup_home,
            "PATH": os.pathsep.join(
                part
                for part in [
                    cargo_home + "/bin",
                    os.environ.get("PATH", ""),
                    "/usr/local/bin",
                    "/usr/bin",
                    "/bin",
                ]
                if part
            ),
        }
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=working_dir,
                env=run_env,
            )
            return ExecutionResult(
                success=result.returncode == 0,
                stdout=self._sanitize_output(result.stdout),
                stderr=self._sanitize_output(result.stderr),
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out after {self.timeout}s",
                exit_code=-1,
                timed_out=True,
            )
        except FileNotFoundError:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"command not found: {command[0]}",
                exit_code=-1,
            )
        except OSError as exc:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(exc),
                exit_code=getattr(exc, "errno", -1) or -1,
            )

    def cargo_run(self, project_path: str) -> ExecutionResult:
        return self.execute(["cargo", "run", "--quiet"], working_dir=project_path)

    def cargo_test(self, project_path: str) -> ExecutionResult:
        return self.execute(["cargo", "test"], working_dir=project_path)

    def read_file(self, file_path: str, max_chars: int = 4000) -> ExecutionResult:
        """Return file contents (truncated if huge). Pure in-process, no subprocess."""
        try:
            p = Path(file_path)
            if not p.exists():
                return ExecutionResult(False, "", f"file not found: {file_path}", -1)
            text = p.read_text(encoding="utf-8")
            if len(text) > max_chars:
                head = max_chars // 2 - 20
                tail = max_chars - head - 20
                text = f"{text[:head]}\n…[truncated]…\n{text[-tail:]}"
            return ExecutionResult(True, text, "", 0)
        except OSError as exc:
            return ExecutionResult(False, "", f"OSError: {exc}", -1)

    def apply_patch(self, file_path: str, find: str, replace: str) -> ExecutionResult:
        """Find-and-replace edit on a single file. `find` must occur exactly once.
        Pure in-process; no subprocess sandboxing (text edit, not arbitrary code)."""
        try:
            p = Path(file_path)
            if not p.exists():
                return ExecutionResult(False, "", f"file not found: {file_path}", -1)
            text = p.read_text(encoding="utf-8")
            count = text.count(find)
            if count == 0:
                return ExecutionResult(False, "", "find snippet not found in file", -1)
            if count > 1:
                return ExecutionResult(False, "", f"find snippet occurs {count} times; must be unique", -1)
            p.write_text(text.replace(find, replace, 1), encoding="utf-8")
            return ExecutionResult(True, "patch applied", "", 0)
        except OSError as exc:
            return ExecutionResult(False, "", f"OSError: {exc}", -1)
