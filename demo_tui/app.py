from __future__ import annotations

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


ROLE_LABELS = {
    "system": "system",
    "user": "user",
    "assistant": "assistant",
    "tool": "tool",
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
    Screen { background: #0b0f14; color: #d7dee8; }
    #topbar { dock: top; height: 1; padding: 0 1; background: #11161d; color: #aab6c4; }
    #main { height: 1fr; padding: 0; }
    #transcript { width: 1fr; padding: 0 1 0 1; scrollbar-size: 1 1; }
    .message { width: 100%; margin: 0; padding: 0 1; border: solid #26313d; }
    .system { background: #0f141b; color: #b8c2cc; border: solid #56616f; }
    .user { background: #13130f; color: #eadca6; border: solid #a8944a; }
    .assistant { background: #0d1520; color: #d6e4f0; border: solid #4f83b8; }
    .call { border: solid #5a8fc7; }
    .final { background: #1b1013; color: #f1d2d7; border: solid #c85a68; }
    .tool { background: #0d1712; color: #d3eadc; border: solid #57996f; }
    .error { background: #1b1013; color: #e7a5ad; border: solid #c85a68; }
    .status { dock: bottom; color: #8290a0; padding: 0 1; height: 1; background: #11161d; }
    #composer { dock: bottom; height: 4; padding: 0 1 1 1; background: #0b0f14; }
    #prompt { height: 3; max-height: 6; border: tall #5f748c; background: #101720; color: #d7dee8; }
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
        crate = compact_middle(self.config.project.name or str(self.config.project), 36)
        endpoint = compact_middle(self.endpoint.removeprefix("http://").removeprefix("https://"), 32)
        return (
            f"GLYPH · {self.model} · {endpoint} · "
            f"crate={crate} · exec={self.config.sandbox_backend}"
        )

    @staticmethod
    def _trace_block(role: str, text: str, *, final: bool = False) -> str:
        label = "assistant · FINAL" if final else ROLE_LABELS[role]
        return f"{label}\n{render_message(role, text)}"

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
                "assistant · streaming\n<|im_start|>assistant\n",
                classes="message assistant",
                markup=False,
            )
            await transcript.mount(self._assistant_widget)
            status.update(f"model round {event.round_index} · streaming")
        elif event.kind == "assistant_delta" and self._assistant_widget is not None:
            self._assistant_text += event.text
            self._assistant_widget.update(f"assistant · streaming\n<|im_start|>assistant\n{self._assistant_text}")
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
