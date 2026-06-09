from __future__ import annotations

import re
from pathlib import Path

from datasets import Dataset

import verifiers as vf
from agent_runtime.protocol import (
    GIBBERISH_RE,
    REPETITION_RE,
    ROLE_LEAK_RE,
    SimpleTraceValidator,
    call_syntax_errors,
    ended_cleanly_after_final,
    final_count,
    final_hygiene_errors,
    strip_terminal_chatml_end,
)
from rl.task_format import load_prompts
from agent_runtime.rust.executor import ExecutionResult, RustExecutor, create_executor
from agent_runtime.rust.runtime import ensure_sandbox_copy, execute_rust_tool, rewrite_params_for_sandbox
from agent_runtime.rust.results import (
    format_result_block,
    parse_call_blocks,
)
from agent_runtime.rust.tools import RUST_TOOLS

# Tool names allowed by the Rust RL environment.
RUST_TOOL_NAMES = {
    getattr(tool, "name", None) if not isinstance(tool, dict) else tool.get("name")
    for tool in RUST_TOOLS
}
RUST_TOOL_NAMES.discard(None)

DEBUG_PARSE = False
# Eval-aligned reward for reliability lift. The only positive outcome is the
# heldout-style valid trace: cargo verifier pass, no later tools, exactly one
# clean FINAL after the passing result, and no protocol errors. Invalid cargo
# success is not rewarded; it only avoids some failure penalties.
DEFAULT_REWARD_CONFIG = {
    # format floor
    "structure_valid_bonus": 0.0,
    "no_call_penalty": -5.0,
    "malformed_call_penalty": -4.0,
    "role_marker_penalty": -10.0,
    "bad_cargo_project_path_penalty": -4.0,
    "gibberish_penalty": -5.0,
    "bad_final_hygiene_penalty": -2.0,
    # clean completion
    "final_once_bonus": 0.0,
    "missing_final_penalty": -3.0,
    # Only exact heldout-style success is positive.
    "verifier_success_bonus": 0.0,
    "verifier_success_clean_final_bonus": 10.0,
    # bounded anti-churn / anti-thrash shaping
    "tool_after_success_penalty": -6.0,
    "tool_budget_exhausted_penalty": -5.0,
    "failed_verifier_penalty": -1.0,
    "max_failed_verifier_penalty": -4.0,
}

REWARD_CONFIG = DEFAULT_REWARD_CONFIG.copy()
def _set_reward_config(overrides: dict[str, float]) -> None:
    REWARD_CONFIG.clear()
    REWARD_CONFIG.update(DEFAULT_REWARD_CONFIG)
    REWARD_CONFIG.update({k: v for k, v in overrides.items() if v is not None})


# gives bonus if validator passes
def _structure_reward(assistant_text: str, result_text: str, validator: SimpleTraceValidator | None) -> float:
    if validator is None:
        return 0.0
    v = validator.validate(assistant_text, result_text)
    return REWARD_CONFIG["structure_valid_bonus"] if v.valid else 0.0


# ---------------------------------------------------------------------------
# Reward scoring (operates on full transcript; no execution side-effects here)
# ---------------------------------------------------------------------------

# VITAL, walks backward through calls and finds last cargo_test or cargo_run; if that terminal
# verifier succeeded, rollout gets a major reward
def _terminal_verifier_success(
    calls: list[dict],
    tool_text: str,
) -> tuple[bool, bool]:
    """Return (success, saw_terminal_verifier) for cargo_test/cargo_run."""
    for call in reversed(calls):
        if call["tool"] not in {"cargo_test", "cargo_run"}:
            continue
        res = _find_result_for(call["id"], tool_text)
        if res is None:
            continue
        return bool(res.get("success", False)), True
    return False, False


# Ordered pass/fail for every executed cargo_test/cargo_run call, in call order.
# Lets the reward count failed attempts and detect recovery (fail -> ... -> pass).
def _verifier_outcomes(calls: list[dict], tool_text: str) -> list[bool]:
    outcomes: list[bool] = []
    for call in calls:
        if call["tool"] not in {"cargo_test", "cargo_run"}:
            continue
        res = _find_result_for(call["id"], tool_text)
        if res is None:
            continue
        outcomes.append(bool(res.get("success", False)))
    return outcomes


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
            strip_terminal_chatml_end(_message_content(m)) if role == "assistant" else _message_content(m)
            for m in completion
            if _message_role(m) == role
        )
    return "" if role == "tool" else _completion_text(completion)


