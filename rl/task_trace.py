from __future__ import annotations

import re
from pathlib import Path

from datasets import Dataset

import verifiers as vf
from core.validator import TaskValidator
from rl.task_format import load_prompts
from rl.rust.executor import ExecutionResult, RustExecutor, create_executor
from rl.rust.results import (
    extract_pending_call_ids,
    format_result_block,
    parse_call_blocks,
)
from rl.rust.reward import compute_tool_reward
from rl.rust.tools import RUST_TOOLS

# Tool names allowed by the Rust RL environment.
RUST_TOOL_NAMES = {
    getattr(tool, "name", None) if not isinstance(tool, dict) else tool.get("name")
    for tool in RUST_TOOLS
}
RUST_TOOL_NAMES.discard(None)

DEBUG_PARSE = False


# ---------------------------------------------------------------------------
# Real tool execution dispatch (moved off the reward path; lives in the env)
# ---------------------------------------------------------------------------

def _execute(executor: RustExecutor, tool_name: str, params: dict) -> ExecutionResult:
    if tool_name == "rustc":
        source_file = params.get("source_file")
        if not source_file:
            return ExecutionResult(False, "", "missing source_file", -1)
        return executor.compile_file(source_file, params.get("output"))
    if tool_name == "cargo_check":
        return executor.cargo_check(params.get("project_path", "."))
    if tool_name == "cargo_build":
        release = str(params.get("release", "false")).lower() == "true"
        return executor.cargo_build(params.get("project_path", "."), release)
    if tool_name == "cargo_test":
        return executor.cargo_test(params.get("project_path", "."), params.get("test_name"))
    if tool_name == "execute":
        binary_path = params.get("binary_path")
        if not binary_path:
            return ExecutionResult(False, "", "missing binary_path", -1)
        return executor.run_binary(binary_path)
    return ExecutionResult(False, "", f"unknown tool: {tool_name}", -1)


# ---------------------------------------------------------------------------
# Reward scoring (operates on full transcript; no execution side-effects here)
# ---------------------------------------------------------------------------

def _normalize_expected_args(expected_args) -> dict[str, str]:
    if not expected_args:
        return {}
    return {str(k): str(v) for k, v in expected_args.items()}


def _score_tool_alignment(
    tool_call: dict,
    expected_tool: str | None,
    expected_args: dict[str, str],
) -> float:
    score = 0.0
    actual_tool = tool_call["tool"]
    actual_args = {str(k): str(v) for k, v in tool_call["params"].items()}

    if expected_tool:
        score += 0.45 if actual_tool == expected_tool else -0.7

    matched_exact = matched_partial = missing = wrong = 0
    for key, expected_value in expected_args.items():
        actual_value = actual_args.get(key)
        if actual_value is None:
            missing += 1
            continue
        if actual_value == expected_value:
            matched_exact += 1
            continue
        expected_name = Path(expected_value).name
        actual_name = Path(actual_value).name
        if expected_name and actual_name and expected_name == actual_name:
            matched_partial += 1
        else:
            wrong += 1

    score += matched_exact * 0.2
    score += matched_partial * 0.08
    score -= missing * 0.12
    score -= wrong * 0.18

    extra_args = [key for key in actual_args if key not in expected_args]
    score -= min(len(extra_args) * 0.04, 0.12)

    if expected_args and matched_exact == len(expected_args):
        score += 0.15

    if tool_call.get("id"):
        score += 0.05

    return score


def _completion_text(completion) -> str:
    if isinstance(completion, str):
        return completion
    if isinstance(completion, list):
        # chat-mode rollout: concatenate everything past the prompt
        parts = []
        for m in completion:
            if isinstance(m, dict):
                parts.append(str(m.get("content", "")))
            else:
                parts.append(str(m))
        return "\n".join(parts)
    return str(completion)


def _find_result_for(call_id: str, text: str) -> dict | None:
    """Locate the env-emitted result block for a given call id; pull status fields."""
    m = re.search(
        r"result\s*\{[^}]*?data\s*↦\s*「(.*?)」\s*🏷\s*" + re.escape(call_id) + r"[^}]*\}",
        text,
        re.DOTALL,
    )
    if not m:
        return None
    body = m.group(1)
    status = re.search(r"status:\s*(\w+)", body)
    exit_code = re.search(r"exit_code:\s*(-?\d+)", body)
    timed_out = "timed_out: true" in body
    stdout_m = re.search(r"stdout:\n(.*?)(?:\nstderr:|\Z)", body, re.DOTALL)
    stderr_m = re.search(r"stderr:\n(.*)\Z", body, re.DOTALL)
    return {
        "success": (status.group(1) == "success") if status else False,
        "exit_code": int(exit_code.group(1)) if exit_code else -1,
        "timed_out": timed_out,
        "stdout": stdout_m.group(1) if stdout_m else "",
        "stderr": stderr_m.group(1) if stderr_m else "",
    }


