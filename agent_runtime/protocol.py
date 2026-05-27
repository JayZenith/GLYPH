from __future__ import annotations

import re
from dataclasses import dataclass


SEG_RE = re.compile(r"<\|im_start\|>(\w+)\n(.*?)<\|im_end\|>", re.DOTALL)
CALL_BLOCK_RE = re.compile(r"^\s*CALL\s+([A-Za-z_]\w*)\((.*?)\)\s*$", re.MULTILINE | re.DOTALL)
CALL_ID_RE = re.compile(r'\bid\s*=\s*"([^"]+)"')
ARG_RE = re.compile(r'(\w+)\s*=\s*"((?:[^"\\]|\\.)*)"')
RESULT_ID_RE = re.compile(r"^\s*RESULT\s+([A-Za-z0-9_\-]+):", re.MULTILINE)
FINAL_RE = re.compile(r"^\s*FINAL:\s*", re.MULTILINE)
ROLE_LEAK_RE = re.compile(r"(<\|im_start\|>|<\|im_end\|>|^\s*(system|user|assistant|tool)\s*$)", re.MULTILINE)
REPETITION_RE = re.compile(r"(.{20,200}?)\1{4,}", re.DOTALL)


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]


@dataclass
class ProtocolCall:
    tool: str
    id: str
    params: dict[str, str]


def _joined_role_text(text: str, role: str) -> str:
    if "<|im_start|>" not in text:
        return text if role == "assistant" else ""
    return "\n".join(body for seg_role, body in SEG_RE.findall(text) if seg_role == role)


def assistant_text(text: str) -> str:
    return _joined_role_text(text, "assistant")


def tool_text(text: str) -> str:
    return _joined_role_text(text, "tool")


def parse_calls(text: str) -> list[ProtocolCall]:
    calls: list[ProtocolCall] = []
    for tool_name, arg_blob in CALL_BLOCK_RE.findall(text):
        match = CALL_ID_RE.search(arg_blob)
        if not match:
            continue
        params = {
            key: bytes(value, "utf-8").decode("unicode_escape")
            for key, value in ARG_RE.findall(arg_blob)
            if key != "id"
        }
        calls.append(ProtocolCall(tool=tool_name, id=match.group(1), params=params))
    return calls


def extract_result_ids(text: str) -> list[str]:
    return RESULT_ID_RE.findall(text)


def extract_pending_call_ids(assistant_text: str, result_text: str = "") -> list[str]:
    call_ids = [call.id for call in parse_calls(assistant_text)]
    result_ids = set(extract_result_ids(result_text))
    return [call_id for call_id in call_ids if call_id not in result_ids]


def has_final(assistant_text: str) -> bool:
    return bool(FINAL_RE.search(assistant_text))


def final_count(assistant_text: str) -> int:
    return len(FINAL_RE.findall(assistant_text))


def ended_cleanly_after_final(assistant_text: str) -> bool:
    if not has_final(assistant_text):
        return False
    stripped = assistant_text.strip()
    last_final = stripped.rfind("FINAL:")
    if last_final < 0:
        return False
    tail = stripped[last_final:]
    return "CALL " not in tail[6:]


class SimpleTraceValidator:
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
        if REPETITION_RE.search(assistant_text):
            errors.append("Detected repetition")
        if ROLE_LEAK_RE.search(assistant_text):
            errors.append("Role marker leakage")
        if has_final(assistant_text):
            last_final = assistant_text.rfind("FINAL:")
            if last_final >= 0 and "CALL " in assistant_text[last_final + len("FINAL:"):]:
                errors.append("Garbage after final response")
        return ValidationResult(valid=not errors, errors=errors)
