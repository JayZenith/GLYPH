from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
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
    def __init__(self, timeout: int = 30, sandbox_backend: str = "auto", allow_unsafe_host_execution: bool = False):
        self.timeout = timeout
        if sandbox_backend not in {"auto", "bwrap", "host"}:
            raise ValueError("sandbox_backend must be one of: auto, bwrap, host")
        self.sandbox_backend = sandbox_backend
        self.allow_unsafe_host_execution = allow_unsafe_host_execution
        self._protected_snapshots: dict[str, dict[str, tuple[str, str]]] = {}
        self._snapshot_lock = threading.Lock()

    def _sanitize_output(self, text: str) -> str:
        cwd = str(Path.cwd())
        return text.replace(cwd + "/", "")

    def execute(
        self,
        command: list[str],
        working_dir: str | None = None,
        allowed_root: str | Path | None = None,
    ) -> ExecutionResult:
        if allowed_root is None:
            return ExecutionResult(False, "", "refusing execution without an allowed_root", -1)
        try:
            root = Path(allowed_root).resolve(strict=True)
            cwd = self._confined_path(working_dir or ".", root, require_exists=True)
        except (OSError, ValueError) as exc:
            return ExecutionResult(False, "", f"path confinement error: {exc}", -1)
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
        backend = self._resolved_backend()
        if backend is None:
            return ExecutionResult(False, "", "bubblewrap is unavailable; refusing unsafe host execution (set allow_unsafe_host_execution=True and sandbox_backend='host' only inside an external container)", -1)
        run_command = command
        run_cwd = str(cwd)
        if backend == "bwrap":
            run_command, run_cwd, run_env = self._bubblewrap_command(command, root, cwd, Path(cargo_home), Path(rustup_home))
        try:
            process = subprocess.Popen(
                run_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=run_cwd,
                env=run_env,
                start_new_session=True,
            )
            try:
                stdout, stderr = process.communicate(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                return ExecutionResult(False, "", f"Execution timed out after {self.timeout}s", -1, timed_out=True)
            return ExecutionResult(
                success=process.returncode == 0,
                stdout=self._sanitize_output(stdout),
                stderr=self._sanitize_output(stderr),
                exit_code=process.returncode,
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

    def _resolved_backend(self) -> str | None:
        if self.sandbox_backend == "bwrap":
            return "bwrap" if shutil.which("bwrap") else None
        if self.sandbox_backend == "host":
            return "host" if self.allow_unsafe_host_execution else None
        if shutil.which("bwrap"):
            return "bwrap"
        return None

    @staticmethod
    def _protected_state(root: Path) -> dict[str, tuple[str, str]]:
        state: dict[str, tuple[str, str]] = {}
        for path in root.rglob("*"):
            rel = path.relative_to(root)
            if rel.parts and rel.parts[0] in {"target", ".git"}:
                continue
            if path.is_symlink() or not path.is_file():
                continue
            fully_protected = path.name in {"Cargo.toml", "build.rs"} or any(part in {"tests", "benches", ".cargo"} for part in rel.parts)
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if fully_protected:
                state[str(rel)] = ("full", text)
            elif path.suffix == ".rs" and "#[cfg(test)]" in text:
                state[str(rel)] = ("test_suffix", text[text.index("#[cfg(test)]"):])
        return state

    def ensure_protected_snapshot(self, allowed_root: str | Path) -> str | None:
        try:
            root = Path(allowed_root).resolve(strict=True)
        except OSError as exc:
            return f"cannot snapshot protected files: {exc}"
        key = str(root)
        with self._snapshot_lock:
            self._protected_snapshots.setdefault(key, self._protected_state(root))
        return None

    def validate_protected_snapshot(self, allowed_root: str | Path) -> str | None:
        error = self.ensure_protected_snapshot(allowed_root)
        if error:
            return error
        root = Path(allowed_root).resolve(strict=True)
        expected = self._protected_snapshots[str(root)]
        current_state = self._protected_state(root)
        if current_state.keys() != expected.keys():
            return "protected grading/build file set changed outside apply_patch"
        for rel, (mode, original) in expected.items():
            current = current_state[rel][1]
            if mode == "test_suffix":
                if current != original:
                    return f"protected test content changed outside apply_patch: {rel}"
            elif current != original:
                return f"protected grading/build file changed outside apply_patch: {rel}"
        return None

    @staticmethod
    def _confined_path(value: str | Path, root: Path, require_exists: bool = False) -> Path:
        raw = Path(value)
        candidate = raw.resolve(strict=False) if raw.is_absolute() else (Path.cwd() / raw).resolve(strict=False)
        try:
            candidate.relative_to(root)
        except ValueError:
            candidate = (root / raw).resolve(strict=False)
        candidate.relative_to(root)
        if require_exists and not candidate.exists():
            raise FileNotFoundError(candidate)
        return candidate

    @staticmethod
    def _bubblewrap_command(command: list[str], root: Path, cwd: Path, cargo_home: Path, rustup_home: Path) -> tuple[list[str], str, dict[str, str]]:
        rel_cwd = cwd.relative_to(root)
        args = ["bwrap", "--die-with-parent", "--new-session", "--unshare-all", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--dir", "/opt", "--dir", "/opt/cargo", "--bind", str(root), "/workspace", "--chdir", str(Path("/workspace") / rel_cwd)]
        for system_dir in ("/usr", "/bin", "/lib", "/lib64", "/etc"):
            if Path(system_dir).exists():
                args.extend(["--ro-bind", system_dir, system_dir])
        # Mount only tool proxies and dependency caches; never expose Cargo credentials.
        for name in ("bin", "registry", "git"):
            source = cargo_home / name
            if source.exists():
                args.extend(["--ro-bind", str(source), f"/opt/cargo/{name}"])
        if rustup_home.exists():
            args.extend(["--ro-bind", str(rustup_home), "/opt/rustup"])
        args.extend(["--", *command])
        if shutil.which("prlimit"):
            args = ["prlimit", "--nproc=256", "--as=8589934592", "--fsize=1073741824", "--", *args]
        env = {"LANG": "en_US.UTF-8", "HOME": "/tmp", "TMPDIR": "/tmp", "CARGO_HOME": "/opt/cargo", "RUSTUP_HOME": "/opt/rustup", "CARGO_NET_OFFLINE": "true", "PATH": "/opt/cargo/bin:/usr/local/bin:/usr/bin:/bin"}
        return args, str(root), env

    def cargo_run(self, project_path: str, allowed_root: str | Path | None = None) -> ExecutionResult:
        return self.execute(["cargo", "run", "--quiet"], working_dir=project_path, allowed_root=allowed_root)

    def cargo_test(self, project_path: str, allowed_root: str | Path | None = None) -> ExecutionResult:
        return self.execute(["cargo", "test"], working_dir=project_path, allowed_root=allowed_root)

    def read_file(self, file_path: str, max_chars: int = 4000, allowed_root: str | Path | None = None) -> ExecutionResult:
        """Return file contents (truncated if huge). Pure in-process, no subprocess."""
        try:
            if allowed_root is None:
                return ExecutionResult(False, "", "refusing file access without an allowed_root", -1)
            p = self._confined_path(file_path, Path(allowed_root).resolve(strict=True), require_exists=True)
            if not p.exists():
                return ExecutionResult(False, "", f"file not found: {file_path}", -1)
            text = p.read_text(encoding="utf-8")
            if len(text) > max_chars:
                head = max_chars // 2 - 20
                tail = max_chars - head - 20
                text = f"{text[:head]}\n…[truncated]…\n{text[-tail:]}"
            return ExecutionResult(True, text, "", 0)
        except (OSError, ValueError) as exc:
            return ExecutionResult(False, "", f"OSError: {exc}", -1)

    def apply_patch(self, file_path: str, find: str, replace: str, allowed_root: str | Path | None = None) -> ExecutionResult:
        """Confined find-and-replace; grading and build-control files are immutable."""
        try:
            if allowed_root is None:
                return ExecutionResult(False, "", "refusing file access without an allowed_root", -1)
            root = Path(allowed_root).resolve(strict=True)
            p = self._confined_path(file_path, root, require_exists=True)
            if not p.exists():
                return ExecutionResult(False, "", f"file not found: {file_path}", -1)
            rel = p.relative_to(root)
            if p.name in {"Cargo.toml", "build.rs"} or any(part in {"tests", "benches", ".cargo"} for part in rel.parts):
                return ExecutionResult(False, "", f"protected grading/build file: {rel}", -1)
            protected_markers = ("#[test]", "#[cfg(test)]", "mod tests", "assert!", "assert_eq!", "assert_ne!")
            if any(marker in find or marker in replace for marker in protected_markers):
                return ExecutionResult(False, "", "patch touches protected grading-test markers", -1)
            text = p.read_text(encoding="utf-8")
            count = text.count(find)
            if count == 0:
                return ExecutionResult(False, "", "find snippet not found in file", -1)
            if count > 1:
                return ExecutionResult(False, "", f"find snippet occurs {count} times; must be unique", -1)
            updated = text.replace(find, replace, 1)
            marker = "#[cfg(test)]"
            if marker in text:
                if marker not in updated or text[text.index(marker):] != updated[updated.index(marker):]:
                    return ExecutionResult(False, "", "patch would modify protected #[cfg(test)] content", -1)
            elif marker in updated:
                return ExecutionResult(False, "", "patch would introduce protected #[cfg(test)] content", -1)
            p.write_text(updated, encoding="utf-8")
            return ExecutionResult(True, "patch applied", "", 0)
        except (OSError, ValueError) as exc:
            return ExecutionResult(False, "", f"OSError: {exc}", -1)