def _format_chatml_message(role: str, content: str) -> str:
    return f"<|im_start|>{role}\n{content.rstrip()}\n<|im_end|>"


def _format_chatml_messages(messages) -> str:
    if isinstance(messages, str):
        return messages
    if isinstance(messages, list):
        return "\n".join(
            _format_chatml_message(_message_role(m), _message_content(m))
            for m in messages
            if _message_role(m)
        )
    return str(messages)


def _strip_role_leak_tail(text: str) -> str:
    """Use only the assistant segment before leaked chat-template boundaries."""
    markers = [
        match.start()
        for match in re.finditer(
            r"<\|im_start\|>|<\|im_end\|>|^(?:user|tool|assistant)\s*$",
            text,
            re.MULTILINE,
        )
    ]
    return text[: min(markers)].rstrip() if markers else text


def _normalize_assistant_for_reward(text: str) -> str:
    """Match eval scoring: only a terminal ChatML end marker is outside content."""
    return strip_terminal_chatml_end(text).strip()


def _role_marker_errors(text: str) -> list[str]:
    stripped = text.rstrip()
    if stripped.endswith("<|im_end|>"):
        before_end = stripped[: -len("<|im_end|>")].rstrip()
        last_final = before_end.rfind("FINAL:")
        last_call = before_end.rfind("CALL ")
        if last_final >= 0 and last_final > last_call:
            stripped = before_end
    if ROLE_LEAK_RE.search(stripped):
        return ["Generated chat role marker"]
    return []


def _latest_assistant_segment(text: str) -> str:
    marker = "<|im_start|>assistant\n"
    if marker not in text:
        return text
    return text.rsplit(marker, 1)[-1]


def _append_unseen_text(prior: str, text: str) -> str:
    if not text or text in prior:
        return prior
    max_overlap = min(len(prior), len(text))
    for size in range(max_overlap, 0, -1):
        if prior.endswith(text[:size]):
            return prior + text[size:]
    return prior + text


def _format_chatml_tool_turn(result_block: str) -> str:
    return (
        "\n\n"
        "<|im_start|>tool\n"
        f"{result_block}\n"
        "<|im_end|>\n\n"
        "<|im_start|>assistant\n"
    )


def _trajectory_generated_text(state: dict) -> str:
    parts: list[str] = []
    for step in state.get("trajectory") or []:
        for message in step.get("completion") or []:
            if _message_role(message) == "assistant":
                parts.append(strip_terminal_chatml_end(_message_content(message)))
    return "\n".join(parts)


def _trajectory_tool_text(state: dict) -> str:
    parts: list[str] = []
    for step in state.get("trajectory") or []:
        for field in ("prompt", "completion"):
            for message in step.get(field) or []:
                if _message_role(message) == "tool":
                    parts.append(_message_content(message))
    return "\n".join(parts)


def _trajectory_full_text(state: dict) -> str:
    if state.get("raw_chatml_transcript"):
        return str(state["raw_chatml_transcript"])
    parts: list[str] = []
    for step in state.get("trajectory") or []:
        for field in ("prompt", "completion"):
            for message in step.get(field) or []:
                parts.append(_message_content(message))
    return "\n".join(parts)


def _finalization_reward(assistant_text: str) -> float:
    """Exactly one FINAL -> small bonus; otherwise the missing-FINAL penalty.

    Independent of solving: finalizing always beats looping. Solving and
    solve-then-stop are scored separately in `_outcome_reward`.
    """
    if final_count(assistant_text) == 1:
        return REWARD_CONFIG["final_once_bonus"]
    return REWARD_CONFIG["missing_final_penalty"]


def _result_offset(call_id: str, full_text: str) -> int:
    return full_text.find(f"RESULT {call_id}:")


def _heldout_style_success(
    assistant_text: str,
    full_text: str,
    success_pos: int,
    later_tools: list[dict],
    protocol_errors: list[str] | None = None,
) -> bool:
    if protocol_errors:
        return False
    if success_pos < 0 or later_tools:
        return False
    if final_count(assistant_text) != 1:
        return False
    if not ended_cleanly_after_final(assistant_text):
        return False
    if ROLE_LEAK_RE.search(assistant_text):
        return False
    if final_hygiene_errors(assistant_text):
        return False
    final_pos = full_text.rfind("FINAL:")
    return final_pos > success_pos


