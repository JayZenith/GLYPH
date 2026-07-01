from __future__ import annotations

from ..protocol import parse_calls
from .executor import ExecutionResult


def parse_call_blocks(text: str) -> list[dict]:
    return [
        {
            "tool": call.tool,
            "id": call.id,
            "params": call.params,
        }
        for call in parse_calls(text)
    ]


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = max_chars // 2 - 20
    tail = max_chars - head - 20
    return f"{text[:head]}\n...[truncated]...\n{text[-tail:]}"


def format_result_block(call_id: str, result: ExecutionResult, max_chars: int = 8000) -> str:
    status = "success" if result.success else "failed"
    lines = [f"status: {status}"]
    if result.timed_out:
        lines.append("timed_out: true")
    if result.stdout:
        lines.append(f"stdout:\n{result.stdout.strip()}")
    if result.stderr and not result.success:
        lines.append(f"stderr:\n{result.stderr.strip()}")
    body = _truncate("\n".join(lines).strip(), max_chars)
    return f"RESULT {call_id}:\n{body}"

