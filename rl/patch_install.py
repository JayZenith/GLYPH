#!/usr/bin/env python3
"""
Patch an installed PRIME-RL checkout to bootstrap trainer LoRA weights from a
PEFT adapter via `PRIME_RL_INIT_ADAPTER=/path/to/adapter`.
"""

from __future__ import annotations

import argparse
from pathlib import Path


HELPER = """
def _maybe_load_initial_lora_adapter(model: nn.Module) -> None:
    adapter_dir_env = os.environ.get("PRIME_RL_INIT_ADAPTER")
    if not adapter_dir_env:
        return

    logger = get_logger()
    adapter_dir = Path(adapter_dir_env)
    if not adapter_dir.exists():
        raise FileNotFoundError(f"Initial LoRA adapter path does not exist: {adapter_dir}")

    from safetensors.torch import load_file

    weights_path = adapter_dir / "adapter_model.safetensors"
    if not weights_path.exists():
        raise FileNotFoundError(f"Expected adapter weights at {weights_path}")

    translated = {}
    for key, value in load_file(weights_path).items():
        new_key = key
        if new_key.startswith("base_model.model."):
            new_key = new_key[len("base_model.model.") :]
        if ".modules_to_save.default." in new_key:
            new_key = new_key.replace(".modules_to_save.default.", ".")
        if new_key.endswith(".weight") and (".lora_A." in new_key or ".lora_B." in new_key):
            new_key = new_key[: -len(".weight")]
        if new_key.endswith(".lora_A"):
            new_key += ".0"
        elif new_key.endswith(".lora_B"):
            new_key += ".0"
        translated[new_key] = value

    model_state = model.state_dict()
    loaded = 0
    missing = []
    mismatched = []
    with torch.no_grad():
        for key, value in translated.items():
            target = model_state.get(key)
            if target is None:
                missing.append(key)
                continue
            if tuple(target.shape) != tuple(value.shape):
                mismatched.append((key, tuple(target.shape), tuple(value.shape)))
                continue
            target.copy_(value.to(device=target.device, dtype=target.dtype))
            loaded += 1

    if mismatched:
        first = mismatched[0]
        raise ValueError(
            f"Adapter shape mismatch for {first[0]}: model={first[1]} adapter={first[2]} "
            f"(and {len(mismatched) - 1} more)"
        )

    if missing:
        logger.warning(f"Skipped {len(missing)} adapter tensors not found in PRIME-RL model")

    logger.info(f"Loaded initial LoRA adapter from {adapter_dir} into {loaded} PRIME-RL tensors")
""".strip()

TEACHER_LOGPROB_PATCH_OLD = """import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from itertools import cycle
from pathlib import Path
from typing import Any

import pandas as pd
import verifiers as vf
from rich.console import Console
from rich.table import Table
from verifiers.utils.client_utils import setup_openai_client
"""

TEACHER_LOGPROB_PATCH_NEW = """import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from itertools import cycle
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import verifiers as vf
from rich.console import Console
from rich.table import Table
"""

TEACHER_LOGPROB_BLOCK_OLD = """async def compute_teacher_logprobs(
    clients: list[vf.ClientConfig],
    model_name: str,
    samples: list[TrainingSample],
) -> list[list[float]]:
    \"\"\"Compute teacher model logprobs for a batch of training samples via prefill.\"\"\"
    from prime_rl.inference.vllm.serving_generate import GenerateResponse

    async def _compute_single(client_config: vf.ClientConfig, sample: TrainingSample) -> list[float]:
        client = setup_openai_client(client_config)

        response = await client.post(
            \"/generate\",
            cast_to=GenerateResponse,
            body={
                \"model\": model_name,
                \"prompt_token_ids\": sample.prompt_ids + sample.completion_ids,
                \"max_tokens\": 1,
                \"temperature\": 1.0,
                \"top_p\": 1.0,
                \"prompt_logprobs\": True,
            },
        )
        return [0.0 if lp is None else float(lp) for lp in response.prompt_logprobs or []]

    return await asyncio.gather(*[_compute_single(client, sample) for client, sample in zip(cycle(clients), samples)])
"""

