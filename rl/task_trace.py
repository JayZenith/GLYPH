from __future__ import annotations

import re
from pathlib import Path

from datasets import Dataset

import verifiers as vf
from agent_runtime.protocol import SimpleTraceValidator, ended_cleanly_after_final, has_final
from rl.task_format import load_prompts
from agent_runtime.rust.executor import ExecutionResult, RustExecutor, create_executor
from agent_runtime.rust.runtime import ensure_sandbox_copy, execute_rust_tool, rewrite_params_for_sandbox
from agent_runtime.rust.results import (
    format_result_block,
    parse_call_blocks,
)
from agent_runtime.rust.reward import compute_tool_reward
from agent_runtime.rust.tools import RUST_TOOLS

# Tool names allowed by the Rust RL environment.
RUST_TOOL_NAMES = {
    getattr(tool, "name", None) if not isinstance(tool, dict) else tool.get("name")
    for tool in RUST_TOOLS
}
RUST_TOOL_NAMES.discard(None)

DEBUG_PARSE = False
DEFAULT_REWARD_CONFIG = {
    "clean_tool_boundary_bonus": 1.5,
    "structure_valid_bonus": 1.0,
    "penalty_garbage_after_final_response": -2.0,
    "penalty_missing_response": -1.0,
    "penalty_role_marker_leakage": -0.5,
    "penalty_repetition": -1.0,
    "penalty_tool_calls_without_matching_result": -0.75,
    "penalty_not_ended_cleanly_after_final": -2.0,
    "no_call_penalty": -1.25,
    "any_success_bonus": 0.5,
    "missing_results_penalty": -0.75,
    "response_presence_bonus": 0.1,
    "exact_final_termination_bonus": 0.5,
    "dirty_final_response_reward_cap": -5.0,
    "require_clean_termination_for_success_reward": True,
}

REWARD_CONFIG = DEFAULT_REWARD_CONFIG.copy()

STRUCTURE_PENALTY_KEYS = {
    "Garbage after final response": "penalty_garbage_after_final_response",
    "Missing response": "penalty_missing_response",
    "Role marker leakage": "penalty_role_marker_leakage",
    "Detected repetition": "penalty_repetition",
    "Tool calls without matching result": "penalty_tool_calls_without_matching_result",
}


def _set_reward_config(overrides: dict[str, float]) -> None:
    REWARD_CONFIG.clear()
    REWARD_CONFIG.update(DEFAULT_REWARD_CONFIG)
    REWARD_CONFIG.update({k: v for k, v in overrides.items() if v is not None})


def _ended_cleanly_after_response(text: str) -> bool:
    return ended_cleanly_after_final(text)


def _response_termination_reward(text: str) -> float:
    if not has_final(text):
        return 0.0
    if _ended_cleanly_after_response(text):
        return REWARD_CONFIG["exact_final_termination_bonus"]
    return REWARD_CONFIG["penalty_not_ended_cleanly_after_final"]


def _has_response(text: str) -> bool:
    return has_final(text)


def _apply_clean_termination_gate(
    reward: float,
    *,
    assistant_trace: str,
    any_success: bool,
    real_results_seen: int,
    clean_end: bool,
) -> float:
    if clean_end:
        if any_success:
            reward += REWARD_CONFIG["any_success_bonus"]
        if real_results_seen > 0:
            reward += REWARD_CONFIG["clean_tool_boundary_bonus"]
        else:
            reward += REWARD_CONFIG["missing_results_penalty"]
        reward += REWARD_CONFIG["response_presence_bonus"]
        return reward

    if real_results_seen == 0:
        reward += REWARD_CONFIG["missing_results_penalty"]

    if _has_response(assistant_trace) and REWARD_CONFIG["require_clean_termination_for_success_reward"]:
        reward = min(reward, REWARD_CONFIG["dirty_final_response_reward_cap"])

    return reward


def _structure_reward(assistant_text: str, result_text: str, validator: SimpleTraceValidator | None) -> float:
    if validator is None:
        return 0.0
    v = validator.validate(assistant_text, result_text)
    score = REWARD_CONFIG["structure_valid_bonus"] if v.valid else 0.0
    for err in v.errors:
        for prefix, penalty_key in STRUCTURE_PENALTY_KEYS.items():
            if err.startswith(prefix):
                score += REWARD_CONFIG[penalty_key]
                break
    score += _response_termination_reward(assistant_text)
    return score


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


def _score_tool_sequence(calls: list[dict], expected_tool_sequence: list[str]) -> float:
    if not expected_tool_sequence:
        return 0.0
    actual = [call["tool"] for call in calls]
    if actual == expected_tool_sequence:
        return 1.25
    score = 0.0
    for idx, expected_tool in enumerate(expected_tool_sequence):
        if idx >= len(actual):
            score -= 0.3
            continue
        if actual[idx] == expected_tool:
            score += 0.2
        else:
            score -= 0.35
    if len(actual) > len(expected_tool_sequence):
        score -= min(0.15 * (len(actual) - len(expected_tool_sequence)), 0.75)
    return score


