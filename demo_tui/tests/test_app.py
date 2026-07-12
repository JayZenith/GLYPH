from __future__ import annotations

import asyncio
from pathlib import Path

from textual.widgets import Static, TextArea

from demo_tui.app import GlyphDemoApp
from demo_tui.session import DemoConfig, DemoEvent


class FakeClient:
    async def close(self) -> None:
        return None


async def exercise_app() -> None:
    app = GlyphDemoApp(
        FakeClient(),
        DemoConfig(project=Path("demo-crate")),
        "http://gpu:8000/v1",
        "glyph",
    )
    async with app.run_test() as pilot:
        prompt = app.query_one("#prompt", TextArea)
        assert prompt.has_focus
        sidebar_values = [str(widget.render()) for widget in app.query(".sidebar-value")]
        assert any("gpu:8000" in value for value in sidebar_values)
        original_height = prompt.styles.height.value
        prompt.load_text("Fix the crate. " * 40)
        app._resize_prompt()
        assert prompt.styles.height.value > original_height
        await app._handle_event(DemoEvent("system", "SYS"))
        await app._handle_event(DemoEvent("user", "USR"))
        await app._handle_event(DemoEvent("assistant_start", round_index=1))
        await app._handle_event(DemoEvent("assistant_delta", "FINAL: done", round_index=1))
        await app._handle_event(DemoEvent("assistant_end", round_index=1))
        await app._handle_event(DemoEvent("tool_result", "RESULT c1:\nstatus: success", round_index=1))
        transcript = "\n".join(str(widget.render()) for widget in app.query("#transcript Static"))
        assert "<|im_start|>system\nSYS\n<|im_end|>" in transcript
        assert "<|im_start|>user\nUSR\n<|im_end|>" in transcript
        assert "<|im_start|>assistant\nFINAL: done\n<|im_end|>" in transcript
        assert "<|im_start|>tool\nRESULT c1:" in transcript
        await pilot.press("ctrl+l")
        assert "Transcript cleared" in str(app.query_one("#status", Static).render())


def test_app_mounts_and_keyboard_actions_work() -> None:
    asyncio.run(exercise_app())
