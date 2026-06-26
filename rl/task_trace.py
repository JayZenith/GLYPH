from __future__ import annotations

from datasets import Dataset

import verifiers as vf
from agent_runtime.protocol import SimpleTraceValidator
from agent_runtime.rust.executor import RustExecutor
from rl.environment import RustToolEnv
from rl.reward import _rust_tool_reward, build_reward_config
from rl.task_format import load_prompts


def build_dataset(prompts, env_id) -> tuple[Dataset, dict[str, dict]]:
    """Build rollout tasks for Verifiers and lookup metadata for runtime inference."""
    # Dataset ownership: these rows are the tasks available for rollout.
    # Keep the row shape stable because PRIME-RL/verifiers consume these keys.
    info_keys = (
        "expected_tool",
        "blueprint_root",
        "trace_prefix",
        "expected_output",
    )
    rows = []
    trace_infos: dict[str, dict] = {}
    for item in prompts:
        info = {k: item[k] for k in info_keys if k in item}
        rows.append({"prompt": item["prompt"], "info": info, "task": env_id})
        trace_prefix = info.get("trace_prefix") or info.get("blueprint_root")
        if trace_prefix:
            trace_infos[str(trace_prefix)] = info
    return Dataset.from_list(rows), trace_infos


def build_rubric(reward_config) -> vf.Rubric:
    """Build the Verifiers reward container for Glyph rollouts."""
    # Parser ownership: verifiers threads a Parser through Rubric and Env even
    # though Glyph's reward reads chat/state directly. Keep it explicit because
    # the pinned runtime examples construct Rubric(parser=parser).
    parser = vf.Parser()

    # Validator ownership: checks Glyph protocol structure before the clean
    # success bonus can be awarded.
    validator = SimpleTraceValidator()

    # Rubric ownership: Verifiers container that invokes reward functions.
    rubric = vf.Rubric(parser=parser)
    rubric.class_objects["validator"] = validator

    # Reward config ownership: numeric reward/penalty values shared with the
    # reward function through Verifiers' class_objects.
    rubric.class_objects["reward_config"] = reward_config

    # _rust_tool_reward ownership: computes the final scalar reward for a
    # completed rollout.
    rubric.add_reward_func(_rust_tool_reward, weight=1.0)
    return rubric


def load_environment(
    data_path: str = "synthetic_data/rl_prompts_signal_v3_pool_b_mixed.jsonl",
    max_samples: int | None = None,
    env_id: str = "task-trace",
    timeout: int = 30,
    max_tool_rounds: int = 5,
    structure_valid_bonus: float | None = None,
    no_call_penalty: float | None = None,
    malformed_call_penalty: float | None = None,
    no_verifier_penalty: float | None = None,
    bad_cargo_project_path_penalty: float | None = None,
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
    # Load prompt data: JSONL prompts are normalized into chat-message rows.
    prompts, _ = load_prompts(
        data_path=data_path,
        max_samples=max_samples,
    )
    dataset, trace_infos = build_dataset(prompts, env_id)

    reward_config = build_reward_config(
        {
            "structure_valid_bonus": structure_valid_bonus,
            "no_call_penalty": no_call_penalty,
            "malformed_call_penalty": malformed_call_penalty,
            "no_verifier_penalty": no_verifier_penalty,
            "bad_cargo_project_path_penalty": bad_cargo_project_path_penalty,
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
    rubric = build_rubric(reward_config)

    # Executor ownership: runs real Rust tools inside the rollout environment.
    executor = RustExecutor(timeout=timeout)

    # RustToolEnv ownership: runs one multi-turn tool-use episode.
    return RustToolEnv(
        dataset=dataset,
        parser=rubric.parser,
        rubric=rubric,
        message_type="chat",
        env_id=env_id,
        executor=executor,
        max_tool_rounds=max_tool_rounds,
        trace_infos=trace_infos,
    )