def _completion_text(completion) -> str:
    if isinstance(completion, str):
        return completion
    if isinstance(completion, list):
        # chat-mode rollout: concatenate everything past the prompt
        return "\n".join(_message_content(m) for m in completion)
    return str(completion)


def _message_value(message, key: str, default=""):
    if isinstance(message, dict):
        return message.get(key, default)
    value = getattr(message, key, default)
    if value is default and hasattr(message, "model_dump"):
        value = message.model_dump().get(key, default)
    return default if value is None else value


def _message_role(message) -> str:
    return str(_message_value(message, "role", ""))


def _message_content(message) -> str:
    return str(_message_value(message, "content", ""))


def _completion_role_text(completion, role: str) -> str:
    if isinstance(completion, list):
        return "\n".join(
            _message_content(m)
            for m in completion
            if _message_role(m) == role
        )
    return "" if role == "tool" else _completion_text(completion)


def _trajectory_generated_text(state: dict) -> str:
    parts: list[str] = []
    for step in state.get("trajectory") or []:
        for message in step.get("completion") or []:
            if _message_role(message) == "assistant":
                parts.append(_message_content(message))
    return "\n".join(parts)


def _trajectory_tool_text(state: dict) -> str:
    parts: list[str] = []
    for step in state.get("trajectory") or []:
        for field in ("prompt", "completion"):
            for message in step.get(field) or []:
                if _message_role(message) == "tool":
                    parts.append(_message_content(message))
    return "\n".join(parts)


