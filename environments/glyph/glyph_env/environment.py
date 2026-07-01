from __future__ import annotations

from pathlib import Path

import verifiers as vf

from .agent_runtime.protocol import (
    ProtocolCall,
    call_syntax_errors,
    parse_calls,
    strip_generated_assistant_stop,
)
from .agent_runtime.rust.executor import ExecutionResult, RustExecutor
from .agent_runtime.rust.results import format_result_block
from .agent_runtime.rust.runtime import (
    SUPPORTED_RUST_TOOLS,
    ensure_sandbox_copy,
    execute_rust_tool,
    rewrite_params_for_sandbox,
)
from .agent_runtime.chatml import render_tool_turn
from .rollout_text import (
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

    def _latest_completion_text(self, state: dict) -> str:
        trajectory = state.get("trajectory") or []
        if not trajectory:
            return ""
        text = messages_text(trajectory[-1]["completion"])
        return strip_generated_assistant_stop(text)

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

    def _pending_calls(self, text: str, state: dict) -> tuple[list[ProtocolCall], set[str]]:
        executed = set(state.get("executed_call_ids") or [])
        calls = [call for call in parse_calls(text) if call.id not in executed]
        return calls, executed

    def _resolve_info(self, calls: list[ProtocolCall], kwargs: dict) -> dict:
        info = kwargs.get("info") or {}
        if not info.get("expected_tool"):
            info = self._infer_info_from_calls(calls)
        return info

    def _execute_call(
        self,
        call: ProtocolCall,
        params: dict,
        info: dict,
        is_rust_prompt: bool,
    ) -> ExecutionResult:
        if not is_rust_prompt:
            return ExecutionResult(False, "", "missing rust task metadata", -1)
        if call.tool not in SUPPORTED_RUST_TOOLS:
            return ExecutionResult(False, "", f"unknown tool: {call.tool}", -1)
        return execute_rust_tool(
            self.executor,
            call.tool,
            params,
            expected_output=info.get("expected_output") if call.tool == "cargo_run" else None,
        )

    def _record_result(
        self,
        state: dict,
        call: ProtocolCall,
        result: ExecutionResult,
    ) -> dict[str, str]:
        result_block = format_result_block(call.id, result)
        # executed_tool_calls preserves structured CALL objects for reward logic.
        state.setdefault("executed_tool_calls", []).append(call)
        # executed_results stores structured execution outcomes keyed by CALL id.
        state.setdefault("executed_results", {})[call.id] = result
        # executed_result_blocks stores rendered RESULT text for protocol scoring.
        state.setdefault("executed_result_blocks", []).append(result_block)
        return {
            "role": "tool",
            "tool_call_id": call.id,
            "content": result_block,
        }

    @vf.stop
    async def glyph_completed(self, state, **kwargs) -> bool:
        # Verifiers calls this after assistant turns to decide whether the
        # episode ends, while its built-in stop checks still run separately.
        trajectory = state.get("trajectory") or []
        if not trajectory:
            return False
        if state.get("tool_budget_exhausted"):
            return True
        text = self._latest_completion_text(state)
        errors = call_syntax_errors(text)
        if errors:
            state["malformed_call_errors"] = errors
            return True
        pending_calls, executed = self._pending_calls(text, state)
        if pending_calls and (
            state.get("rounds_used", 0) >= self.max_tool_rounds
            or len(executed) >= self.max_tool_rounds
        ):
            # tool_budget_exhausted means the model asked for an unexecuted CALL
            # after the configured call/round budget was already spent.
            state["tool_budget_exhausted"] = True
            return True
        return not pending_calls

    async def env_response(self, messages, state, **kwargs):
        # Verifiers calls this to turn model CALL lines into tool RESULT messages.
        prior_trace = messages_text(messages)
        raw_latest = latest_assistant_segment(prior_trace)
        text = strip_generated_assistant_stop(raw_latest)
        errors = call_syntax_errors(text)
        if errors:
            state["malformed_call_errors"] = errors
            return []
        calls, executed = self._pending_calls(text, state)
        if not calls:
            return []

        info = self._resolve_info(calls, kwargs)
        # resolved_info lets reward recover task metadata when Verifiers does not
        # pass info directly to the reward callback.
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
            # The rollout can still receive results for calls within budget, but
            # reward should know an extra CALL was left unexecuted.
            state["tool_budget_exhausted"] = True

        for call in calls[:remaining]:
            params = call.params
            if trace_prefix and sandbox_path:
                params = rewrite_params_for_sandbox(params, trace_prefix, sandbox_path)
            er = self._execute_call(call, params, info, is_rust_prompt)
            executed.add(call.id)
            response = self._record_result(state, call, er)
            tool_turn = render_tool_turn(response["content"])
            # raw_chatml_transcript is the cumulative rendered conversation used
            # for reward ordering checks.
            prior_trace += tool_turn
            responses.append(response)

        # rounds_used tracks how many assistant CALL turns produced tool work.
        state["rounds_used"] = state.get("rounds_used", 0) + 1
        # executed_call_ids is the duplicate-call guard for future turns.
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
