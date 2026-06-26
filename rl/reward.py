from __future__ import annotations

import re
from types import MappingProxyType
from typing import Mapping

from agent_runtime.protocol import (
    ProtocolCall,
    SimpleTraceValidator,
    call_syntax_errors,
    ended_cleanly_after_final,
    final_count,
    final_hygiene_errors,
    parse_calls,
    strip_generated_assistant_stop,
)
from agent_runtime.rust.executor import ExecutionResult
from rl.rollout_text import (
    collect_rollout_text,
    completion_role_text,
    completion_text,
)


# Eval-aligned reward for reliability lift. The only positive outcome is the
# heldout-style valid trace: cargo verifier pass, no later tools, exactly one
# clean FINAL after the passing result, and no protocol errors. Invalid cargo
# success is not rewarded; it only avoids some failure penalties.
DEFAULT_REWARD_CONFIG = MappingProxyType({
    # format floor
    "structure_valid_bonus": 0.0,
    "no_call_penalty": -5.0,
    "malformed_call_penalty": -4.0,
    "no_verifier_penalty": -3.0,
    "bad_cargo_project_path_penalty": -4.0,
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
})


RewardConfig = Mapping[str, float]


def build_reward_config(overrides: dict[str, float | None]) -> dict[str, float]:
    config = dict(DEFAULT_REWARD_CONFIG)
    config.update({k: v for k, v in overrides.items() if v is not None})
    return config


def _structure_reward(
    assistant_text: str,
    result_text: str,
    validator: SimpleTraceValidator | None,
    reward_config: RewardConfig,
) -> float:
    if validator is None:
        return 0.0
    v = validator.validate(assistant_text, result_text)
    return reward_config["structure_valid_bonus"] if v.valid else 0.0


def _finalization_reward(assistant_text: str, reward_config: RewardConfig) -> float:
    """Exactly one FINAL -> small bonus; otherwise the missing-FINAL penalty."""
    if final_count(assistant_text) == 1:
        return reward_config["final_once_bonus"]
    return reward_config["missing_final_penalty"]


def _result_offset(call_id: str, full_text: str) -> int:
    return full_text.find(f"RESULT {call_id}:")


def _heldout_style_success(
    assistant_text: str,
    full_text: str,
    success_pos: int,
    later_tools: list[ProtocolCall],
    latest_assistant_turn: str,
    protocol_errors: list[str] | None = None,
) -> bool:
    if protocol_errors:
        return False
    if success_pos < 0 or later_tools:
        return False
    if not latest_assistant_turn.strip().startswith("FINAL:"):
        return False
    if final_count(assistant_text) != 1:
        return False
    if not ended_cleanly_after_final(assistant_text):
        return False
    if final_hygiene_errors(assistant_text):
        return False
    final_pos = full_text.rfind("FINAL:")
    return final_pos > success_pos


def _cargo_project_path_errors(calls: list[ProtocolCall]) -> list[str]:
    errors: list[str] = []
    for call in calls:
        if call.tool not in {"cargo_run", "cargo_test"}:
            continue
        project_path = str(call.params.get("project_path", ""))
        if re.search(r"/src/(?:main|lib)\.rs$", project_path):
            errors.append(f"{call.id}: cargo project_path points at source file")
    return errors


def _protocol_reward_penalty(
    assistant_text: str,
    calls: list[ProtocolCall],
    state: dict,
    reward_config: RewardConfig,
) -> tuple[float, list[str]]:
    errors: list[str] = []
    errors.extend(call_syntax_errors(assistant_text))
    errors.extend(_cargo_project_path_errors(calls))
    if state.get("malformed_call_errors"):
        errors.extend(str(e) for e in state["malformed_call_errors"])
    penalty = 0.0
    if any("CALL" in e or "argument" in e for e in errors):
        penalty += reward_config["malformed_call_penalty"]
    if any("project_path" in e for e in errors):
        penalty += reward_config["bad_cargo_project_path_penalty"]
    final_errors = final_hygiene_errors(assistant_text)
    if final_errors:
        errors.extend(final_errors)
        penalty += reward_config["bad_final_hygiene_penalty"]
    return penalty, errors


