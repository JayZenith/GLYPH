from __future__ import annotations

from pathlib import Path

import verifiers as vf

from agent_runtime.protocol import (
    ProtocolCall,
    call_syntax_errors,
    parse_calls,
    strip_generated_assistant_stop,
)
from agent_runtime.rust.executor import ExecutionResult, RustExecutor
from agent_runtime.rust.results import format_result_block
from agent_runtime.rust.runtime import (
    SUPPORTED_RUST_TOOLS,
    ensure_sandbox_copy,
    execute_rust_tool,
    rewrite_params_for_sandbox,
)
from agent_runtime.chatml import render_tool_turn
from rl.rollout_text import (
    latest_assistant_segment,
    messages_text,
)


class RustToolEnv(vf.MultiTurnEnv):
    """Run the model in chat format and execute Glyph tool calls."""

    def __init__(
        self,
        *args,
        executor: RustExecutor,
        max_tool_rounds: int = 5,
        sandbox_root: Path | None = None,
        trace_infos: dict[str, dict] | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.executor = executor
        self.max_tool_rounds = max_tool_rounds
        self.sandbox_root = Path(sandbox_root) if sandbox_root else Path("runs/rlvr1/sandboxes")
        self.trace_infos = trace_infos or {}

    def _ensure_sandbox(self, state: dict, blueprint_root: str) -> str:
        if state.get("sandbox_path"):
            return state["sandbox_path"]
        rollout_id, sandbox = ensure_sandbox_copy(
            blueprint_root=blueprint_root,
            sandbox_root=self.sandbox_root,
            run_id=state.get("rollout_id"),
        )
        state["rollout_id"] = rollout_id
        state["sandbox_path"] = sandbox
        state["blueprint_root"] = blueprint_root
        return state["sandbox_path"]

    async def is_completed(self, state, **kwargs) -> bool:
        trajectory = state.get("trajectory") or []
        if not trajectory:
            return False
        if state.get("rounds_used", 0) >= self.max_tool_rounds:
            state["tool_budget_exhausted"] = True
            return True
        if len(state.get("executed_call_ids") or []) >= self.max_tool_rounds:
            state["tool_budget_exhausted"] = True
            return True
        if state.get("tool_budget_exhausted"):
            return True
        text = strip_generated_assistant_stop(messages_text(trajectory[-1]["completion"]))
        errors = call_syntax_errors(text)
        if errors:
            state["malformed_call_errors"] = errors
            return True
        executed = set(state.get("executed_call_ids") or [])
        calls = parse_calls(text)
        return not any(call.id not in executed for call in calls)

    async def env_response(self, messages, state, **kwargs):
        prior_trace = messages_text(messages)
        raw_latest = latest_assistant_segment(prior_trace)
        text = strip_generated_assistant_stop(raw_latest)
        errors = call_syntax_errors(text)
        if errors:
            state["malformed_call_errors"] = errors
            return []
        executed = set(state.get("executed_call_ids") or [])
        calls = [call for call in parse_calls(text) if call.id not in executed]
        if not calls:
            return []

        info = kwargs.get("info") or {}
        if not info.get("expected_tool"):
            info = self._infer_info_from_calls(calls)
        state["resolved_info"] = info
        is_rust_prompt = bool(info.get("expected_tool"))
        blueprint_root = info.get("blueprint_root")
        trace_prefix = info.get("trace_prefix") or blueprint_root
        sandbox_path = self._ensure_sandbox(state, blueprint_root) if blueprint_root else None

        responses: list[dict[str, str]] = []
        remaining = max(self.max_tool_rounds - len(executed), 0)
        if remaining <= 0:
            state["tool_budget_exhausted"] = True
            return []
        if len(calls) > remaining:
            state["tool_budget_exhausted"] = True

        for call in calls[:remaining]:
            cid = call.id
            params = call.params
            if trace_prefix and sandbox_path:
                params = rewrite_params_for_sandbox(params, trace_prefix, sandbox_path)
            if not is_rust_prompt:
                er = ExecutionResult(False, "", "missing rust task metadata", -1)
            elif call.tool not in SUPPORTED_RUST_TOOLS:
                er = ExecutionResult(False, "", f"unknown tool: {call.tool}", -1)
            else:
                er = execute_rust_tool(
                    self.executor,
                    call.tool,
                    params,
                    expected_output=info.get("expected_output") if call.tool == "cargo_run" else None,
                )
            executed.add(cid)
            result_block = format_result_block(cid, er)
            tool_turn = render_tool_turn(result_block)
            state.setdefault("executed_tool_calls", []).append(call)
            state.setdefault("executed_results", {})[cid] = er
            state.setdefault("executed_result_blocks", []).append(result_block)
            prior_trace += tool_turn
            responses.append(
                {
                    "role": "tool",
                    "tool_call_id": cid,
                    "content": result_block,
                }
            )

        state["rounds_used"] = state.get("rounds_used", 0) + 1
        state["executed_call_ids"] = sorted(executed)
        state["raw_chatml_transcript"] = prior_trace
        return responses

    def _infer_info_from_calls(self, calls: list[ProtocolCall]) -> dict:
        for call in calls:
            for value in call.params.values():
                if not isinstance(value, str):
                    continue
                for trace_prefix, info in self.trace_infos.items():
                    if value == trace_prefix or value.startswith(trace_prefix + "/"):
                        return info
        return {}