async def _rust_tool_reward(completion, **kwargs) -> float:
    """Score the full multi-turn rollout from the transcript the env produced.

    RLVR shape: every executed tool call contributes its own verifiable reward
    (exit code, test outcome, etc. via `compute_tool_reward`). Alignment with
    `expected_tool`/`expected_args` is scored once against the first call (only
    the first call has an expected target). A light penalty discourages
    spamming additional tool calls beyond what the task needs.
    """
    text = _completion_text(completion)

    calls = parse_call_blocks(text)
    if not calls:
        return -1.25

    expected_tool = kwargs.get("expected_tool")
    expected_args = _normalize_expected_args(kwargs.get("expected_args"))

    reward = _score_tool_alignment(calls[0], expected_tool, expected_args)

    any_success = False
    for call in calls:
        result = _find_result_for(call["id"], text)
        if result is None:
            continue
        reward += compute_tool_reward(
            tool_name=call["tool"],
            execution_result=result,
        ).total
        any_success = any_success or result.get("success", False)

    # Light penalty for extra calls beyond the first — RLVR rewards correct
    # multi-step workflows (build → test → execute), so don't penalize too hard,
    # just discourage fishing.
    if len(calls) > 1:
        reward -= 0.05 * (len(calls) - 1)

    if "response「" in text:
        reward += 0.1

    validator: TaskValidator = kwargs.get("validator")
    if validator and any_success:
        struct_result = validator.validate(text)
        reward += 0.2 if struct_result.valid else 0.0

    return reward


# ---------------------------------------------------------------------------
# Multi-turn env: execute real tools between assistant turns
# ---------------------------------------------------------------------------

class RustToolEnv(vf.MultiTurnEnv):
    """Run the model in trace-format chat; when it emits an `act { call ↦ … }`
    block, execute the tool for real and append a `result {…}` block before the
    next round. Stops when no pending calls remain or `max_tool_rounds` reached.

    NOTE: this subclasses `vf.MultiTurnEnv` and follows the current async
    verifiers API (`env_response(messages, state)` + `is_completed(state)`).
    """

    def __init__(
        self,
        *args,
        executor: RustExecutor,
        max_tool_rounds: int = 4,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.executor = executor
        self.max_tool_rounds = max_tool_rounds

    @staticmethod
    def _messages_text(messages) -> str:
        if isinstance(messages, str):
            return messages
        if isinstance(messages, list):
            return "\n".join(
                str(m.get("content", "") if isinstance(m, dict) else m) for m in messages
            )
        return str(messages)

    async def is_completed(self, state, **kwargs) -> bool:
        trajectory = state.get("trajectory") or []
        if not trajectory:
            return False
        if state.get("rounds_used", 0) >= self.max_tool_rounds:
            return True
        text = self._messages_text(trajectory[-1]["completion"])
        return not extract_pending_call_ids(text)

    async def env_response(self, messages, state, **kwargs):
        text = self._messages_text(messages)
        pending = extract_pending_call_ids(text)
        if not pending:
            return []

        by_id = {c["id"]: c for c in parse_call_blocks(text)}
        responses: list[dict[str, str]] = []
        for cid in pending:
            call = by_id.get(cid)
            if call is None:
                er = ExecutionResult(False, "", f"unknown call id: {cid}", -1)
            elif call["tool"] not in RUST_TOOL_NAMES:
                er = ExecutionResult(False, "", f"unknown tool: {call['tool']}", -1)
            else:
                er = _execute(self.executor, call["tool"], call["params"])
            responses.append(
                {
                    "role": "tool",
                    "tool_call_id": cid,
                    "content": format_result_block(cid, er),
                }
            )

        state["rounds_used"] = state.get("rounds_used", 0) + 1
        return responses


# ---------------------------------------------------------------------------
# PRIME-RL environment entrypoint
# ---------------------------------------------------------------------------

def load_environment(
    data_path: str = "traces.processed.jsonl",
    max_samples: int | None = None,
    max_trace_chars: int | None = 50000,
    env_id: str = "task-trace",
    nsjail_path: str | None = None,
    timeout: int = 30,
    max_tool_rounds: int = 4,
) -> vf.Environment:
    """Load the Rust tool RL environment with real multi-round tool execution."""

    prompts, _ = load_prompts(
        data_path=data_path,
        max_samples=max_samples,
        max_trace_chars=max_trace_chars,
    )
    dataset = Dataset.from_list(
        [
            {
                **item,
                "task": env_id,
            }
            for item in prompts
        ]
    )

    parser = vf.Parser()
    validator = TaskValidator()
    executor = create_executor(nsjail_path=nsjail_path, timeout=timeout)
    rubric = vf.Rubric(parser=parser)
    rubric.class_objects["validator"] = validator
    rubric.add_reward_func(_rust_tool_reward, weight=1.0)

    env = RustToolEnv(
        dataset=dataset,
        parser=parser,
        rubric=rubric,
        message_type="completion",
        env_id=env_id,
        executor=executor,
        max_tool_rounds=max_tool_rounds,
    )
    return env
