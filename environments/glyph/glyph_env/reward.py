from __future__ import annotations

import re
from types import MappingProxyType
from typing import Mapping

from .agent_runtime.protocol import (
    ProtocolCall,
    SimpleTraceValidator,
    call_syntax_errors,
    ended_cleanly_after_final,
    final_count,
    parse_calls,
    strip_generated_assistant_stop,
)
from .agent_runtime.rust.executor import ExecutionResult
from .rollout_text import (
    collect_rollout_text,
    completion_role_text,
    completion_text,
)


# Eval-aligned reward for reliability lift. The only positive outcome is the
# heldout-style valid trace: cargo verifier pass, no later tools, exactly one
# clean FINAL after the passing result, and no protocol errors. Invalid cargo
# success is not rewarded; it only avoids some failure penalties.
#
# Default reward table:
# valid structure -> 0; no CALL -> -5; malformed CALL -> -4
# no cargo verifier -> -3; cargo project_path points at source file -> -4
# missing FINAL -> -3; clean verifier success -> +10
# tool after verifier success -> -6; tool budget exhausted -> -5
# failed verifier before success -> -1 each, bounded at -4
DEFAULT_REWARD_CONFIG = MappingProxyType({
    # format floor
    "structure_valid_bonus": 0.0,
    "no_call_penalty": -5.0,
    "malformed_call_penalty": -4.0,
    "no_verifier_penalty": -3.0,
    "bad_cargo_project_path_penalty": -4.0,
    # Deprecated no-op kept so old launch commands/configs still validate.
    "bad_final_hygiene_penalty": 0.0,
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
    # Dense partial-credit shaping applied ONLY when no cargo verifier succeeded.
    # Turns the all-fail region (which otherwise scores identically -> zero
    # advantage -> filtered out of training) into a graded signal: did it
    # compile, and what fraction of tests passed. Kept well below the +10
    # clean-success bonus so full success still dominates the gradient. Off by
    # default (0.0) to preserve the sparse reward; enable per-run via CLI.
    "progress_compile_bonus": 0.0,
    "progress_test_frac_bonus": 0.0,
    # Compiler-phase ladder: a Rust-specific dense signal. rustc fails in a fixed
    # phase order (parse -> type/resolve -> borrow/lifetime -> compiles), and
    # reaching a later phase requires passing every earlier one, so the furthest
    # phase a crate reaches is a principled, hard-to-game distance-to-compiling.
    # Rewards graded progress in the never-compiles region that the coarse
    # compile-bonus leaves flat. Off by default; the compiler-aware run sets this
    # alone (compile/test-frac bonuses 0) for a clean A/B vs the generic dense reward.
    "progress_error_ladder_bonus": 0.0,
})


RewardConfig = Mapping[str, float]


# Consumes CLI/env overrides and returns the numeric reward table used by the scorer.
def build_reward_config(overrides: dict[str, float | None]) -> dict[str, float]:
    config = dict(DEFAULT_REWARD_CONFIG)
    config.update({k: v for k, v in overrides.items() if v is not None})
    return config


# Consumes assistant/tool text and owns the protocol-validity gate used by the
# clean-success bonus. Returns (structure scalar, validator_valid).
def _structure_reward(
    assistant_text: str,
    result_text: str,
    validator: SimpleTraceValidator | None,
    reward_config: RewardConfig,
) -> tuple[float, bool]:
    if validator is None:
        return 0.0, True
    v = validator.validate(assistant_text, result_text)
    structure = reward_config["structure_valid_bonus"] if v.valid else 0.0
    return structure, v.valid


# Consumes assistant text and owns the single-FINAL shaping decision. Returns a scalar.
def _finalization_reward(assistant_text: str, reward_config: RewardConfig) -> float:
    """Exactly one FINAL -> small bonus; otherwise the missing-FINAL penalty."""
    if final_count(assistant_text) == 1:
        return reward_config["final_once_bonus"]
    return reward_config["missing_final_penalty"]


# Consumes a CALL id and full transcript. Returns the byte offset of its RESULT block.
def _result_offset(call_id: str, full_text: str) -> int:
    return full_text.find(f"RESULT {call_id}:")


# Consumes normalized transcript facts and owns the exact heldout-style success
# predicate. Returns a boolean, not reward points.
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
    final_pos = full_text.rfind("FINAL:")
    return final_pos > success_pos


# Consumes parsed CALLs and owns cargo-specific argument validation. Returns errors.
def _cargo_project_path_errors(calls: list[ProtocolCall]) -> list[str]:
    errors: list[str] = []
    for call in calls:
        if call.tool not in {"cargo_run", "cargo_test"}:
            continue
        project_path = str(call.params.get("project_path", ""))
        if re.search(r"/src/(?:main|lib)\.rs$", project_path):
            errors.append(f"{call.id}: cargo project_path points at source file")
    return errors


# Consumes assistant text, parsed calls, and runtime state. Returns
# (protocol penalty scalar, protocol error strings).
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
    return penalty, errors


# Consumes parsed calls plus structured execution results and owns verifier
# success/failure reward. Returns a scalar.
_TEST_RESULT_RE = re.compile(r"test result:\s*\w+\.\s*(\d+)\s+passed;\s*(\d+)\s+failed")

