from __future__ import annotations

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Static, TextArea

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
    Header { background: #0a0f16; color: #39ff88; }
    #main { height: 1fr; }
    #transcript { width: 1fr; padding: 0 1; border: solid #20362a; }
    #sidebar { width: 34; padding: 1 2; background: #090e14; border: solid #20362a; }
    #sidebar-title { color: #39ff88; text-style: bold; margin-bottom: 1; }
    .sidebar-label { color: #759883; margin-top: 1; }
    .sidebar-value { color: #e6fff0; }
    .message { width: 100%; margin: 0 0 0 0; padding: 0 1; }
    .system { background: #101217; border: solid #9aa4b2; }
    .user { background: #15140b; border: solid #ffe94a; }
    .assistant { background: #08131f; border: solid #45a3ff; }
    .final { background: #21090d; color: #ffd7dc; border: solid #ff4a5e; }
    .tool { background: #08150e; border: solid #39ff88; }
    .error { background: #21090d; color: #ff8a96; border: solid #ff4a5e; }
    .status { color: #759883; padding: 0 1; height: 1; }
    #composer { dock: bottom; height: auto; margin-bottom: 1; }
    #prompt { height: 3; max-height: 8; border: tall #39ff88; background: #090e14; }
    Footer { background: #0a0f16; }
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
        yield Header()
        with Horizontal(id="main"):
            yield VerticalScroll(id="transcript")
            with Vertical(id="sidebar"):
                yield Static("LIVE SESSION", id="sidebar-title")
                yield Static("MODEL", classes="sidebar-label")
                yield Static(self.model, classes="sidebar-value")
                yield Static("ENDPOINT", classes="sidebar-label")
                yield Static(self.endpoint, classes="sidebar-value")
                yield Static("SOURCE CRATE", classes="sidebar-label")
                yield Static(str(self.config.project), classes="sidebar-value")
                yield Static("EXECUTION", classes="sidebar-label")
                yield Static(self.config.sandbox_backend, classes="sidebar-value")
        yield Static("Enter a task to start a fresh rollout.", id="status", classes="status")
        with Vertical(id="composer"):
            yield PromptTextArea(
                "",
                placeholder="Describe the Rust task for the agent...",
                id="prompt",
                show_line_numbers=False,
                soft_wrap=True,
                compact=True,
            )
        yield Footer()

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
        prompt_input.styles.height = max(3, min(8, visual_lines + 2))

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
