from __future__ import annotations

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static, TextArea

from agent_runtime.chatml import render_message

from .client import VLLMCompletionClient
from .session import DemoConfig, DemoEvent, GlyphDemoSession


def compact_middle(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    keep = max(4, (limit - 1) // 2)
    return f"{text[:keep]}…{text[-keep:]}"


ROLE_HEADERS = {
    "system": ("● SYSTEM", "#a78bfa"),
    "user": ("● USER", "#facc15"),
    "assistant": ("✦ ASSISTANT / CALL", "#22d3ee"),
    "assistant_streaming": ("✦ ASSISTANT / STREAMING", "#38bdf8"),
    "assistant_final": ("◆ ASSISTANT / FINAL", "#fb7185"),
    "tool": ("■ TOOL RESULT", "#34d399"),
}


class PromptTextArea(TextArea):
    BINDINGS = [
        Binding("enter", "submit_prompt", "Submit", show=False, priority=True),
        Binding("shift+enter", "insert_newline", "Newline", show=False, priority=True),
        *TextArea.BINDINGS,
    ]

    async def action_submit_prompt(self) -> None:
        await self.app.action_submit_prompt()

    def action_insert_newline(self) -> None:
        self.insert("\n")


class GlyphDemoApp(App):
    TITLE = "GLYPH"
    SUB_TITLE = "remote vLLM · local Rust tools"
    CSS = """
    Screen { background: #03050a; color: #d7dee8; }
    #topbar { dock: top; height: 1; padding: 0 1; background: #050913; color: #7dffbf; }
    #main { height: 1fr; padding: 0; }
    #transcript { width: 1fr; padding: 0 1 0 1; scrollbar-size: 1 1; background: #03050a; }
    .message { width: 100%; margin: 0; padding: 0 1; border: round #26313d; }
    .system { background: #080b13; color: #cbd5e1; border: round #665f9f; }
    .user { background: #0f0d08; color: #fff4bf; border: round #b8962e; }
    .assistant { background: #06111c; color: #d8f3ff; border: round #00c8ff; }
    .call { border: round #00d4ff; }
    .final { background: #17070d; color: #ffe0e7; border: round #ff3f6e; }
    .tool { background: #06130e; color: #d8ffe9; border: round #00f59b; }
    .error { background: #17070d; color: #ffb3c1; border: round #ff3f6e; }
    .status { dock: bottom; color: #8aa0b8; padding: 0 1; height: 1; background: #050913; }
    #composer { dock: bottom; height: 4; padding: 0 1 1 1; background: #03050a; }
    #prompt { height: 3; max-height: 6; border: round #00f59b; background: #07101a; color: #e6fff4; }
    """
    BINDINGS = [
        ("enter", "submit_prompt", "Submit"),
        ("shift+enter", "insert_newline", "Newline"),
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+l", "clear", "Clear"),
        ("ctrl+r", "focus_prompt", "Prompt"),
    ]

    def __init__(self, client: VLLMCompletionClient, config: DemoConfig, endpoint: str, model: str) -> None:
        super().__init__()
        self.client = client
        self.config = config
        self.endpoint = endpoint
        self.model = model
        self._assistant_widget: Static | None = None
        self._assistant_text = ""

    def compose(self) -> ComposeResult:
        yield Static(self._topbar_text(), id="topbar", markup=False)
        with Vertical(id="main"):
            yield VerticalScroll(id="transcript")
        with Vertical(id="composer"):
            yield PromptTextArea(
                "",
                placeholder="Ask GLYPH to fix the Rust eval crate...",
                id="prompt",
                show_line_numbers=False,
                soft_wrap=True,
                compact=True,
            )
        yield Static("⏎ submit · ⇧⏎ newline · ^L clear · ^R prompt · ^Q quit", id="status", classes="status")

    def _topbar_text(self) -> str:
        crate = compact_middle(self.config.project.name or str(self.config.project), 36)
        endpoint = compact_middle(self.endpoint.removeprefix("http://").removeprefix("https://"), 32)
        return (
            f"✦ GLYPH │ model {self.model} │ vLLM {endpoint} │ "
            f"crate {crate} │ exec {self.config.sandbox_backend}"
        )

    @staticmethod
    def _trace_block(role: str, text: str, *, final: bool = False, streaming: bool = False) -> Text:
        header_key = role
        if role == "assistant" and streaming:
            header_key = "assistant_streaming"
        elif role == "assistant" and final:
            header_key = "assistant_final"
        label, color = ROLE_HEADERS[header_key]
        block = Text()
        block.append(label, style=f"bold {color}")
        block.append("  ")
        block.append("raw ChatML trace", style="#637083")
        block.append("\n")
        trace = f"<|im_start|>{role}\n{text}" if streaming else render_message(role, text)
        block.append(trace, style="#d7dee8")
        return block

    def on_mount(self) -> None:
        self.query_one("#prompt", TextArea).focus()

    async def on_unmount(self) -> None:
        await self.client.close()

    async def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "prompt":
            self._resize_prompt()

    async def action_submit_prompt(self) -> None:
        prompt_input = self.query_one("#prompt", TextArea)
        prompt = prompt_input.text.strip()
        if not prompt:
            return
        prompt_input.clear()
        self._resize_prompt()
        prompt_input.disabled = True
        self.run_agent(prompt)

    def _resize_prompt(self) -> None:
        prompt_input = self.query_one("#prompt", TextArea)
        width = max(24, prompt_input.size.width - 4)
        visual_lines = 1
        for line in prompt_input.text.splitlines() or [""]:
            visual_lines += max(0, (len(line) - 1) // width)
        prompt_height = max(3, min(6, visual_lines + 2))
        prompt_input.styles.height = prompt_height
        self.query_one("#composer", Vertical).styles.height = prompt_height + 1

    @work(exclusive=True)
    async def run_agent(self, prompt: str) -> None:
        session = GlyphDemoSession(self.client, self.config)
        try:
            async for event in session.run(prompt):
                await self._handle_event(event)
        finally:
            if session.messages:
                path = session.save_transcript()
                self.query_one("#status", Static).update(f"saved · {path}")
            prompt_input = self.query_one("#prompt", TextArea)
            prompt_input.disabled = False
            prompt_input.focus()

    async def _handle_event(self, event: DemoEvent) -> None:
        transcript = self.query_one("#transcript", VerticalScroll)
        status = self.query_one("#status", Static)
        if event.kind == "workspace":
            status.update(f"sandbox · {event.text}")
        elif event.kind == "system":
            await transcript.mount(
                Static(self._trace_block("system", event.text), classes="message system", markup=False)
            )
        elif event.kind == "user":
            await transcript.mount(
                Static(self._trace_block("user", event.text), classes="message user", markup=False)
            )
        elif event.kind == "assistant_start":
            self._assistant_text = ""
            self._assistant_widget = Static(
                self._trace_block("assistant", "", streaming=True),
                classes="message assistant",
                markup=False,
            )
            await transcript.mount(self._assistant_widget)
            status.update(f"model round {event.round_index} · streaming")
        elif event.kind == "assistant_delta" and self._assistant_widget is not None:
            self._assistant_text += event.text
            self._assistant_widget.update(self._trace_block("assistant", self._assistant_text, streaming=True))
        elif event.kind == "assistant_end" and self._assistant_widget is not None:
            self._assistant_text = event.text
            if event.text.lstrip().startswith("FINAL:"):
                self._assistant_widget.remove_class("assistant")
                self._assistant_widget.remove_class("call")
                self._assistant_widget.add_class("final")
            else:
                self._assistant_widget.add_class("call")
            self._assistant_widget.update(
                self._trace_block("assistant", event.text, final=event.text.lstrip().startswith("FINAL:"))
            )
        elif event.kind == "tool_start":
            status.update(f"tool · {event.text}")
        elif event.kind == "tool_result":
            await transcript.mount(Static(self._trace_block("tool", event.text), classes="message tool", markup=False))
        elif event.kind == "complete":
            status.update("complete · FINAL received")
        elif event.kind == "error":
            await transcript.mount(Static(event.text, classes="message error", markup=False))
            status.update("stopped · inspect the error above")
        transcript.scroll_end(animate=False)

    async def action_clear(self) -> None:
        await self.query_one("#transcript", VerticalScroll).remove_children()
        self.query_one("#status", Static).update("Transcript cleared. Enter a task to start again.")

    def action_focus_prompt(self) -> None:
        self.query_one("#prompt", TextArea).focus()