def _find_result_for(call_id: str, text: str) -> dict | None:
    """Locate the env-emitted result block for a given call id; pull status fields."""
    m = re.search(
        r"RESULT\s+" + re.escape(call_id) + r":\n(.*?)(?=\nRESULT\s+[A-Za-z0-9_\-]+:|\Z)",
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
    state = kwargs.get("state") or {}
    text = _completion_text(completion)
    assistant_text = _trajectory_generated_text(state) or _completion_role_text(
        completion, "assistant"
    )
    executed_calls = state.get("executed_tool_calls") or []
    tool_text = "\n".join(state.get("executed_result_blocks") or [])
    if not tool_text:
        tool_text = _trajectory_tool_text(state) or _completion_role_text(
            completion, "tool"
        )
    info = kwargs.get("info") or {}
    expected_tool = info.get("expected_tool")
    expected_args = _normalize_expected_args(info.get("expected_args"))
    expected_tool_sequence = list(info.get("expected_tool_sequence") or [])
    validator: SimpleTraceValidator | None = kwargs.get("validator")
    structure = _structure_reward(assistant_text or text, tool_text, validator)
    assistant_trace = assistant_text or text

    # Non-Rust prompt: structure enforcement only. Env still mocks tool results
    # if the model emits a call, but we don't score Rust execution.
    if not expected_tool:
        return structure

    calls = executed_calls or parse_call_blocks(assistant_text or text)
    if not calls:
        return REWARD_CONFIG["no_call_penalty"] + structure

    first_call = calls[0]
    reward = _score_tool_alignment(first_call, expected_tool, expected_args)
    reward += _score_tool_sequence(calls, expected_tool_sequence)

    # Sum compute_tool_reward across every executed call. Multi-step workflows
    # (apply_patch → cargo_test, apply_patch → cargo_run) are credited per call.
    expected_output = info.get("expected_output")
    any_success = False
    real_results_seen = 0
    for call in calls:
        res = _find_result_for(call["id"], tool_text)
        if res is None:
            continue
        real_results_seen += 1
        tr = compute_tool_reward(
            tool_name=call["tool"],
            execution_result=res,
            expected_output=expected_output if call["tool"] == "cargo_run" else None,
        )
        reward += tr.total
        if bool(res.get("success", False)):
            any_success = True

    reward = _apply_clean_termination_gate(
        reward,
        assistant_trace=assistant_trace,
        any_success=any_success,
        real_results_seen=real_results_seen,
        clean_end=_ended_cleanly_after_response(assistant_trace),
    )

    return reward + structure


# ---------------------------------------------------------------------------
# Multi-turn env: execute real tools between assistant turns
# ---------------------------------------------------------------------------

class RustToolEnv(vf.MultiTurnEnv):
    """Run the model in chat format; when it emits a `CALL ...` block, execute
    the tool for real and append a `RESULT cN:` block before the next round.
    Stops when no pending calls remain or `max_tool_rounds` is reached.

    NOTE: this subclasses `vf.MultiTurnEnv` and follows the current async
    verifiers API (`env_response(messages, state)` + `is_completed(state)`).
    """

    def __init__(
        self,
        *args,
        executor: RustExecutor,
        max_tool_rounds: int = 5,
        sandbox_root: Path | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.executor = executor
        self.max_tool_rounds = max_tool_rounds
        self.sandbox_root = Path(sandbox_root) if sandbox_root else Path("runs/rlvr1/sandboxes")

    def _ensure_sandbox(self, state: dict, blueprint_root: str) -> str:
        """Per-rollout copy of a blueprint project. Idempotent within a rollout."""
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

    @staticmethod
    def _messages_text(messages) -> str:
        if isinstance(messages, str):
            return messages
        if isinstance(messages, list):
            return "\n".join(_message_content(m) for m in messages)
        return str(messages)

    async def is_completed(self, state, **kwargs) -> bool:
        trajectory = state.get("trajectory") or []
        if not trajectory:
            return False
        if state.get("rounds_used", 0) >= self.max_tool_rounds:
            return True
        text = self._messages_text(trajectory[-1]["completion"])
        executed = set(state.get("executed_call_ids") or [])
        calls = parse_call_blocks(text)
        return not any(call["id"] not in executed for call in calls)

    async def env_response(self, messages, state, **kwargs):
        text = self._messages_text(messages)
        executed = set(state.get("executed_call_ids") or [])
        calls = [call for call in parse_call_blocks(text) if call["id"] not in executed]
        if not calls:
            return []

        info = kwargs.get("info") or {}
        is_rust_prompt = bool(info.get("expected_tool"))
        blueprint_root = info.get("blueprint_root")
        sandbox_path = self._ensure_sandbox(state, blueprint_root) if blueprint_root else None

        responses: list[dict[str, str]] = []
        for call in calls:
            cid = call["id"]
            params = call["params"]
            if blueprint_root and sandbox_path:
                params = rewrite_params_for_sandbox(params, blueprint_root, sandbox_path)
            if not is_rust_prompt:
                # Non-Rust prompt: mock the tool result so the assistant→tool
                # boundary structure stays intact for the structure reward.
                er = ExecutionResult(True, f"Mocked tool result for {cid}.", "", 0)
            elif call["tool"] not in RUST_TOOL_NAMES:
                er = ExecutionResult(False, "", f"unknown tool: {call['tool']}", -1)
            else:
                er = execute_rust_tool(
                    self.executor,
                    call["tool"],
                    params,
                    expected_output=info.get("expected_output") if call["tool"] == "cargo_run" else None,
                )
            executed.add(cid)
            result_block = format_result_block(cid, er)
            state.setdefault("executed_tool_calls", []).append(call)
            state.setdefault("executed_result_blocks", []).append(result_block)
            responses.append(
                {
                    "role": "tool",
                    "tool_call_id": cid,
                    "content": result_block,
                }
            )

        state["rounds_used"] = state.get("rounds_used", 0) + 1
        state["executed_call_ids"] = sorted(executed)
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
    max_tool_rounds: int = 5,
    clean_tool_boundary_bonus: float | None = None,
    structure_valid_bonus: float | None = None,
    penalty_garbage_after_final_response: float | None = None,
    penalty_missing_response: float | None = None,
    penalty_role_marker_leakage: float | None = None,
    penalty_repetition: float | None = None,
    penalty_tool_calls_without_matching_result: float | None = None,
    penalty_not_ended_cleanly_after_final: float | None = None,
    no_call_penalty: float | None = None,
    any_success_bonus: float | None = None,
    missing_results_penalty: float | None = None,
    response_presence_bonus: float | None = None,
    exact_final_termination_bonus: float | None = None,
    dirty_final_response_reward_cap: float | None = None,
    require_clean_termination_for_success_reward: bool | None = None,
) -> vf.Environment:
    """Load the Rust tool RL environment with real multi-round tool execution."""
    _set_reward_config(
        {
            "clean_tool_boundary_bonus": clean_tool_boundary_bonus,
            "structure_valid_bonus": structure_valid_bonus,
            "penalty_garbage_after_final_response": penalty_garbage_after_final_response,
            "penalty_missing_response": penalty_missing_response,
            "penalty_role_marker_leakage": penalty_role_marker_leakage,
            "penalty_repetition": penalty_repetition,
            "penalty_tool_calls_without_matching_result": penalty_tool_calls_without_matching_result,
            "penalty_not_ended_cleanly_after_final": penalty_not_ended_cleanly_after_final,
            "no_call_penalty": no_call_penalty,
            "any_success_bonus": any_success_bonus,
            "missing_results_penalty": missing_results_penalty,
            "response_presence_bonus": response_presence_bonus,
            "exact_final_termination_bonus": exact_final_termination_bonus,
            "dirty_final_response_reward_cap": dirty_final_response_reward_cap,
            "require_clean_termination_for_success_reward": require_clean_termination_for_success_reward,
        }
    )

    prompts, _ = load_prompts(
        data_path=data_path,
        max_samples=max_samples,
        max_trace_chars=max_trace_chars,
    )
    # Verifiers at our prime-rl pin forwards a dataset row's `info` dict into
    # env_response / reward kwargs but does NOT forward arbitrary top-level
    # columns. Pack expected_tool / expected_args / blueprint_root /
    # expected_output into `info` so the env can actually execute the verifier.
    info_keys = (
        "expected_tool",
        "expected_args",
        "expected_tool_sequence",
        "blueprint_root",
        "expected_output",
        "kind",
    )
    dataset = Dataset.from_list(
        [
            {
                "prompt": item["prompt"],
                "info": {k: item[k] for k in info_keys if k in item},
                "task": env_id,
            }
            for item in prompts
        ]
    )

    parser = vf.Parser()
    validator = SimpleTraceValidator()
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