def _outcome_reward(
    calls: list[ProtocolCall],
    executed_results: dict[str, ExecutionResult],
    assistant_text: str,
    full_text: str,
    latest_assistant_turn: str,
    reward_config: RewardConfig,
    protocol_errors: list[str] | None = None,
) -> float:
    """Primary signal: exact heldout-style success."""
    success_idx: int | None = None
    success_pos = -1
    failed_before_success = 0
    saw_verifier_result = False
    for idx, call in enumerate(calls):
        if call.tool not in {"cargo_test", "cargo_run"}:
            continue
        result = executed_results.get(call.id)
        if result is None:
            continue
        saw_verifier_result = True
        if result.success:
            success_idx = idx
            pos = _result_offset(call.id, full_text)
            if pos >= 0:
                success_pos = pos
            break
        failed_before_success += 1

    if not saw_verifier_result:
        return reward_config["no_verifier_penalty"]

    fail_penalty = max(
        reward_config["max_failed_verifier_penalty"],
        failed_before_success * reward_config["failed_verifier_penalty"],
    )

    if success_idx is None:
        return fail_penalty

    reward = reward_config["verifier_success_bonus"] + fail_penalty
    later_tools = calls[success_idx + 1 :]
    if later_tools:
        reward += reward_config["tool_after_success_penalty"]

    if _heldout_style_success(
        assistant_text,
        full_text,
        success_pos,
        later_tools,
        latest_assistant_turn,
        protocol_errors,
    ):
        reward += reward_config["verifier_success_clean_final_bonus"]
    return reward


async def _rust_tool_reward(completion, **kwargs) -> float:
    """Score the full multi-turn rollout from the transcript the env produced."""
    state = kwargs.get("state") or {}
    text = completion_text(completion)
    reward_config = kwargs.get("reward_config") or DEFAULT_REWARD_CONFIG
    rollout_text = collect_rollout_text(state)
    assistant_text = rollout_text.assistant or completion_role_text(
        completion, "assistant"
    )
    executed_calls = state.get("executed_tool_calls") or []
    executed_results = state.get("executed_results") or {}
    tool_text = "\n".join(state.get("executed_result_blocks") or [])
    if not tool_text:
        tool_text = rollout_text.tool or completion_role_text(
            completion, "tool"
        )
    full_text = rollout_text.full or text
    info = kwargs.get("info") or state.get("resolved_info") or {}
    expected_tool = info.get("expected_tool")
    validator: SimpleTraceValidator | None = kwargs.get("validator")
    raw_assistant_trace = assistant_text or text
    reward_assistant_trace = strip_generated_assistant_stop(raw_assistant_trace).strip()
    assistant_trace = strip_generated_assistant_stop(raw_assistant_trace)
    latest_assistant_turn = (
        rollout_text.latest_assistant
        or strip_generated_assistant_stop(completion_role_text(completion, "assistant")).strip()
    )
    structure = _structure_reward(assistant_trace, tool_text, validator, reward_config)

    if not expected_tool:
        return structure

    calls = parse_calls(assistant_trace) or executed_calls
    if not calls:
        protocol_penalty, _ = _protocol_reward_penalty(
            reward_assistant_trace,
            [],
            state,
            reward_config,
        )
        return reward_config["no_call_penalty"] + protocol_penalty + structure

    reward = 0.0
    malformed = len(re.findall(r"\bCALL[A-Z]", raw_assistant_trace))
    reward += min(malformed, 4) * reward_config["malformed_call_penalty"]
    protocol_penalty, protocol_errors = _protocol_reward_penalty(
        reward_assistant_trace,
        calls,
        state,
        reward_config,
    )
    reward += protocol_penalty

    reward += _finalization_reward(reward_assistant_trace, reward_config)
    reward += _outcome_reward(
        calls,
        executed_results,
        reward_assistant_trace,
        full_text,
        latest_assistant_turn,
        reward_config,
        protocol_errors,
    )
    if protocol_errors:
        reward = min(reward, 0.0)

    if state.get("tool_budget_exhausted"):
        reward += reward_config["tool_budget_exhausted_penalty"]

    return reward + structure