def _cargo_project_path_errors(calls: list[dict]) -> list[str]:
    errors: list[str] = []
    for call in calls:
        if call["tool"] not in {"cargo_run", "cargo_test"}:
            continue
        project_path = str(call.get("params", {}).get("project_path", ""))
        if re.search(r"/src/(?:main|lib)\.rs$", project_path):
            errors.append(f"{call['id']}: cargo project_path points at source file")
    return errors


def _protocol_reward_penalty(assistant_text: str, calls: list[dict], state: dict) -> tuple[float, list[str]]:
    errors: list[str] = []
    errors.extend(_role_marker_errors(assistant_text))
    errors.extend(call_syntax_errors(assistant_text))
    errors.extend(_cargo_project_path_errors(calls))
    if state.get("malformed_call_errors"):
        errors.extend(str(e) for e in state["malformed_call_errors"])
    penalty = 0.0
    if any("CALL" in e or "argument" in e for e in errors):
        penalty += REWARD_CONFIG["malformed_call_penalty"]
    if any("role marker" in e for e in errors):
        penalty += REWARD_CONFIG["role_marker_penalty"]
    if any("project_path" in e for e in errors):
        penalty += REWARD_CONFIG["bad_cargo_project_path_penalty"]
    if GIBBERISH_RE.search(assistant_text) or "<|endoftext|>" in assistant_text or "\ufffd" in assistant_text:
        errors.append("Detected gibberish")
        penalty += REWARD_CONFIG["gibberish_penalty"]
    if REPETITION_RE.search(assistant_text):
        errors.append("Detected repetition")
        penalty += REWARD_CONFIG["gibberish_penalty"]
    final_errors = final_hygiene_errors(assistant_text)
    if final_errors:
        errors.extend(final_errors)
        penalty += REWARD_CONFIG["bad_final_hygiene_penalty"]
    return penalty, errors


def _outcome_reward(
    calls: list[dict],
    tool_text: str,
    assistant_text: str,
    full_text: str,
    protocol_errors: list[str] | None = None,
) -> float:
    """Primary signal: exact heldout-style success.

    Cargo success without the exact stop contract is not positive reward. This
    avoids training a policy that gets tools to execute in RL while still failing
    strict heldout eval.
    """
    success_idx: int | None = None
    success_pos = -1
    failed_before_success = 0
    for idx, call in enumerate(calls):
        if call["tool"] not in {"cargo_test", "cargo_run"}:
            continue
        result = _find_result_for(call["id"], tool_text)
        if result is None:
            continue
        if result.get("success"):
            success_idx = idx
            pos = _result_offset(call["id"], full_text)
            if pos >= 0:
                success_pos = pos
            break
        failed_before_success += 1

    fail_penalty = max(
        REWARD_CONFIG["max_failed_verifier_penalty"],
        failed_before_success * REWARD_CONFIG["failed_verifier_penalty"],
    )

    if success_idx is None:
        return fail_penalty

    reward = REWARD_CONFIG["verifier_success_bonus"] + fail_penalty
    later_tools = [
        call for call in calls[success_idx + 1 :]
        if _find_result_for(call["id"], tool_text) is not None
    ]
    if later_tools:
        reward += REWARD_CONFIG["tool_after_success_penalty"]

    if _heldout_style_success(assistant_text, full_text, success_pos, later_tools, protocol_errors):
        reward += REWARD_CONFIG["verifier_success_clean_final_bonus"]
    return reward


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


