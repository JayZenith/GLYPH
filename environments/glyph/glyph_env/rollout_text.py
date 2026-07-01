from __future__ import annotations

from dataclasses import dataclass

from .agent_runtime.chatml import (
    message_content,
    message_role,
    render_messages,
)
from .agent_runtime.protocol import strip_generated_assistant_stop


# Verifiers stores rollout data across completion lists and cumulative
# trajectory steps. Reward code wants normalized strings: assistant text,
# latest assistant turn, tool RESULT text, and the full rendered transcript.
def completion_text(completion) -> str:
    if isinstance(completion, str):
        return completion
    if isinstance(completion, list):
        return "\n".join(message_content(m) for m in completion)
    return str(completion)


def completion_role_text(completion, role: str) -> str:
    if isinstance(completion, list):
        return "\n".join(
            strip_generated_assistant_stop(message_content(m)) if role == "assistant" else message_content(m)
            for m in completion
            if message_role(m) == role
        )
    return "" if role == "tool" else completion_text(completion)


def latest_assistant_segment(text: str) -> str:
    marker = "<|im_start|>assistant\n"
    if marker not in text:
        return text
    return text.rsplit(marker, 1)[-1]


def messages_text(messages) -> str:
    if isinstance(messages, str):
        return messages
    if isinstance(messages, list):
        return render_messages(messages).rstrip()
    return str(messages)


@dataclass(frozen=True)
class RolloutText:
    assistant: str
    latest_assistant: str
    tool: str
    full: str


def collect_rollout_text(state: dict) -> RolloutText:
    assistant_parts: list[str] = []
    tool_parts: list[str] = []
    latest_assistant = ""
    trajectory = state.get("trajectory") or []

    for step in trajectory:
        for field in ("prompt", "completion"):
            for message in step.get(field) or []:
                content = message_content(message)
                role = message_role(message)
                if role == "tool":
                    tool_parts.append(content)
                if field == "completion" and role == "assistant":
                    assistant = strip_generated_assistant_stop(content)
                    assistant_parts.append(assistant)
                    latest_assistant = assistant.strip()

    full = ""
    if trajectory:
        last = trajectory[-1]
        full = messages_text(
            [*(last.get("prompt") or []), *(last.get("completion") or [])]
        )
    if not full and state.get("raw_chatml_transcript"):
        full = str(state["raw_chatml_transcript"])
    return RolloutText(
        assistant="\n".join(assistant_parts),
        latest_assistant=latest_assistant,
        tool="\n".join(tool_parts),
        full=full,
    )
