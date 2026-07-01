"""Parse and validate the CALL / RESULT / FINAL protocol.

This module is deliberately narrower than the RL reward. It answers questions
like:
- Which assistant text belongs to assistant turns?
- Which CALL lines are syntactically valid?
- Which RESULT ids have appeared?
- Is there exactly one FINAL and no later CALL?

RL uses these checks as protocol/format gates, then adds task-specific reward
logic in rl/task_trace.py for cargo success, recovery attempts, post-success
tool churn, and heldout-style clean stopping.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Shared protocol patterns
# ---------------------------------------------------------------------------

# Full ChatML segment parser, used for stored rendered traces.
SEG_RE = re.compile(r"<\|im_start\|>(\w+)\n(.*?)<\|im_end\|>", re.DOTALL)

# Model-emitted tool request lines use a readable header plus JSON args:
# CALL tool_name {"id":"c1","key":"value"}
TOOL_NAME_RE = re.compile(r"^[A-Za-z_]\w*$")

# One runtime-emitted tool result block:
# RESULT c1:
RESULT_ID_RE = re.compile(r"^\s*RESULT\s+([A-Za-z0-9_\-]+):", re.MULTILINE)

# A final answer can contain arbitrary answer text after FINAL:.
FINAL_RE = re.compile(r"^\s*FINAL:\s*", re.MULTILINE)

ASSISTANT_STOP = "<|im_end|>"

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]


@dataclass
class ProtocolCall:
    tool: str
    id: str
    params: dict[str, str]


# ---------------------------------------------------------------------------
# ChatML role extraction
# ---------------------------------------------------------------------------
# Validation judges model assistant output separately from tool results.
# Otherwise RESULT text could be mistaken for something the model generated.

def _joined_role_text(text: str, role: str) -> str:
    """Return one role's body text from a full ChatML transcript.

    Example: assistant_text("<|im_start|>assistant\nFINAL: ok<|im_end|>")
    returns "FINAL: ok".

    Example: tool_text("<|im_start|>tool\nRESULT c1:\nok<|im_end|>")
    returns "RESULT c1:\nok".

    If there are no ChatML markers, the input is already plain generated
    text. In that case assistant_text("FINAL: ok") returns "FINAL: ok", while
    tool_text("FINAL: ok") returns "".
    """
    if "<|im_start|>" not in text:
        return text if role == "assistant" else ""
    return "\n".join(body for seg_role, body in SEG_RE.findall(text) if seg_role == role)


def assistant_text(text: str) -> str:
    return _joined_role_text(text, "assistant")


def tool_text(text: str) -> str:
    return _joined_role_text(text, "tool")


def strip_generated_assistant_stop(text: str) -> str:
    """Remove one terminal assistant stop token from raw model output.

    The prompt ends with "<|im_start|>assistant\n", so the model may finish a
    CALL or FINAL turn by emitting "<|im_end|>". That final stop token is a
    boundary, not assistant content.
    """
    stripped = text.rstrip()
    if stripped.endswith(ASSISTANT_STOP):
        return stripped[: -len(ASSISTANT_STOP)].rstrip()
    return stripped


# ---------------------------------------------------------------------------
# CALL parsing
# ---------------------------------------------------------------------------

def parse_call_line(line: str) -> tuple[ProtocolCall | None, list[str]]:
    """Parse one CALL line.

    Returns (None, []) for non-CALL lines, (None, errors) for malformed CALLs,
    and (ProtocolCall, []) for valid CALLs.
    """
    stripped = line.strip()
    if not stripped.startswith("CALL "):
        return None, []
    if "`" in stripped or stripped.endswith(";"):
        return None, ["Malformed CALL line terminator"]
    try:
        _, rest = stripped.split(None, 1)
        tool_name, payload = rest.split(None, 1)
    except ValueError:
        return None, ["Malformed CALL line"]
    if not TOOL_NAME_RE.fullmatch(tool_name):
        return None, ["Malformed CALL tool name"]
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as exc:
        return None, [f"Malformed CALL JSON: {exc.msg} at column {exc.colno}"]
    if not isinstance(decoded, dict):
        return None, ["CALL JSON payload must be an object"]
    params = dict(decoded)
    call_id = params.pop("id", None)
    if call_id is None or call_id == "":
        return None, ["Missing CALL id"]
    if not isinstance(call_id, str):
        return None, ["CALL id must be a string"]
    for key, value in params.items():
        if not isinstance(value, str):
            return None, [f"CALL argument must be a string: {key}"]
    return ProtocolCall(tool=tool_name, id=call_id, params=params), []


def call_syntax_errors(text: str) -> list[str]:
    """Return line-numbered syntax errors for every malformed CALL line."""
    errors: list[str] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if not line.strip().startswith("CALL "):
            continue
        _, line_errors = parse_call_line(line)
        errors.extend(f"line {line_no}: {err}" for err in line_errors)
    return errors


def parse_calls(text: str) -> list[ProtocolCall]:
    """Return every valid CALL in assistant text, ignoring malformed CALLs."""
    calls: list[ProtocolCall] = []
    for line in text.splitlines():
        call, errors = parse_call_line(line)
        if call is not None and not errors:
            calls.append(call)
    return calls


# ---------------------------------------------------------------------------
# RESULT parsing
# ---------------------------------------------------------------------------

def extract_result_ids(text: str) -> list[str]:
    """Return ids from RESULT blocks in tool text."""
    return RESULT_ID_RE.findall(text)


def extract_pending_call_ids(assistant_text: str, result_text: str = "") -> list[str]:
    """Return CALL ids that do not yet have matching RESULT ids."""
    call_ids = [call.id for call in parse_calls(assistant_text)]
    result_ids = set(extract_result_ids(result_text))
    return [call_id for call_id in call_ids if call_id not in result_ids]


# ---------------------------------------------------------------------------
# FINAL checks
# ---------------------------------------------------------------------------

def has_final(assistant_text: str) -> bool:
    return bool(FINAL_RE.search(assistant_text))


def final_count(assistant_text: str) -> int:
    return len(FINAL_RE.findall(assistant_text))


def ended_cleanly_after_final(assistant_text: str) -> bool:
    """Return true if the last FINAL is not followed by another CALL."""
    if not has_final(assistant_text):
        return False
    stripped = assistant_text.strip()
    last_final = stripped.rfind("FINAL:")
    if last_final < 0:
        return False
    tail = stripped[last_final:]
    return "CALL " not in tail[6:]


# ---------------------------------------------------------------------------
# Coarse structural validator
# ---------------------------------------------------------------------------

class SimpleTraceValidator:
    """Protocol-only validator used by RL as a structure gate.

    This is not the complete RL reward shape. It checks generic transcript
    validity: final presence, CALL/RESULT pairing, syntax, and role leaks.
    rl/task_trace.py adds outcome rewards and penalties that depend on executed
    cargo_test/cargo_run results.
    """

    def validate(self, assistant_text: str, result_text: str = "") -> ValidationResult:
        errors: list[str] = []
        calls = parse_calls(assistant_text)
        call_ids = [call.id for call in calls]
        result_ids = extract_result_ids(result_text)

        if not has_final(assistant_text):
            errors.append("Missing response")
        if final_count(assistant_text) > 1:
            errors.append("Multiple final responses")
        if has_final(assistant_text) and not ended_cleanly_after_final(assistant_text):
            errors.append("Garbage after final response")
        if result_ids != call_ids[: len(result_ids)] or len(result_ids) < len(call_ids):
            errors.append("Tool calls without matching result")
        errors.extend(call_syntax_errors(assistant_text))
        return ValidationResult(valid=not errors, errors=errors)