# core reward function: collect assistant text, collect tool results, parse calls,
# score first-tool alignment/formatting, then add simple finalization shaping.
async def _rust_tool_reward(completion, **kwargs) -> float:
    """Score the full multi-turn rollout from the transcript the env produced."""
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
    full_text = _append_unseen_text(_trajectory_full_text(state), text) or text
    info = kwargs.get("info") or {}
    expected_tool = info.get("expected_tool")
    validator: SimpleTraceValidator | None = kwargs.get("validator")
    raw_assistant_trace = assistant_text or text
    reward_assistant_trace = _normalize_assistant_for_reward(raw_assistant_trace)
    assistant_trace = _strip_role_leak_tail(raw_assistant_trace)
    structure = _structure_reward(assistant_trace, tool_text, validator)

    # Non-Rust prompt: structure enforcement only. Env still mocks tool results
    # if the model emits a call, but we don't score Rust execution.
    if not expected_tool:
        return structure

    # Only actual env-executed calls can earn tool/verifier reward. If state is
    # unavailable, fall back to pre-boundary text only so fake transcript tails
    # do not count.
    calls = executed_calls or parse_call_blocks(assistant_trace)
    if not calls:
        protocol_penalty, _ = _protocol_reward_penalty(reward_assistant_trace, [], state)
        return REWARD_CONFIG["no_call_penalty"] + protocol_penalty + structure

    reward = 0.0
    # Malformed call keyword (e.g. "CALLTYPE" instead of "CALL ") breaks the
    # parser so no tool executes. Penalize per occurrence (capped) to train the
    # exact `CALL <tool>(...)` form.
    malformed = len(re.findall(r"\bCALL[A-Z]", raw_assistant_trace))
    reward += min(malformed, 4) * REWARD_CONFIG["malformed_call_penalty"]
    protocol_penalty, protocol_errors = _protocol_reward_penalty(
        reward_assistant_trace,
        calls,
        state,
    )
    reward += protocol_penalty

    reward += _finalization_reward(reward_assistant_trace)
    reward += _outcome_reward(calls, tool_text, reward_assistant_trace, full_text, protocol_errors)
    if protocol_errors:
        reward = min(reward, 0.0)

    if state.get("tool_budget_exhausted"):
        reward += REWARD_CONFIG["tool_budget_exhausted_penalty"]

    return reward + structure


# ---------------------------------------------------------------------------
# Multi-turn env: execute real tools between assistant turns
# ---------------------------------------------------------------------------

# Watches model output for CALLs, rewrites paths into sandbox paths, executes tools, appends RESULT blocks, etc.
# until no pending calls or max rounds
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
        trace_infos: dict[str, dict] | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.executor = executor
        self.max_tool_rounds = max_tool_rounds
        self.sandbox_root = Path(sandbox_root) if sandbox_root else Path("runs/rlvr1/sandboxes")
        self.trace_infos = trace_infos or {}

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
        return _format_chatml_messages(messages)

    @staticmethod
    def _trajectory_chars(state: dict) -> int:
        total = 0
        for step in state.get("trajectory") or []:
            for field in ("prompt", "completion"):
                for message in step.get(field) or []:
                    total += len(_message_content(message))
        return total

    def _raw_trace_text(self, state: dict, messages=None) -> str:
        prior = state.get("raw_chatml_transcript", "")
        if messages is not None:
            prior = _append_unseen_text(prior, self._messages_text(messages))
        return prior

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
        text = _strip_role_leak_tail(
            _latest_assistant_segment(
                self._raw_trace_text(state, trajectory[-1]["completion"])
            )
        )
        latest_content = _completion_role_text(trajectory[-1]["completion"], "assistant")
        marker_errors = _role_marker_errors(latest_content)
        text = strip_terminal_chatml_end(text)
        if marker_errors:
            state["malformed_call_errors"] = marker_errors
            return True
        errors = call_syntax_errors(text)
        if errors:
            state["malformed_call_errors"] = errors
            return True
        executed = set(state.get("executed_call_ids") or [])
        calls = parse_call_blocks(text)
        return not any(call["id"] not in executed for call in calls)

    async def env_response(self, messages, state, **kwargs):
        prior_trace = state.get("raw_chatml_transcript", "")
        incoming_text = self._messages_text(messages)
        raw_text = self._raw_trace_text(state, messages)
        raw_latest = _latest_assistant_segment(raw_text)
        latest_content = _completion_role_text(messages, "assistant")
        marker_errors = _role_marker_errors(latest_content)
        text = strip_terminal_chatml_end(_strip_role_leak_tail(raw_latest))
        if marker_errors:
            state["malformed_call_errors"] = marker_errors
            return []
        errors = call_syntax_errors(text)
        if errors:
            state["malformed_call_errors"] = errors
            return []
        executed = set(state.get("executed_call_ids") or [])
        calls = [call for call in parse_call_blocks(text) if call["id"] not in executed]
        if not calls:
            return []

        info = kwargs.get("info") or {}
        if not info.get("expected_tool"):
            info = self._infer_info_from_calls(calls)
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
            cid = call["id"]
            params = call["params"]
            if trace_prefix and sandbox_path:
                params = rewrite_params_for_sandbox(params, trace_prefix, sandbox_path)
            if not is_rust_prompt:
                er = ExecutionResult(False, "", "missing rust task metadata", -1)
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
            tool_turn = _format_chatml_tool_turn(result_block)
            state.setdefault("executed_tool_calls", []).append(call)
            state.setdefault("executed_result_blocks", []).append(result_block)
            prior_trace = _append_unseen_text(prior_trace, incoming_text)
            prior_trace = f"{prior_trace}{tool_turn}"
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

    def _infer_info_from_calls(self, calls: list[dict]) -> dict:
        for call in calls:
            params = call.get("params") or {}
            for value in params.values():
                if not isinstance(value, str):
                    continue
                for trace_prefix, info in self.trace_infos.items():
                    if value == trace_prefix or value.startswith(trace_prefix + "/"):
                        return info
        return {}


