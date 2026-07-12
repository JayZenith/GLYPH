from __future__ import annotations

import asyncio
from pathlib import Path

from demo_tui.session import DemoConfig, GlyphDemoSession


class FakeBackend:
    def __init__(self, turns: list[str]) -> None:
        self.turns = iter(turns)
        self.prompts: list[str] = []

    async def stream(self, prompt: str):
        self.prompts.append(prompt)
        text = next(self.turns)
        midpoint = max(1, len(text) // 2)
        yield text[:midpoint]
        yield text[midpoint:]


class FakeBwrapFailureBackend:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def stream(self, prompt: str):
        self.prompts.append(prompt)
        yield 'CALL cargo_test {"id":"c1","project_path":"runs/demo/crate"}'


def make_crate(root: Path) -> Path:
    crate = root / "crate"
    (crate / "src").mkdir(parents=True)
    (crate / "Cargo.toml").write_text(
        '[package]\nname="demo"\nversion="0.1.0"\nedition="2021"\n'
    )
    (crate / "src/lib.rs").write_text("pub fn answer() -> u8 { 42 }\n")
    return crate


async def collect(session: GlyphDemoSession, prompt: str):
    return [event async for event in session.run(prompt)]


def test_session_runs_call_result_final_against_disposable_copy(tmp_path: Path) -> None:
    crate = make_crate(tmp_path)
    backend = FakeBackend(
        [
            'CALL read_file {"id":"c1","file_path":"runs/demo/crate/src/lib.rs"}',
            "FINAL: inspected the implementation",
        ]
    )
    session = GlyphDemoSession(
        backend,
        DemoConfig(
            project=crate,
            trace_prefix="runs/demo/crate",
            sandbox_root=tmp_path / "sandboxes",
            transcript_root=tmp_path / "transcripts",
        ),
    )
    events = asyncio.run(collect(session, "Inspect runs/demo/crate/src/lib.rs and report what it returns."))

    event_kinds = [event.kind for event in events]
    assert event_kinds[:3] == ["workspace", "system", "user"]
    assert event_kinds.count("assistant_start") == 2
    assert events[1].text == session.config.system_prompt
    assert events[2].text.startswith("Inspect runs/demo/crate")
    assert any(event.kind == "tool_result" and "pub fn answer" in event.text for event in events)
    assert events[-1].kind == "complete"
    assert session.sandbox_path is not None and session.sandbox_path != crate
    assert (crate / "src/lib.rs").read_text() == "pub fn answer() -> u8 { 42 }\n"
    assert "<|im_start|>tool\nRESULT c1:" in backend.prompts[1]
    saved = session.save_transcript()
    assert saved.exists()
    assert "FINAL: inspected the implementation" in saved.read_text()


def test_session_trims_overgenerated_assistant_role_continuations(tmp_path: Path) -> None:
    crate = make_crate(tmp_path)
    backend = FakeBackend(
        [
            (
                'CALL read_file {"id":"c1","file_path":"runs/demo/crate/src/lib.rs"}'
                '\n\nassistant\n'
                'CALL cargo_test {"id":"c2","project_path":"runs/demo/crate"}'
                '\n\nassistant\n'
                "FINAL: overgenerated"
            ),
            "FINAL: inspected after one tool",
        ]
    )
    session = GlyphDemoSession(
        backend,
        DemoConfig(
            project=crate,
            trace_prefix="runs/demo/crate",
            sandbox_root=tmp_path / "sandboxes",
            transcript_root=tmp_path / "transcripts",
        ),
    )

    events = asyncio.run(collect(session, "Inspect runs/demo/crate/src/lib.rs."))

    assert any(event.kind == "tool_result" and "pub fn answer" in event.text for event in events)
    assert events[-1].kind == "complete"
    assert "CALL cargo_test" not in session.messages[2]["content"]
    assert "FINAL: overgenerated" not in session.messages[2]["content"]


def test_session_appends_display_only_diff_to_patch_tool_result(tmp_path: Path) -> None:
    crate = make_crate(tmp_path)
    backend = FakeBackend(
        [
            (
                'CALL apply_patch {"id":"c1","file_path":"runs/demo/crate/src/lib.rs",'
                '"find":"pub fn answer() -> u8 { 42 }\\n",'
                '"replace":"pub fn answer() -> u8 { 7 }\\n"}'
            ),
            "FINAL: patched the implementation",
        ]
    )
    session = GlyphDemoSession(
        backend,
        DemoConfig(
            project=crate,
            trace_prefix="runs/demo/crate",
            sandbox_root=tmp_path / "sandboxes",
            transcript_root=tmp_path / "transcripts",
        ),
    )

    events = asyncio.run(collect(session, "Patch runs/demo/crate/src/lib.rs."))

    diff_events = [event for event in events if event.kind == "diff_result"]
    assert diff_events == []
    patch_result = next(event for event in events if event.kind == "tool_result")
    assert "RESULT c1:" in patch_result.text
    assert "PATCH DIFF:" in patch_result.text
    assert "--- a/src/lib.rs" in patch_result.text
    assert "+++ b/src/lib.rs" in patch_result.text
    assert "-pub fn answer() -> u8 { 42 }" in patch_result.text
    assert "+pub fn answer() -> u8 { 7 }" in patch_result.text
    assert all("PATCH DIFF" not in message["content"] for message in session.messages)


def test_session_stops_on_bubblewrap_infrastructure_failure(tmp_path: Path) -> None:
    crate = make_crate(tmp_path)
    session = GlyphDemoSession(
        FakeBwrapFailureBackend(),
        DemoConfig(
            project=crate,
            trace_prefix="runs/demo/crate",
            sandbox_root=tmp_path / "sandboxes",
            sandbox_backend="host",
        ),
    )

    async def fake_to_thread(func, *args):
        from agent_runtime.rust.executor import ExecutionResult

        return ExecutionResult(
            False,
            "",
            "bwrap: Creating new namespace failed: Resource temporarily unavailable",
            1,
        )

    original_to_thread = asyncio.to_thread
    asyncio.to_thread = fake_to_thread
    try:
        events = asyncio.run(collect(session, "Run tests."))
    finally:
        asyncio.to_thread = original_to_thread

    assert events[-1].kind == "error"
    assert "Bubblewrap cannot create a namespace" in events[-1].text


def test_session_stops_on_malformed_call(tmp_path: Path) -> None:
    crate = make_crate(tmp_path)
    session = GlyphDemoSession(
        FakeBackend(["CALL read_file not-json"]),
        DemoConfig(project=crate, sandbox_root=tmp_path / "sandboxes"),
    )

    events = asyncio.run(collect(session, "Inspect the crate."))

    assert events[-1].kind == "error"
    assert "Malformed CALL" in events[-1].text
