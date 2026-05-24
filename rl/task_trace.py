from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from datasets import Dataset

import verifiers as vf
from core.validator import TaskValidator
from rl.task_format import load_prompts
from rl.rust.executor import ExecutionResult, RustExecutor, create_executor
from rl.rust.results import (
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
DEFAULT_REWARD_CONFIG = {
    "clean_tool_boundary_bonus": 1.5,
    "structure_valid_bonus": 1.0,
    "penalty_unbalanced_braces": -0.5,
    "penalty_unbalanced_brackets": -0.5,
    "penalty_unbalanced_special_quotes": -0.5,
    "penalty_garbage_after_final_response": -2.0,
    "penalty_final_response_unclosed": -0.75,
    "penalty_missing_response": -1.0,
    "penalty_undefined_tags": -0.4,
    "penalty_unsatisfied_todos": -1.0,
    "penalty_repetition": -1.0,
    "penalty_tool_calls_without_matching_result": -0.75,
    "penalty_not_ended_cleanly_after_response": -2.0,
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
    "Unbalanced braces": "penalty_unbalanced_braces",
    "Unbalanced brackets": "penalty_unbalanced_brackets",
    "Unbalanced special quotes": "penalty_unbalanced_special_quotes",
    "Garbage after final response": "penalty_garbage_after_final_response",
    "Final response block is unclosed": "penalty_final_response_unclosed",
    "Missing response": "penalty_missing_response",
    "References to undefined tags": "penalty_undefined_tags",
    "Unsatisfied todo items": "penalty_unsatisfied_todos",
    "Detected repetition": "penalty_repetition",
    "Tool calls without matching result": "penalty_tool_calls_without_matching_result",
}


def _set_reward_config(overrides: dict[str, float]) -> None:
    REWARD_CONFIG.clear()
    REWARD_CONFIG.update(DEFAULT_REWARD_CONFIG)
    REWARD_CONFIG.update({k: v for k, v in overrides.items() if v is not None})


def _ended_cleanly_after_response(text: str) -> bool:
    if "response「" not in text:
        return False
    return bool(re.search(r"response「.*?」\s*(?:<\|im_end\|>\s*)?$", text, re.DOTALL))


def _response_termination_reward(text: str) -> float:
    if "response「" not in text:
        return 0.0
    if _ended_cleanly_after_response(text):
        return REWARD_CONFIG["exact_final_termination_bonus"]
    return REWARD_CONFIG["penalty_not_ended_cleanly_after_response"]


def _has_response(text: str) -> bool:
    return "response「" in text


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


def _structure_reward(trace_text: str, validator) -> float:
    """Always-on reward term from TaskValidator. Targets the V2 eval failure modes:
    malformed tail / extra braces, reference hygiene, todo satisfaction."""
    if validator is None:
        return 0.0
    v = validator.validate(trace_text)
    score = REWARD_CONFIG["structure_valid_bonus"] if v.valid else 0.0
    for err in v.errors:
        for prefix, penalty_key in STRUCTURE_PENALTY_KEYS.items():
            if err.startswith(prefix):
                score += REWARD_CONFIG[penalty_key]
                break
    score += _response_termination_reward(trace_text)
    return score


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
    if tool_name == "cargo_run":
        return executor.cargo_run(params.get("project_path", "."))
    if tool_name == "read_file":
        file_path = params.get("file_path")
        if not file_path:
            return ExecutionResult(False, "", "missing file_path", -1)
        return executor.read_file(file_path)
    if tool_name == "apply_patch":
        file_path = params.get("file_path")
        find = params.get("find")
        replace = params.get("replace")
        if not file_path or find is None or replace is None:
            return ExecutionResult(False, "", "apply_patch needs file_path, find, replace", -1)
        return executor.apply_patch(file_path, find, replace)
    return ExecutionResult(False, "", f"unknown tool: {tool_name}", -1)


# Per-rollout sandboxing for code-edit cases. Each rollout gets its own copy
# of the blueprint project so concurrent rollouts cannot stomp on each other.

def _rewrite_path(value: str, blueprint: str, sandbox: str) -> str:
    if isinstance(value, str) and value.startswith(blueprint):
        return sandbox + value[len(blueprint):]
    return value


def _rewrite_params(params: dict, blueprint: str, sandbox: str) -> dict:
    return {k: _rewrite_path(v, blueprint, sandbox) if isinstance(v, str) else v
            for k, v in params.items()}


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
    validator: TaskValidator = kwargs.get("validator")
    structure = _structure_reward(text, validator)
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
        rollout_id = state.get("rollout_id") or uuid.uuid4().hex[:12]
        blueprint = Path(blueprint_root)
        sandbox = self.sandbox_root / rollout_id / blueprint.name
        sandbox.parent.mkdir(parents=True, exist_ok=True)
        if blueprint.is_dir():
            shutil.copytree(blueprint, sandbox, dirs_exist_ok=True)
        else:
            sandbox.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(blueprint, sandbox)
        state["rollout_id"] = rollout_id
        state["sandbox_path"] = str(sandbox)
        state["blueprint_root"] = str(blueprint)
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
                params = _rewrite_params(params, blueprint_root, sandbox_path)
            if not is_rust_prompt:
                # Non-Rust prompt: mock the tool result so the assistant→tool
                # boundary structure stays intact for the structure reward.
                er = ExecutionResult(True, f"Mocked tool result for {cid}.", "", 0)
            elif call["tool"] not in RUST_TOOL_NAMES:
                er = ExecutionResult(False, "", f"unknown tool: {call['tool']}", -1)
            else:
                er = _execute(self.executor, call["tool"], params)
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
    penalty_unbalanced_braces: float | None = None,
    penalty_unbalanced_brackets: float | None = None,
    penalty_unbalanced_special_quotes: float | None = None,
    penalty_garbage_after_final_response: float | None = None,
    penalty_final_response_unclosed: float | None = None,
    penalty_missing_response: float | None = None,
    penalty_undefined_tags: float | None = None,
    penalty_unsatisfied_todos: float | None = None,
    penalty_repetition: float | None = None,
    penalty_tool_calls_without_matching_result: float | None = None,
    penalty_not_ended_cleanly_after_response: float | None = None,
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
            "penalty_unbalanced_braces": penalty_unbalanced_braces,
            "penalty_unbalanced_brackets": penalty_unbalanced_brackets,
            "penalty_unbalanced_special_quotes": penalty_unbalanced_special_quotes,
            "penalty_garbage_after_final_response": penalty_garbage_after_final_response,
            "penalty_final_response_unclosed": penalty_final_response_unclosed,
            "penalty_missing_response": penalty_missing_response,
            "penalty_undefined_tags": penalty_undefined_tags,
            "penalty_unsatisfied_todos": penalty_unsatisfied_todos,
            "penalty_repetition": penalty_repetition,
            "penalty_tool_calls_without_matching_result": penalty_tool_calls_without_matching_result,
            "penalty_not_ended_cleanly_after_response": penalty_not_ended_cleanly_after_response,
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
    info_keys = ("expected_tool", "expected_args", "blueprint_root", "expected_output")
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