# ---------------------------------------------------------------------------
# PRIME-RL environment entrypoint
# ---------------------------------------------------------------------------

# load prompts, pack metadata into `info`, registers _rust_tool_reward and returns `RustToolEnv`
def load_environment(
    data_path: str = "synthetic_data/rl_prompts_1062.jsonl",
    max_samples: int | None = None,
    env_id: str = "task-trace",
    nsjail_path: str | None = None,
    timeout: int = 30,
    max_tool_rounds: int = 5,
    structure_valid_bonus: float | None = None,
    no_call_penalty: float | None = None,
    malformed_call_penalty: float | None = None,
    bad_cargo_project_path_penalty: float | None = None,
    gibberish_penalty: float | None = None,
    bad_final_hygiene_penalty: float | None = None,
    tool_budget_exhausted_penalty: float | None = None,
    final_once_bonus: float | None = None,
    missing_final_penalty: float | None = None,
    verifier_success_bonus: float | None = None,
    verifier_success_clean_final_bonus: float | None = None,
    tool_after_success_penalty: float | None = None,
    failed_verifier_penalty: float | None = None,
    max_failed_verifier_penalty: float | None = None,
) -> vf.Environment:
    """Load the Rust tool RL environment with real multi-round tool execution."""
    _set_reward_config(
        {
            "structure_valid_bonus": structure_valid_bonus,
            "no_call_penalty": no_call_penalty,
            "malformed_call_penalty": malformed_call_penalty,
            "bad_cargo_project_path_penalty": bad_cargo_project_path_penalty,
            "gibberish_penalty": gibberish_penalty,
            "bad_final_hygiene_penalty": bad_final_hygiene_penalty,
            "tool_budget_exhausted_penalty": tool_budget_exhausted_penalty,
            "final_once_bonus": final_once_bonus,
            "missing_final_penalty": missing_final_penalty,
            "verifier_success_bonus": verifier_success_bonus,
            "verifier_success_clean_final_bonus": verifier_success_clean_final_bonus,
            "tool_after_success_penalty": tool_after_success_penalty,
            "failed_verifier_penalty": failed_verifier_penalty,
            "max_failed_verifier_penalty": max_failed_verifier_penalty,
        }
    )

    prompts, _ = load_prompts(
        data_path=data_path,
        max_samples=max_samples,
    )
    # Verifiers at our prime-rl pin forwards a dataset row's `info` dict into
    # env_response / reward kwargs but does NOT forward arbitrary top-level
    # columns. Pack expected_tool / expected_args / blueprint_root / trace_prefix /
    # expected_output into `info` so the env can actually execute the verifier.
    info_keys = (
        "expected_tool",
        "expected_args",
        "blueprint_root",
        "trace_prefix",
        "expected_output",
        "kind",
    )
    rows = []
    trace_infos: dict[str, dict] = {}
    for item in prompts:
        info = {k: item[k] for k in info_keys if k in item}
        rows.append({"prompt": item["prompt"], "info": info, "task": env_id})
        trace_prefix = info.get("trace_prefix")
        if trace_prefix:
            trace_infos[str(trace_prefix)] = info
    dataset = Dataset.from_list(rows)

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
        message_type="chat",
        env_id=env_id,
        executor=executor,
        max_tool_rounds=max_tool_rounds,
        trace_infos=trace_infos,
    )
    return env