# rustc error codes raised during borrow check / lifetime resolution. Their
# presence implies the crate already passed lexing, parsing, name resolution,
# and type check — i.e. it reached a late compiler phase. Everything else with
# an error[Ennnn] code is treated as an earlier (type/resolution) failure, and a
# bare "error:" with no code as an earliest (parse/syntax) failure.
_E_CODE_RE = re.compile(r"error\[E(\d{4})\]")
_BORROW_LIFETIME_CODES = frozenset({
    "0382", "0499", "0502", "0503", "0505", "0506", "0507", "0508", "0509",
    "0515", "0597", "0716",  # borrow / move / temporary lifetime
    "0106", "0309", "0310", "0311", "0621", "0623",  # explicit lifetime
})


def _compiler_phase_stage(out: str, compiled: bool) -> int:
    """Furthest rustc phase the crate reached, as a 0-4 ladder.

    4 compiles · 3 borrow/lifetime (type-checked) · 2 type/resolution (parsed) ·
    1 parse/syntax · 0 nothing. Monotone in real progress because each phase
    gates the next, so the model cannot climb it without genuinely better Rust.
    """
    if compiled:
        return 4
    codes = set(_E_CODE_RE.findall(out))
    if codes & _BORROW_LIFETIME_CODES:
        return 3
    if codes:
        return 2
    if "error" in out:
        return 1
    return 0


def _progress_reward(
    calls: list[ProtocolCall],
    executed_results: dict[str, ExecutionResult],
    reward_config: RewardConfig,
) -> float:
    """Dense partial credit for the no-success region.

    Scans cargo verifier results for the best partial progress across the
    rollout: whether the crate compiled, the highest test-pass fraction, and
    (compiler-aware arm) the furthest rustc phase reached. All are objective task
    facts the model cannot game (tests/expected output are fixed by the case;
    the phase ladder is monotone in real progress). Returns 0.0 when every
    shaping bonus is disabled, so the default sparse reward is unchanged.
    """
    compile_bonus = reward_config.get("progress_compile_bonus", 0.0)
    test_bonus = reward_config.get("progress_test_frac_bonus", 0.0)
    ladder_bonus = reward_config.get("progress_error_ladder_bonus", 0.0)
    if not compile_bonus and not test_bonus and not ladder_bonus:
        return 0.0

    compiled = False
    best_test_frac = 0.0
    best_stage = 0
    for call in calls:
        if call.tool not in {"cargo_test", "cargo_run"}:
            continue
        result = executed_results.get(call.id)
        if result is None:
            continue
        out = f"{result.stdout or ''}\n{result.stderr or ''}"
        compile_failed = ("error[E" in out) or ("could not compile" in out)
        call_compiled = not compile_failed and (
            result.success or "test result:" in out or "Finished" in out or "Running `" in out
        )
        if call_compiled:
            compiled = True
        for match in _TEST_RESULT_RE.finditer(out):
            passed, failed = int(match.group(1)), int(match.group(2))
            if passed + failed > 0:
                best_test_frac = max(best_test_frac, passed / (passed + failed))
        if ladder_bonus:
            best_stage = max(best_stage, _compiler_phase_stage(out, call_compiled))

    reward = (compile_bonus if compiled else 0.0) + test_bonus * best_test_frac
    if ladder_bonus:
        reward += ladder_bonus * (best_stage / 4.0)
    return reward


def _outcome_reward(
    calls: list[ProtocolCall],
    executed_results: dict[str, ExecutionResult],
    assistant_text: str,
    full_text: str,
    latest_assistant_turn: str,
    reward_config: RewardConfig,
    validator_valid: bool,
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
        return fail_penalty + _progress_reward(calls, executed_results, reward_config)

    reward = reward_config["verifier_success_bonus"] + fail_penalty
    later_tools = calls[success_idx + 1 :]
    if later_tools:
        reward += reward_config["tool_after_success_penalty"]

    if validator_valid and _heldout_style_success(
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
    # 1. Reconstruct rollout text/state from Verifiers completion + env state.
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

    # 2. Validate protocol structure. Validator validity gates the +10 clean success.
    structure, validator_valid = _structure_reward(
        assistant_trace,
        tool_text,
        validator,
        reward_config,
    )

    if not expected_tool:
        return structure

    # 3. Parse CALLs from assistant text, falling back to env-recorded calls.
    calls = parse_calls(assistant_trace) or executed_calls
    if not calls:
        protocol_penalty, _ = _protocol_reward_penalty(
            reward_assistant_trace,
            [],
            state,
            reward_config,
        )
        return reward_config["no_call_penalty"] + protocol_penalty + structure

    # 4. Calculate malformed/protocol penalties.
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

    # 5. Calculate FINAL penalties.
    reward += _finalization_reward(reward_assistant_trace, reward_config)

    # 6-7. Inspect cargo verifier results and award exact clean success if valid.
    reward += _outcome_reward(
        calls,
        executed_results,
        reward_assistant_trace,
        full_text,
        latest_assistant_turn,
        reward_config,
        validator_valid,
        protocol_errors,
    )
    if protocol_errors:
        reward = min(reward, 0.0)

    # 8. Apply tool-budget penalty if the environment marked the rollout exhausted.
    if state.get("tool_budget_exhausted"):
        reward += reward_config["tool_budget_exhausted_penalty"]

    # 9. Return one scalar reward to Verifiers/PRIME-RL.
    return reward + structure
