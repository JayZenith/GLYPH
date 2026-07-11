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

    assert [event.kind for event in events].count("assistant_start") == 2
    assert any(event.kind == "tool_result" and "pub fn answer" in event.text for event in events)
    assert events[-1].kind == "complete"
    assert session.sandbox_path is not None and session.sandbox_path != crate
    assert (crate / "src/lib.rs").read_text() == "pub fn answer() -> u8 { 42 }\n"
    assert "<|im_start|>tool\nRESULT c1:" in backend.prompts[1]
    saved = session.save_transcript()
    assert saved.exists()
    assert "FINAL: inspected the implementation" in saved.read_text()


def test_session_stops_on_malformed_call(tmp_path: Path) -> None:
    crate = make_crate(tmp_path)
    session = GlyphDemoSession(
        FakeBackend(["CALL read_file not-json"]),
        DemoConfig(project=crate, sandbox_root=tmp_path / "sandboxes"),
    )

    events = asyncio.run(collect(session, "Inspect the crate."))

    assert events[-1].kind == "error"
    assert "Malformed CALL" in events[-1].text
