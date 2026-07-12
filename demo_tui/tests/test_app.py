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
        topbar = str(app.query_one("#topbar", Static).render())
        assert "gpu:8000" in topbar
        assert "demo-crate" in topbar
        original_height = prompt.styles.height.value
        await pilot.press("F")
        await pilot.press("i")
        await pilot.press("x")
        assert prompt.text == "Fix"
        prompt.clear()
        prompt.load_text("Fix the crate. " * 40)
        app._resize_prompt()
        assert prompt.styles.height.value > original_height
        submitted: list[str] = []
        app.run_agent = submitted.append
        prompt.load_text("Run the eval case")
        await pilot.press("enter")
        assert submitted == ["Run the eval case"]
        await app._handle_event(DemoEvent("system", "SYS"))
        await app._handle_event(DemoEvent("user", "USR"))
        await app._handle_event(DemoEvent("assistant_start", round_index=1))
        await app._handle_event(DemoEvent("assistant_end", 'CALL read_file {"id":"c1"}', round_index=1))
        call_widget = app.query(".call").first(Static)
        assert "assistant" in call_widget.classes
        await app._handle_event(DemoEvent("assistant_start", round_index=1))
        await app._handle_event(
            DemoEvent("assistant_delta", "FINAL: done\n\nassistant\nCALL bad {}", round_index=1)
        )
        await app._handle_event(DemoEvent("assistant_end", "FINAL: done", round_index=1))
        final_widget = app.query(".final").first(Static)
        assert "assistant" not in final_widget.classes
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
