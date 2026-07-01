from __future__ import annotations

import tempfile
from pathlib import Path

from datasets import Dataset

import verifiers as vf

from .agent_runtime.protocol import SimpleTraceValidator
from .agent_runtime.rust.executor import RustExecutor
from .environment import RustToolEnv
from .reward import _rust_tool_reward, build_reward_config
from .task_format import load_prompts

CRATES_DATASET_REPO = "JayZenith/glyph-crates"
DEFAULT_DATA_FILE = "rl_prompts_pool_b_mixed_oversampled.jsonl"


def _resolve_data_path(data_path: str | None) -> tuple[str, Path]:
    """Download the companion crate-blueprints dataset and return
    (jsonl path, blueprints root) for a self-contained install off the Hub.

    GLYPH's tasks reference real Rust crate templates on disk
    (`blueprint_root` / `trace_prefix`); those live in a companion HF dataset
    rather than this wheel, so this pulls + caches them on first use and
    rewrites prompt rows to point at the cached copy.
    """
    from huggingface_hub import snapshot_download

    cache_root = Path(
        snapshot_download(repo_id=CRATES_DATASET_REPO, repo_type="dataset")
    )
    resolved_data_path = data_path or str(cache_root / DEFAULT_DATA_FILE)
    return resolved_data_path, cache_root


def _rewrite_blueprint_paths(prompts: list[dict], cache_root: Path) -> None:
    """Prompt rows ship with repo-relative blueprint_root/trace_prefix values
    (e.g. "synthetic_data/blueprints/<case>"); rewrite them onto the local
    cached copy of the companion crates dataset so sandboxing works anywhere.
    """
    for row in prompts:
        for key in ("blueprint_root", "trace_prefix"):
            value = row.get(key)
            if not value:
                continue
            rel = value.split("synthetic_data/", 1)[-1]
            candidate = cache_root / rel
            if candidate.exists():
                row[key] = str(candidate)


def build_dataset(prompts, env_id) -> tuple[Dataset, dict[str, dict]]:
    """Build rollout tasks for Verifiers and lookup metadata for runtime inference."""
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
    parser = vf.Parser()
    validator = SimpleTraceValidator()
    rubric = vf.Rubric(parser=parser)
    rubric.class_objects["validator"] = validator
    rubric.class_objects["reward_config"] = reward_config
    rubric.add_reward_func(_rust_tool_reward, weight=1.0)
    return rubric


def load_environment(
    data_path: str | None = None,
    max_samples: int | None = None,
    env_id: str = "glyph",
    timeout: int = 30,
    max_tool_rounds: int = 15,
    sandbox_root: str | None = None,
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
    progress_compile_bonus: float | None = None,
    progress_test_frac_bonus: float | None = None,
    progress_error_ladder_bonus: float | None = None,
) -> vf.Environment:
    """Load the GLYPH Rust tool-use RL environment with real cargo execution.

    A tool-use agent patches real Rust crates until `cargo_test`/`cargo_run`
    verifies success, or confirms an already-correct crate, then must end with
    a clean FINAL. Reward is verifiable: cargo actually compiles and runs.
    See https://github.com/JayZenith/GLYPH and https://jayzenith.github.io/GLYPH/.

    Crate templates are pulled from the companion `JayZenith/glyph-crates`
    dataset on first use and cached locally (~30MB) -- pass `data_path` to
    point at a custom prompts JSONL instead of the bundled default.

    Requires a Rust toolchain (`cargo`/`rustc`) on PATH; install via
    https://rustup.rs if `rustc --version` fails.
    """
    resolved_data_path, cache_root = _resolve_data_path(data_path)
    prompts, _ = load_prompts(data_path=resolved_data_path, max_samples=max_samples)
    _rewrite_blueprint_paths(prompts, cache_root)
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
            "progress_compile_bonus": progress_compile_bonus,
            "progress_test_frac_bonus": progress_test_frac_bonus,
            "progress_error_ladder_bonus": progress_error_ladder_bonus,
        }
    )
    rubric = build_rubric(reward_config)

    executor = RustExecutor(timeout=timeout)
    resolved_sandbox_root = Path(sandbox_root) if sandbox_root else Path(tempfile.gettempdir()) / "glyph_sandboxes"

    return RustToolEnv(
        dataset=dataset,
        parser=rubric.parser,
        rubric=rubric,
        message_type="chat",
        env_id=env_id,
        executor=executor,
        max_tool_rounds=max_tool_rounds,
        sandbox_root=resolved_sandbox_root,
        trace_infos=trace_infos,
    )
