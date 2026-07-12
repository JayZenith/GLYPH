from __future__ import annotations

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static, TextArea

from agent_runtime.chatml import render_message

from .client import VLLMCompletionClient
from .session import DemoConfig, DemoEvent, GlyphDemoSession


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
    Screen { background: #05080d; color: #e6fff0; }
    #topbar { dock: top; height: 1; padding: 0 1; background: #080d13; color: #9ff0b8; }
    #main { height: 1fr; }
    #transcript { width: 1fr; padding: 0 0; }
    .message { width: 100%; margin: 0 0 0 0; padding: 0 1; }
    .system { background: #0b0e12; border-left: thick #9aa4b2; }
    .user { background: #131207; border-left: thick #ffe94a; }
    .assistant { background: #07101a; border-left: thick #45a3ff; }
    .final { background: #19070a; color: #ffd7dc; border-left: thick #ff4a5e; }
    .tool { background: #07120b; border-left: thick #39ff88; }
    .error { background: #19070a; color: #ff8a96; border-left: thick #ff4a5e; }
    .status { dock: bottom; color: #759883; padding: 0 1; height: 1; background: #070b10; }
    #composer { dock: bottom; height: 4; padding: 0 0 1 0; }
    #prompt { height: 3; max-height: 6; border: tall #39ff88; background: #090e14; }
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
                placeholder="Describe the Rust task for the agent...",
                id="prompt",
                show_line_numbers=False,
                soft_wrap=True,
                compact=True,
            )
        yield Static("enter submit · shift+enter newline · ctrl+l clear · ctrl+r prompt · ctrl+q quit", id="status", classes="status")

    def _topbar_text(self) -> str:
        return (
            f"GLYPH  model={self.model}  endpoint={self.endpoint}  "
            f"crate={self.config.project}  exec={self.config.sandbox_backend}"
        )

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
                Static(render_message("system", event.text), classes="message system", markup=False)
            )
        elif event.kind == "user":
            await transcript.mount(
                Static(render_message("user", event.text), classes="message user", markup=False)
            )
        elif event.kind == "assistant_start":
            self._assistant_text = ""
            self._assistant_widget = Static(
                "<|im_start|>assistant\n",
                classes="message assistant",
                markup=False,
            )
            await transcript.mount(self._assistant_widget)
            status.update(f"model round {event.round_index} · streaming")
        elif event.kind == "assistant_delta" and self._assistant_widget is not None:
            self._assistant_text += event.text
            self._assistant_widget.update(f"<|im_start|>assistant\n{self._assistant_text}")
        elif event.kind == "assistant_end" and self._assistant_widget is not None:
            self._assistant_text = event.text
            if event.text.lstrip().startswith("FINAL:"):
                self._assistant_widget.remove_class("assistant")
                self._assistant_widget.add_class("final")
            self._assistant_widget.update(render_message("assistant", event.text))
        elif event.kind == "tool_start":
            status.update(f"tool · {event.text}")
        elif event.kind == "tool_result":
            await transcript.mount(Static(render_message("tool", event.text), classes="message tool", markup=False))
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
