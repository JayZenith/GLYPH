"""Tool-result parsing and trace-format result-block formatting for RL rollouts.

Mirrors the eval-time logic in `sft/evals/generation.py` (pending-call detection)
but emits *real* result blocks shaped to match SFT training data:

    result {
        data ↦ 「<stdout/stderr summary>」 🏷 <call_id>
    }

98% of training-data `result {…}` blocks use this single-`data` form; richer
key-value shapes are domain-specific and would be OOD here.
"""
from __future__ import annotations

import re

from rl.rust.executor import ExecutionResult


# Same patterns as sft/evals/generation.py — duplicated here so the RL package
# has no dependency on the SFT eval module at training time.
_CALL_ID_PATTERN = re.compile(r"call\s*↦\s*\{[^}]*?id\s*↦\s*([\w\"\-]+)", re.DOTALL)
_RESULT_BLOCK_TAG = re.compile(r"result\s*\{[^}]*?\}\s*🏷\s*([\w\"\-]+)", re.DOTALL)
_RESULT_INNER_TAG = re.compile(r"data\s*↦\s*[^🏷]*🏷\s*([\w\"\-]+)", re.DOTALL)

# Lighter-weight tool-call shape used by the model in trace format:
#     act { call ↦ { tool ↦ rustc • id ↦ c1 • source_file ↦ "/tmp/x.rs" } }
# We grab the entire `call ↦ { ... }` payload for one call at a time.
_CALL_BLOCK = re.compile(r"call\s*↦\s*\{([^}]*)\}", re.DOTALL)


def extract_pending_call_ids(text: str) -> list[str]:
    """Call ids in `text` that don't yet have a matching result block."""
    call_ids = _CALL_ID_PATTERN.findall(text)
    result_ids = _RESULT_BLOCK_TAG.findall(text) + _RESULT_INNER_TAG.findall(text)
    seen = {r.strip('"') for r in result_ids}
    return [cid.strip('"') for cid in call_ids if cid.strip('"') not in seen]


def parse_call_blocks(text: str) -> list[dict]:
    """Extract every `call ↦ {...}` payload in order: [{tool, id, params}, ...].

    Params are the freeform `key ↦ value` pairs minus the reserved `tool`/`id`.
    Tolerant of quoted and unquoted values; mirrors the looser parser already
    in rl/task_trace.py:_parse_tool_call but returns one entry per call so the
    env can dispatch each independently.
    """
    reserved = {"tool", "id", "task", "name", "description", "params", "type", "enum", "required"}
    calls: list[dict] = []
    for m in _CALL_BLOCK.finditer(text):
        body = m.group(1)
        tool_m = re.search(r"tool\s*↦\s*([A-Za-z_][A-Za-z0-9_]*)", body)
        id_m = re.search(r"id\s*↦\s*([^\s•\n}]+)", body)
        if not tool_m or not id_m:
            continue
        params: dict[str, str] = {}
        for pm in re.finditer(r"(\w+)\s*↦\s*\"([^\"]*)\"", body):
            key = pm.group(1)
            if key not in reserved:
                params[key] = pm.group(2)
        for pm in re.finditer(r"(\w+)\s*↦\s*([^\s•\n}]+)", body):
            key = pm.group(1)
            if key in params or key in reserved:
                continue
            params[key] = pm.group(2)
        calls.append({
            "tool": tool_m.group(1),
            "id": id_m.group(1).strip('"'),
            "params": params,
        })
    return calls


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = max_chars // 2 - 20
    tail = max_chars - head - 20
    return f"{text[:head]}\n…[truncated]…\n{text[-tail:]}"


def format_result_block(call_id: str, result: ExecutionResult, max_chars: int = 500) -> str:
    """Render an ExecutionResult as a trace-format `result {…}` block.

    Single-`data` shape matches 98% of training-data result blocks. Status and
    exit code are baked into the natural-prose payload rather than as separate
    keys to stay inside that majority distribution.
    """
    status = "success" if result.success else "failure"
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    parts = [f"status: {status}", f"exit_code: {result.exit_code}"]
    if result.timed_out:
        parts.append("timed_out: true")
    if stdout:
        parts.append(f"stdout:\n{stdout}")
    if stderr:
        parts.append(f"stderr:\n{stderr}")
    body = _truncate("\n".join(parts), max_chars)
    return (
        "result {\n"
        f"    data ↦ 「{body}」 🏷 {call_id}\n"
        "}"
    )
