from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path

from datasets import Dataset

import verifiers as vf
from core.validator import TaskValidator
from rl.task_format import TaskVerifier, load_prompts


def _canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _review_key(prompt, completion) -> str:
    payload = _canonical_json({"prompt": prompt, "completion": completion})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def _load_review_rejections() -> dict[str, float]:
    path = os.environ.get("GLYPH_REVIEW_REJECTIONS")
    if not path:
        return {}

    file_path = Path(path)
    if not file_path.exists():
        return {}

    default_floor = float(os.environ.get("GLYPH_REVIEW_REWARD_FLOOR", "-2"))
    rejected: dict[str, float] = {}
    with file_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            key = row.get("review_key")
            if not key and "prompt" in row and "completion" in row:
                key = _review_key(row["prompt"], row["completion"])
            if not key:
                continue
            rejected[key] = float(row.get("reward_floor", default_floor))
    return rejected


def _get_reward_floor(prompt, completion) -> float | None:
    rejected = _load_review_rejections()
    if not rejected:
        return None
    return rejected.get(_review_key(prompt, completion))


async def _verifier_reward(completion, **kwargs) -> float:
    verifier: TaskVerifier = kwargs["verifier"]
    prompt = kwargs.get("prompt")
    floor = _get_reward_floor(prompt, completion)
    if floor is not None:
        return floor
    text = completion if isinstance(completion, str) else completion[-1]["content"]
    score, _ = verifier.compute_reward(text)
    return score


async def _smoke_reward(completion, **kwargs) -> float:
    verifier: TaskVerifier = kwargs["verifier"]
    validator: TaskValidator = kwargs["validator"]
    prompt = kwargs.get("prompt")
    floor = _get_reward_floor(prompt, completion)
    if floor is not None:
        return floor
    text = completion if isinstance(completion, str) else completion[-1]["content"]
    struct_pass = 1.0 if validator.validate(text).valid else 0.0
    section_credit, _ = verifier.compute_reward(text)
    return struct_pass + section_credit


def load_environment(
    data_path: str = "traces.processed.jsonl",
    max_samples: int | None = None,
    max_trace_chars: int | None = 50000,
    env_id: str = "task-trace",
    reward_mode: str = "verifier_only",
) -> vf.Environment:
    """Load a TASK-format verifiers environment backed by local prompts."""

    prompts, _ = load_prompts(
        data_path=data_path,
        max_samples=max_samples,
        max_trace_chars=max_trace_chars,
    )
    dataset = Dataset.from_list(
        [
            {
                "prompt": item["prompt"],
                "task": env_id,
            }
            for item in prompts
        ]
    )

    parser = vf.Parser()
    verifier = TaskVerifier()
    validator = TaskValidator()
    rubric = vf.Rubric(parser=parser)
    rubric.class_objects["verifier"] = verifier
    rubric.class_objects["validator"] = validator
    if reward_mode == "smoke_deterministic":
        rubric.add_reward_func(_smoke_reward, weight=1.0)
    elif reward_mode == "verifier_only":
        rubric.add_reward_func(_verifier_reward, weight=1.0)
    else:
        raise ValueError(f"Unknown reward_mode={reward_mode!r}")

    env = vf.SingleTurnEnv(
        dataset=dataset,
        parser=parser,
        rubric=rubric,
        message_type="completion",
        env_id=env_id,
    )
    return env