TEACHER_LOGPROB_BLOCK_NEW = """async def compute_teacher_logprobs(
    clients: list[vf.ClientConfig],
    model_name: str,
    samples: list[TrainingSample],
) -> list[list[float]]:
    \"\"\"Compute teacher model logprobs for a batch of training samples via prefill.\"\"\"

    async def _compute_single(client_config: vf.ClientConfig, sample: TrainingSample) -> list[float]:
        headers = dict(getattr(client_config, \"extra_headers\", {}) or {})
        api_key_var = getattr(client_config, \"api_key_var\", None)
        if api_key_var:
            api_key = os.getenv(api_key_var)
            if api_key:
                headers.setdefault(\"Authorization\", f\"Bearer {api_key}\")

        async with httpx.AsyncClient(
            base_url=client_config.api_base_url,
            timeout=getattr(client_config, \"timeout\", 1200),
            headers=headers,
        ) as client:
            response = await client.post(
                \"/generate\",
                json={
                    \"model\": model_name,
                    \"prompt_token_ids\": sample.prompt_ids + sample.completion_ids,
                    \"max_tokens\": 1,
                    \"temperature\": 1.0,
                    \"top_p\": 1.0,
                    \"prompt_logprobs\": True,
                },
            )
            response.raise_for_status()
            payload = response.json()

        return [0.0 if lp is None else float(lp) for lp in payload.get(\"prompt_logprobs\") or []]

    return await asyncio.gather(*[_compute_single(client, sample) for client, sample in zip(cycle(clients), samples)])
"""


CALL_MARKER = "        apply_lora_to_model(model, config.lora)\n"
CALL_INSERT = CALL_MARKER + "        _maybe_load_initial_lora_adapter(model)\n"


def patch_model_py(path: Path) -> None:
    text = path.read_text()
    if "_maybe_load_initial_lora_adapter" in text:
        return
    if CALL_MARKER not in text:
        raise RuntimeError("Could not find LoRA insertion point in trainer/model.py")

    insert_after = "def pre_download_model(model_name: str) -> None:\n"
    idx = text.find("\n\n", text.find(insert_after))
    if idx == -1:
        raise RuntimeError("Could not find insertion point for helper in trainer/model.py")

    text = text[: idx + 2] + HELPER + "\n\n" + text[idx + 2 :]
    text = text.replace(CALL_MARKER, CALL_INSERT, 1)
    path.write_text(text)


def patch_ckpt_py(path: Path) -> None:
    text = path.read_text()
    old = """        else:
            # For regular transformers models, revert internal format to original HF hub format
            from transformers.core_model_loading import revert_weight_conversion

            self.logger.debug("Reverting transformers internal format to HF hub format for weight checkpoint")
            start_time = time.perf_counter()
            state_dict = revert_weight_conversion(model, state_dict)
            self.logger.debug(f"Reverted to HF hub format in {time.perf_counter() - start_time:.2f} seconds")
"""
    new = """        else:
            # For regular transformers models, revert internal format to original HF hub format
            try:
                from transformers.core_model_loading import revert_weight_conversion
            except ImportError:
                revert_weight_conversion = None

            if revert_weight_conversion is None:
                self.logger.warning(
                    "transformers.core_model_loading.revert_weight_conversion is unavailable; "
                    "saving the trainer state_dict without that conversion"
                )
            else:
                self.logger.debug("Reverting transformers internal format to HF hub format for weight checkpoint")
                start_time = time.perf_counter()
                state_dict = revert_weight_conversion(model, state_dict)
                self.logger.debug(f"Reverted to HF hub format in {time.perf_counter() - start_time:.2f} seconds")
"""
    if old in text:
        text = text.replace(old, new, 1)
        path.write_text(text)


def patch_orchestrator_utils_py(path: Path) -> None:
    text = path.read_text()
    if "payload.get(\"prompt_logprobs\")" in text:
        return
    if TEACHER_LOGPROB_PATCH_OLD not in text:
        raise RuntimeError("Could not find orchestrator imports block to patch")
    if TEACHER_LOGPROB_BLOCK_OLD not in text:
        raise RuntimeError("Could not find teacher logprob block to patch")
    text = text.replace(TEACHER_LOGPROB_PATCH_OLD, TEACHER_LOGPROB_PATCH_NEW, 1)
    text = text.replace(TEACHER_LOGPROB_BLOCK_OLD, TEACHER_LOGPROB_BLOCK_NEW, 1)
    path.write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path, help="Path to PRIME-RL repo root or installed prime_rl package dir")
    args = parser.parse_args()

    target = args.target
    candidates = [
        (
            target / "trainer" / "model.py",
            target / "trainer" / "ckpt.py",
            target / "orchestrator" / "utils.py",
        ),
        (
            target / "src" / "prime_rl" / "trainer" / "model.py",
            target / "src" / "prime_rl" / "trainer" / "ckpt.py",
            target / "src" / "prime_rl" / "orchestrator" / "utils.py",
        ),
    ]
    for model_py, ckpt_py, orchestrator_utils_py in candidates:
        if model_py.exists() and ckpt_py.exists() and orchestrator_utils_py.exists():
            break
    else:
        raise FileNotFoundError(f"Could not find PRIME-RL trainer files under {target}")

    patch_model_py(model_py)
    patch_ckpt_py(ckpt_py)
    patch_orchestrator_utils_py(orchestrator_utils_py)


if __name__ == "__main__":
    main()
