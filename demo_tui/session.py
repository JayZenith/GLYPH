from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from agent_runtime.chatml import DEFAULT_SYSTEM_PROMPT, render_messages
from agent_runtime.protocol import call_syntax_errors, has_final, parse_calls, strip_generated_assistant_stop
from agent_runtime.rust.executor import RustExecutor
from agent_runtime.rust.results import format_result_block
from agent_runtime.rust.runtime import ensure_sandbox_copy, execute_rust_tool, rewrite_params_for_sandbox


class CompletionBackend(Protocol):
    async def stream(self, prompt: str) -> AsyncIterator[str]: ...


@dataclass(frozen=True)
class DemoConfig:
    project: Path
    trace_prefix: str | None = None
    sandbox_root: Path = Path("runs/demo_tui/sandboxes")
    transcript_root: Path = Path("runs/demo_tui/transcripts")
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    expected_output: str | None = None
    max_tool_rounds: int = 20
    tool_timeout: int = 30
    sandbox_backend: str = "auto"
    allow_unsafe_host_execution: bool = False


@dataclass(frozen=True)
class DemoEvent:
    kind: str
    text: str = ""
    round_index: int = 0


class GlyphDemoSession:
    """One interactive prompt, one disposable crate, one audited tool loop."""

    def __init__(self, backend: CompletionBackend, config: DemoConfig) -> None:
        self.backend = backend
        self.config = config
        self.messages: list[dict[str, str]] = []
        self.sandbox_path: Path | None = None
        self._executed_call_ids: set[str] = set()

    @property
    def transcript(self) -> str:
        return render_messages(self.messages)

    def save_transcript(self) -> Path:
        root = self.config.transcript_root.expanduser()
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        path = root / f"glyph_demo_{stamp}.chatml"
        path.write_text(self.transcript, encoding="utf-8")
        return path

    def _prepare(self, user_prompt: str) -> None:
        project = self.config.project.expanduser().resolve(strict=True)
        if not project.is_dir():
            raise ValueError(f"project is not a directory: {project}")
        _, sandbox = ensure_sandbox_copy(project, self.config.sandbox_root.expanduser())
        self.sandbox_path = Path(sandbox).resolve(strict=True)
        self.messages = [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user", "content": user_prompt.strip()},
        ]
        self._executed_call_ids.clear()

    async def run(self, user_prompt: str) -> AsyncIterator[DemoEvent]:
        if not user_prompt.strip():
            yield DemoEvent("error", "Enter a task before starting the agent.")
            return
        try:
            self._prepare(user_prompt)
        except (OSError, ValueError) as exc:
            yield DemoEvent("error", str(exc))
            return

        assert self.sandbox_path is not None
        yield DemoEvent("workspace", str(self.sandbox_path))
        yield DemoEvent("system", self.config.system_prompt)
        yield DemoEvent("user", user_prompt.strip())
        executor = RustExecutor(
            timeout=self.config.tool_timeout,
            sandbox_backend=self.config.sandbox_backend,
            allow_unsafe_host_execution=self.config.allow_unsafe_host_execution,
        )
        project_prefix = str(self.config.project.expanduser().resolve())
        trace_prefixes = [
            prefix
            for prefix in (self.config.trace_prefix, str(self.config.project), project_prefix)
            if prefix
        ]

        for round_index in range(1, self.config.max_tool_rounds + 1):
            yield DemoEvent("assistant_start", round_index=round_index)
            prompt = render_messages(self.messages, add_generation_prompt=True)
            pieces: list[str] = []
            try:
                async for piece in self.backend.stream(prompt):
                    pieces.append(piece)
                    yield DemoEvent("assistant_delta", piece, round_index)
            except Exception as exc:
                yield DemoEvent("error", f"vLLM request failed: {exc}", round_index)
                return

            assistant = strip_generated_assistant_stop("".join(pieces))
            if not assistant:
                yield DemoEvent("error", "The model returned an empty assistant turn.", round_index)
                return
            self.messages.append({"role": "assistant", "content": assistant})
            yield DemoEvent("assistant_end", round_index=round_index)

            syntax_errors = call_syntax_errors(assistant)
            if syntax_errors:
                yield DemoEvent("error", "\n".join(syntax_errors), round_index)
                return

            calls = parse_calls(assistant)
            if has_final(assistant):
                if calls:
                    yield DemoEvent("error", "Assistant emitted CALL and FINAL in the same turn.", round_index)
                else:
                    yield DemoEvent("complete", assistant, round_index)
                return
            if not calls:
                yield DemoEvent("error", "Assistant emitted neither CALL nor FINAL.", round_index)
                return

            for call in calls:
                if call.id in self._executed_call_ids:
                    yield DemoEvent("error", f"Duplicate CALL id: {call.id}", round_index)
                    return
                self._executed_call_ids.add(call.id)
                params = call.params
                for trace_prefix in trace_prefixes:
                    params = rewrite_params_for_sandbox(
                        params, trace_prefix, str(self.sandbox_path)
                    )
                yield DemoEvent("tool_start", f"{call.tool} · {call.id}", round_index)
                result = await asyncio.to_thread(
                    execute_rust_tool,
                    executor,
                    call.tool,
                    params,
                    self.config.expected_output if call.tool == "cargo_run" else None,
                    self.sandbox_path,
                )
                result_block = format_result_block(call.id, result)
                self.messages.append({"role": "tool", "content": result_block})
                yield DemoEvent("tool_result", result_block, round_index)

        yield DemoEvent("error", f"Stopped after {self.config.max_tool_rounds} tool rounds.")
