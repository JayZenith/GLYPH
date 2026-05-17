#!/usr/bin/env python3
"""
Patch an installed PRIME-RL checkout to bootstrap trainer LoRA weights from a
PEFT adapter via `PRIME_RL_INIT_ADAPTER=/path/to/adapter`, and to support
full-weight inference snapshots when the adapter contains `modules_to_save`
(notably `lm_head`), which current vLLM LoRA serving does not support.
"""

from __future__ import annotations

import argparse
from pathlib import Path


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

MODEL_HELPER_ANCHOR = "\n\ndef _patch_qwen3_5_moe_conversion_mapping():\n"
MODEL_HELPER_BLOCK = '''

def _maybe_load_initial_lora_adapter(model: nn.Module) -> None:
    """Load LoRA + modules_to_save weights from PRIME_RL_INIT_ADAPTER if set."""
    adapter_dir = os.environ.get("PRIME_RL_INIT_ADAPTER")
    if not adapter_dir:
        return

    adapter_path = Path(adapter_dir)
    if not adapter_path.exists():
        raise FileNotFoundError(f"PRIME_RL_INIT_ADAPTER does not exist: {adapter_path}")

    weights_path = None
    for candidate in ("adapter_model.safetensors", "adapter_model.bin"):
        path = adapter_path / candidate
        if path.exists():
            weights_path = path
            break
    if weights_path is None:
        raise FileNotFoundError(f"No adapter weights found under {adapter_path}")

    if weights_path.suffix == ".safetensors":
        from safetensors.torch import load_file

        state_dict = load_file(str(weights_path))
    else:
        state_dict = torch.load(weights_path, map_location="cpu")

    remapped_state_dict = {}
    for key, value in state_dict.items():
        new_key = key
        if new_key.startswith("base_model.model."):
            new_key = new_key[len("base_model.model."):]
        new_key = new_key.replace(".modules_to_save.default", "")
        remapped_state_dict[new_key] = value

    incompatible = model.load_state_dict(remapped_state_dict, strict=False)
    logger = get_logger()
    logger.info(
        "Initialized trainer LoRA weights from %s (%d tensors loaded)",
        adapter_path,
        len(remapped_state_dict),
    )
    if getattr(incompatible, "unexpected_keys", None):
        logger.warning("Unexpected adapter keys during bootstrap: %s", incompatible.unexpected_keys)
'''

SCHEDULER_IMPORT_OLD = """import asyncio
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
"""

SCHEDULER_IMPORT_NEW = """import asyncio
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
"""

SCHEDULER_INIT_OLD = """        self.enable_policy_updates = enable_policy_updates
        self.lora_name = lora_name
        self.model_name = self.config.model.name
        self.json_logging = config.log.json_logging
"""

SCHEDULER_INIT_NEW = """        self.enable_policy_updates = enable_policy_updates
        self.lora_name = lora_name
        self.inference_uses_full_weights = os.environ.get("PRIME_RL_INFERENCE_FULL_WEIGHTS", "").lower() in {
            "1",
            "true",
            "yes",
        }
        self.model_name = self.config.model.name
        self.json_logging = config.log.json_logging
"""

SCHEDULER_UPDATE_OLD = """        update_weights_start_time = time.perf_counter()
        weights_path = get_step_path(get_broadcast_dir(self.config.output_dir), next_ckpt_step)
        await self.inference_pool.update_weights(weights_path, lora_name=self.lora_name, step=next_ckpt_step)
        self.update_weights_time = time.perf_counter() - update_weights_start_time
        self.logger.debug(f"Updated weights to step {next_ckpt_step} in {self.update_weights_time:.2f}s")

        self.ckpt_step = next_ckpt_step
        if self.lora_name is not None:
            self.model_name = self.lora_name
            self.inference_pool.update_model_name(self.model_name)
"""

SCHEDULER_UPDATE_NEW = """        update_weights_start_time = time.perf_counter()
        weights_path = get_step_path(get_broadcast_dir(self.config.output_dir), next_ckpt_step)
        inference_lora_name = None if self.inference_uses_full_weights else self.lora_name
        await self.inference_pool.update_weights(weights_path, lora_name=inference_lora_name, step=next_ckpt_step)
        self.update_weights_time = time.perf_counter() - update_weights_start_time
        self.logger.debug(f"Updated weights to step {next_ckpt_step} in {self.update_weights_time:.2f}s")

        self.ckpt_step = next_ckpt_step
        if self.lora_name is not None and not self.inference_uses_full_weights:
            self.model_name = self.lora_name
            self.inference_pool.update_model_name(self.model_name)
"""

ENTRYPOINTS_IMPORT_ANCHOR = "TEACHER_INFERENCE_TOML = \"teacher_inference.toml\"\n"
ENTRYPOINTS_IMPORT_BLOCK = """

FORWARDED_PRIME_RL_ENV_KEYS = (
    "PRIME_RL_INIT_ADAPTER",
    "PRIME_RL_INFERENCE_FULL_WEIGHTS",
)


def _with_forwarded_prime_rl_env(env: dict[str, str]) -> dict[str, str]:
    merged = dict(env)
    for key in FORWARDED_PRIME_RL_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            merged[key] = value
    return merged
"""

ENTRYPOINTS_INFERENCE_ENV_OLD = """                    env={
                        **os.environ,
                        "CUDA_VISIBLE_DEVICES": ",".join(map(str, infer_gpu_ids)),
                    },
"""

ENTRYPOINTS_INFERENCE_ENV_NEW = """                    env=_with_forwarded_prime_rl_env({
                        **os.environ,
                        "CUDA_VISIBLE_DEVICES": ",".join(map(str, infer_gpu_ids)),
                    }),
"""

ENTRYPOINTS_TEACHER_ENV_OLD = """                    env={
                        **os.environ,
                        "CUDA_VISIBLE_DEVICES": ",".join(map(str, teacher_gpu_ids)),
                    },
"""

ENTRYPOINTS_TEACHER_ENV_NEW = """                    env=_with_forwarded_prime_rl_env({
                        **os.environ,
                        "CUDA_VISIBLE_DEVICES": ",".join(map(str, teacher_gpu_ids)),
                    }),
"""

ENTRYPOINTS_ORCH_ENV_OLD = """                env={
                    **os.environ,
                    **wandb_shared_env,
                    "WANDB_SHARED_LABEL": "orchestrator",
                },
"""

ENTRYPOINTS_ORCH_ENV_NEW = """                env=_with_forwarded_prime_rl_env({
                    **os.environ,
                    **wandb_shared_env,
                    "WANDB_SHARED_LABEL": "orchestrator",
                }),
"""

ENTRYPOINTS_TRAINER_ENV_OLD = """                env={
                    **os.environ,
                    **wandb_shared_env,
                    "WANDB_SHARED_LABEL": "trainer",
                    "CUDA_VISIBLE_DEVICES": ",".join(map(str, trainer_gpu_ids)),
                },
"""

ENTRYPOINTS_TRAINER_ENV_NEW = """                env=_with_forwarded_prime_rl_env({
                    **os.environ,
                    **wandb_shared_env,
                    "WANDB_SHARED_LABEL": "trainer",
                    "CUDA_VISIBLE_DEVICES": ",".join(map(str, trainer_gpu_ids)),
                }),
"""

ORCHESTRATOR_RESUME_OLD = """            weights_path = get_weight_dir(
                config.output_dir, scheduler.ckpt_step, check_exists=check_exists, wait_timeout=wait_timeout
            )
            lora_name = config.model.lora.name if config.model.lora else None
            await inference_pool.update_weights(weights_path, lora_name=lora_name, step=scheduler.ckpt_step)
    else:
        logger.info("Training from scratch")
"""

ORCHESTRATOR_RESUME_NEW = """            weights_path = get_weight_dir(
                config.output_dir, scheduler.ckpt_step, check_exists=check_exists, wait_timeout=wait_timeout
            )
            use_full_inference_weights = os.environ.get("PRIME_RL_INFERENCE_FULL_WEIGHTS", "").lower() in {
                "1",
                "true",
                "yes",
            }
            lora_name = None if use_full_inference_weights else (config.model.lora.name if config.model.lora else None)
            await inference_pool.update_weights(weights_path, lora_name=lora_name, step=scheduler.ckpt_step)
    else:
        logger.info("Training from scratch")
"""

FILESYSTEM_IMPORT_OLD = """import shutil
import time
from pathlib import Path
from typing import Literal

import torch.nn as nn
from torch.distributed.tensor import DTensor

from prime_rl.configs.trainer import FileSystemWeightBroadcastConfig, LoRAConfig
from prime_rl.trainer.lora import save_lora_config
"""

FILESYSTEM_IMPORT_NEW = """import os
import shutil
import time
from pathlib import Path
from typing import Literal

import torch
import torch.nn as nn
from torch.distributed.tensor import DTensor

from prime_rl.configs.trainer import FileSystemWeightBroadcastConfig, LoRAConfig
from prime_rl.trainer.lora import save_lora_config, strip_lora_from_state_dict
"""

FILESYSTEM_HELPER_ANCHOR = "\n\nclass FileSystemWeightBroadcast(WeightBroadcast):\n"
FILESYSTEM_HELPER_BLOCK = """

def _use_full_inference_weights() -> bool:
    return os.environ.get("PRIME_RL_INFERENCE_FULL_WEIGHTS", "").lower() in {"1", "true", "yes"}


def _merge_adapter_into_base_state_dict(
    base_state_dict: dict[str, torch.Tensor],
    adapter_state_dict: dict[str, torch.Tensor],
    *,
    alpha: float,
    rank: int,
) -> dict[str, torch.Tensor]:
    merged_state_dict = dict(base_state_dict)
    lora_a: dict[str, torch.Tensor] = {}
    lora_b: dict[str, torch.Tensor] = {}
    scaling = alpha / rank

    for key, value in adapter_state_dict.items():
        if isinstance(value, DTensor):
            value = value.full_tensor()
        tensor = value.to("cpu", non_blocking=False)
        if key.endswith(".lora_A.weight"):
            lora_a[key[: -len(".lora_A.weight")]] = tensor
        elif key.endswith(".lora_B.weight"):
            lora_b[key[: -len(".lora_B.weight")]] = tensor
        else:
            merged_state_dict[key] = tensor

    for prefix, a_tensor in lora_a.items():
        b_tensor = lora_b.get(prefix)
        if b_tensor is None:
            continue
        base_key = f"{prefix}.weight"
        base_tensor = merged_state_dict.get(base_key)
        if base_tensor is None:
            continue
        delta = torch.matmul(b_tensor.to(torch.float32), a_tensor.to(torch.float32))
        merged_state_dict[base_key] = (base_tensor.to(torch.float32) + scaling * delta).to(base_tensor.dtype)

    return merged_state_dict
"""

FILESYSTEM_BODY_OLD = """        self.logger.debug("Starting broadcasting weights to inference engine via shared filesystem")
        start_time = time.perf_counter()
        adapter_only = self.lora_config is not None

        if not adapter_only:
            state_dict = gather_weights_on_master(model, is_master=self.world.is_master)
            if isinstance(model, PreTrainedModelPrimeRL) and model.is_prime_state_dict(state_dict):
                model.convert_to_hf(state_dict)
            else:
                # For regular transformers models, revert internal format to original HF hub format
                from transformers.core_model_loading import revert_weight_conversion

                state_dict = revert_weight_conversion(model, state_dict)
"""

FILESYSTEM_BODY_NEW = """        self.logger.debug("Starting broadcasting weights to inference engine via shared filesystem")
        start_time = time.perf_counter()
        adapter_only = self.lora_config is not None
        export_full_weights = adapter_only and _use_full_inference_weights()
        base_state_dict = None

        if export_full_weights:
            adapter_only = False

        if not adapter_only:
            state_dict = gather_weights_on_master(model, is_master=self.world.is_master)
            if isinstance(model, PreTrainedModelPrimeRL) and model.is_prime_state_dict(state_dict):
                model.convert_to_hf(state_dict)
            else:
                # For regular transformers models, revert internal format to original HF hub format
                from transformers.core_model_loading import revert_weight_conversion

                state_dict = revert_weight_conversion(model, state_dict)
            state_dict = strip_lora_from_state_dict(state_dict)
            base_state_dict = state_dict
"""

FILESYSTEM_LOOP_OLD = """            if adapter_only:
                # For adapter-only, MultiRunManager creates state dict directly for each run
                # All ranks must participate in DTensor gathering, but only master saves
                state_dict = self.multi_run_manager.get_state_dict_for_run(idx)
                for key, value in state_dict.items():
                    if isinstance(value, DTensor):
                        value = value.full_tensor()
                    if self.world.is_master:
                        state_dict[key] = value.to("cpu", non_blocking=False)
"""

FILESYSTEM_LOOP_NEW = """            if adapter_only:
                # For adapter-only, MultiRunManager creates state dict directly for each run
                # All ranks must participate in DTensor gathering, but only master saves
                state_dict = self.multi_run_manager.get_state_dict_for_run(idx)
                for key, value in state_dict.items():
                    if isinstance(value, DTensor):
                        value = value.full_tensor()
                    if self.world.is_master:
                        state_dict[key] = value.to("cpu", non_blocking=False)
            elif export_full_weights:
                adapter_state_dict = self.multi_run_manager.get_state_dict_for_run(idx)
                state_dict = _merge_adapter_into_base_state_dict(
                    base_state_dict,
                    adapter_state_dict,
                    alpha=self.lora_config.alpha,
                    rank=self.lora_config.rank,
                )
"""

VLLM_WORKER_FILE = """from pathlib import Path
from typing import TYPE_CHECKING

from safetensors import safe_open
from torch.nn import Module
from vllm.config import set_current_vllm_config
from vllm.model_executor.model_loader import DefaultModelLoader, get_model_loader

if TYPE_CHECKING:
    from vllm.v1.worker.gpu_worker import Worker

    Worker = Worker
else:
    Worker = object


class FileSystemWeightUpdateWorker(Worker):
    \"\"\"vLLM worker extension for updating weights in-place using shared filesystem.\"\"\"

    def init_broadcaster(self) -> None:
        ...

    def liveness_probe(self) -> None:
        return None

    @staticmethod
    def _raw_weights(safetensors_path: Path):
        with safe_open(str(safetensors_path), framework=\"pt\", device=\"cpu\") as f:
            for key in f.keys():
                yield key, f.get_tensor(key)

    def update_weights_from_path(self, weight_path: str) -> None:
        model_runner = self.model_runner
        model = model_runner.model
        assert isinstance(model, Module)

        weight_dir = Path(weight_path)
        safetensors_path = weight_dir / \"model.safetensors\"
        if safetensors_path.exists():
            weights_iterator = self._raw_weights(safetensors_path)
        else:
            model_loader = get_model_loader(self.load_config)
            assert isinstance(model_loader, DefaultModelLoader)
            local_source = DefaultModelLoader.Source(
                weight_path,
                revision=None,
                prefix=\"\",
                fall_back_to_pt=getattr(model, \"fall_back_to_pt_during_load\", True),
                allow_patterns_overrides=getattr(model, \"allow_patterns_overrides\", None),
            )
            weights_iterator = model_loader._get_weights_iterator(local_source)
        device = next(model.parameters()).device
        with set_current_vllm_config(self.vllm_config), device:
            model.load_weights(weights_iterator)  # type: ignore[arg-type]
"""

QWEN3_LOAD_WEIGHTS_OLD = """    def load_weights(self, weights: Iterable[tuple[str, torch.Tensor]]) -> set[str]:
        loader = AutoWeightsLoader(
            self,
            skip_prefixes=(["lm_head."] if self.config.tie_word_embeddings else None),
        )
        return loader.load_weights(weights)
"""

QWEN3_LOAD_WEIGHTS_NEW = """    def load_weights(self, weights: Iterable[tuple[str, torch.Tensor]]) -> set[str]:
        stacked_params_mapping = [
            ("qkv_proj", "q_proj", "q"),
            ("qkv_proj", "k_proj", "k"),
            ("qkv_proj", "v_proj", "v"),
            ("gate_up_proj", "gate_proj", 0),
            ("gate_up_proj", "up_proj", 1),
        ]
        params_dict = dict(self.named_parameters(remove_duplicate=False))
        loaded_params: set[str] = set()
        for name, loaded_weight in weights:
            if "rotary_emb.inv_freq" in name:
                continue
            if self.quant_config is not None and (
                scale_name := self.quant_config.get_cache_scale(name)
            ):
                param = params_dict[scale_name]
                weight_loader = getattr(param, "weight_loader", default_weight_loader)
                loaded_weight = loaded_weight if loaded_weight.dim() == 0 else loaded_weight[0]
                weight_loader(param, loaded_weight)
                loaded_params.add(scale_name)
                continue
            for param_name, weight_name, shard_id in stacked_params_mapping:
                if weight_name not in name:
                    continue
                name = name.replace(weight_name, param_name)
                if name.endswith(".bias") and name not in params_dict:
                    continue
                if is_pp_missing_parameter(name, self):
                    continue
                if name.endswith("scale"):
                    name = maybe_remap_kv_scale_name(name, params_dict)
                    if name is None:
                        continue
                if name not in params_dict:
                    continue
                param = params_dict[name]
                weight_loader = getattr(param, "weight_loader", default_weight_loader)
                if weight_loader == default_weight_loader:
                    weight_loader(param, loaded_weight)
                else:
                    weight_loader(param, loaded_weight, shard_id)
                break
            else:
                if name.endswith(".bias") and name not in params_dict:
                    continue
                name = maybe_remap_kv_scale_name(name, params_dict)
                if name is None:
                    continue
                if is_pp_missing_parameter(name, self):
                    continue
                if name not in params_dict:
                    continue
                param = params_dict[name]
                weight_loader = getattr(param, "weight_loader", default_weight_loader)
                weight_loader(param, loaded_weight)
            loaded_params.add(name)
        return loaded_params
"""

QWEN3_WEIGHT_UTILS_IMPORT_ANCHOR = "from vllm.sequence import IntermediateTensors\n"
QWEN3_WEIGHT_UTILS_IMPORT_BLOCK = """from vllm.model_executor.model_loader.weight_utils import (
    default_weight_loader,
    maybe_remap_kv_scale_name,
)
"""

QWEN3_UTILS_IMPORT_SINGLE_OLD = (
    "from .utils import AutoWeightsLoader, PPMissingLayer, extract_layer_index, maybe_prefix\n"
)
QWEN3_UTILS_IMPORT_SINGLE_NEW = (
    "from .utils import AutoWeightsLoader, PPMissingLayer, extract_layer_index, is_pp_missing_parameter, maybe_prefix\n"
)
QWEN3_UTILS_IMPORT_MULTI_OLD = """from .utils import (
    AutoWeightsLoader,
    PPMissingLayer,
    extract_layer_index,
    maybe_prefix,
)
"""
QWEN3_UTILS_IMPORT_MULTI_NEW = """from .utils import (
    AutoWeightsLoader,
    PPMissingLayer,
    extract_layer_index,
    is_pp_missing_parameter,
    maybe_prefix,
)
"""



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
    if (
        "payload.get(\"prompt_logprobs\")" in text
        or "GenerateResponse.model_validate_json(http_response.content)" in text
        or 'cast_to=httpx.Response' in text
    ):
        return
    if TEACHER_LOGPROB_PATCH_OLD not in text:
        raise RuntimeError("Could not find orchestrator imports block to patch")
    if TEACHER_LOGPROB_BLOCK_OLD not in text:
        raise RuntimeError("Could not find teacher logprob block to patch")
    text = text.replace(TEACHER_LOGPROB_PATCH_OLD, TEACHER_LOGPROB_PATCH_NEW, 1)
    text = text.replace(TEACHER_LOGPROB_BLOCK_OLD, TEACHER_LOGPROB_BLOCK_NEW, 1)
    path.write_text(text)


def patch_model_py(path: Path) -> None:
    text = path.read_text()
    changed = False

    if "_maybe_load_initial_lora_adapter(model)" not in text:
        if CALL_MARKER not in text:
            raise RuntimeError("Could not find apply_lora_to_model call in trainer/model.py")
        text = text.replace(CALL_MARKER, CALL_INSERT, 1)
        changed = True

    if "def _maybe_load_initial_lora_adapter(model: nn.Module)" not in text:
        if MODEL_HELPER_ANCHOR not in text:
            raise RuntimeError("Could not find insertion anchor for adapter bootstrap helper in trainer/model.py")
        text = text.replace(MODEL_HELPER_ANCHOR, MODEL_HELPER_BLOCK + MODEL_HELPER_ANCHOR, 1)
        changed = True

    if changed:
        path.write_text(text)


def patch_scheduler_py(path: Path) -> None:
    text = path.read_text()
    changed = False
    if "self.inference_uses_full_weights" not in text:
        if SCHEDULER_IMPORT_OLD in text:
            text = text.replace(SCHEDULER_IMPORT_OLD, SCHEDULER_IMPORT_NEW, 1)
            changed = True
        if SCHEDULER_INIT_OLD not in text:
            raise RuntimeError("Could not find Scheduler __init__ block to patch")
        text = text.replace(SCHEDULER_INIT_OLD, SCHEDULER_INIT_NEW, 1)
        changed = True
    if "inference_lora_name = None if self.inference_uses_full_weights else self.lora_name" not in text:
        if SCHEDULER_UPDATE_OLD not in text:
            raise RuntimeError("Could not find Scheduler update block to patch")
        text = text.replace(SCHEDULER_UPDATE_OLD, SCHEDULER_UPDATE_NEW, 1)
        changed = True
    if changed:
        path.write_text(text)


def patch_orchestrator_py(path: Path) -> None:
    text = path.read_text()
    changed = False
    if "use_full_inference_weights" not in text:
        if ORCHESTRATOR_RESUME_OLD not in text:
            raise RuntimeError("Could not find orchestrator resume/startup block to patch")
        text = text.replace(ORCHESTRATOR_RESUME_OLD, ORCHESTRATOR_RESUME_NEW, 1)
        changed = True
    if changed:
        path.write_text(text)


def patch_filesystem_broadcast_py(path: Path) -> None:
    text = path.read_text()
    changed = False
    if "_use_full_inference_weights()" not in text:
        if FILESYSTEM_IMPORT_OLD not in text:
            raise RuntimeError("Could not find filesystem broadcast imports block to patch")
        text = text.replace(FILESYSTEM_IMPORT_OLD, FILESYSTEM_IMPORT_NEW, 1)
        if FILESYSTEM_HELPER_ANCHOR not in text:
            raise RuntimeError("Could not find filesystem broadcast helper anchor")
        text = text.replace(FILESYSTEM_HELPER_ANCHOR, FILESYSTEM_HELPER_BLOCK + FILESYSTEM_HELPER_ANCHOR, 1)
        changed = True
    if FILESYSTEM_BODY_OLD in text:
        text = text.replace(FILESYSTEM_BODY_OLD, FILESYSTEM_BODY_NEW, 1)
        changed = True
    if FILESYSTEM_LOOP_OLD in text:
        text = text.replace(FILESYSTEM_LOOP_OLD, FILESYSTEM_LOOP_NEW, 1)
        changed = True
    if changed:
        path.write_text(text)


def patch_entrypoints_rl_py(path: Path) -> None:
    text = path.read_text()
    changed = False
    if "FORWARDED_PRIME_RL_ENV_KEYS" not in text:
        if ENTRYPOINTS_IMPORT_ANCHOR not in text:
            raise RuntimeError("Could not find entrypoints rl import anchor")
        text = text.replace(ENTRYPOINTS_IMPORT_ANCHOR, ENTRYPOINTS_IMPORT_ANCHOR + ENTRYPOINTS_IMPORT_BLOCK, 1)
        changed = True
    replacements = [
        (ENTRYPOINTS_INFERENCE_ENV_OLD, ENTRYPOINTS_INFERENCE_ENV_NEW),
        (ENTRYPOINTS_TEACHER_ENV_OLD, ENTRYPOINTS_TEACHER_ENV_NEW),
        (ENTRYPOINTS_ORCH_ENV_OLD, ENTRYPOINTS_ORCH_ENV_NEW),
        (ENTRYPOINTS_TRAINER_ENV_OLD, ENTRYPOINTS_TRAINER_ENV_NEW),
    ]
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new, 1)
            changed = True
    if changed:
        path.write_text(text)


def patch_vllm_filesystem_worker_py(path: Path) -> None:
    text = path.read_text()
    desired = VLLM_WORKER_FILE
    if text != desired:
        path.write_text(desired)


def patch_vllm_qwen3_py(path: Path) -> None:
    text = path.read_text()
    original = text

    if "from vllm.model_executor.model_loader.weight_utils import" not in text:
        if QWEN3_WEIGHT_UTILS_IMPORT_ANCHOR not in text:
            raise RuntimeError("Could not find Qwen3 weight_utils import anchor")
        text = text.replace(
            QWEN3_WEIGHT_UTILS_IMPORT_ANCHOR,
            QWEN3_WEIGHT_UTILS_IMPORT_BLOCK + QWEN3_WEIGHT_UTILS_IMPORT_ANCHOR,
            1,
        )

    if QWEN3_UTILS_IMPORT_SINGLE_OLD in text:
        text = text.replace(QWEN3_UTILS_IMPORT_SINGLE_OLD, QWEN3_UTILS_IMPORT_SINGLE_NEW, 1)
    elif QWEN3_UTILS_IMPORT_MULTI_OLD in text:
        text = text.replace(QWEN3_UTILS_IMPORT_MULTI_OLD, QWEN3_UTILS_IMPORT_MULTI_NEW, 1)
    # else: already extended with is_pp_missing_parameter (idempotent no-op)

    if QWEN3_LOAD_WEIGHTS_NEW not in text:
        if QWEN3_LOAD_WEIGHTS_OLD not in text:
            raise RuntimeError("Could not find Qwen3 load_weights block to patch")
        text = text.replace(QWEN3_LOAD_WEIGHTS_OLD, QWEN3_LOAD_WEIGHTS_NEW, 1)

    if text != original:
        path.write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path, help="Path to PRIME-RL repo root or installed prime_rl package dir")
    args = parser.parse_args()

    target = args.target
    candidates = [
        (
            target / "entrypoints" / "rl.py",
            target / "inference" / "vllm" / "worker" / "filesystem.py",
            target / "trainer" / "model.py",
            target / "trainer" / "ckpt.py",
            target / "orchestrator" / "utils.py",
            target / "orchestrator" / "orchestrator.py",
            target / "orchestrator" / "scheduler.py",
            target / "trainer" / "rl" / "broadcast" / "filesystem.py",
        ),
        (
            target / "src" / "prime_rl" / "entrypoints" / "rl.py",
            target / "src" / "prime_rl" / "inference" / "vllm" / "worker" / "filesystem.py",
            target / "src" / "prime_rl" / "trainer" / "model.py",
            target / "src" / "prime_rl" / "trainer" / "ckpt.py",
            target / "src" / "prime_rl" / "orchestrator" / "utils.py",
            target / "src" / "prime_rl" / "orchestrator" / "orchestrator.py",
            target / "src" / "prime_rl" / "orchestrator" / "scheduler.py",
            target / "src" / "prime_rl" / "trainer" / "rl" / "broadcast" / "filesystem.py",
        ),
    ]
    matched = False
    for entrypoints_rl_py, vllm_worker_py, model_py, ckpt_py, orchestrator_utils_py, orchestrator_py, scheduler_py, filesystem_broadcast_py in candidates:
        if not (
            entrypoints_rl_py.exists()
            and vllm_worker_py.exists()
            and model_py.exists()
            and ckpt_py.exists()
            and orchestrator_utils_py.exists()
            and orchestrator_py.exists()
            and scheduler_py.exists()
            and filesystem_broadcast_py.exists()
        ):
            continue
        matched = True
        patch_entrypoints_rl_py(entrypoints_rl_py)
        patch_vllm_filesystem_worker_py(vllm_worker_py)
        patch_model_py(model_py)
        patch_ckpt_py(ckpt_py)
        patch_orchestrator_utils_py(orchestrator_utils_py)
        patch_orchestrator_py(orchestrator_py)
        patch_scheduler_py(scheduler_py)
        patch_filesystem_broadcast_py(filesystem_broadcast_py)
    if not matched:
        raise FileNotFoundError(f"Could not find PRIME-RL trainer files under {target}")

    qwen3_py = _find_vllm_qwen3_path(target)
    if qwen3_py is not None:
        patch_vllm_qwen3_py(qwen3_py)
    else:
        raise FileNotFoundError("Could not locate installed vllm/model_executor/models/qwen3.py")


def _find_vllm_qwen3_path(target: Path) -> Path | None:
    # Probe layouts (prime-rl repo root, site-packages root, site-packages/prime_rl).
    candidates = [
        target / ".venv" / "lib" / "python3.12" / "site-packages" / "vllm" / "model_executor" / "models" / "qwen3.py",
        target / "vllm" / "model_executor" / "models" / "qwen3.py",
        target.parent / "vllm" / "model_executor" / "models" / "qwen3.py",
    ]
    for path in candidates:
        if path.exists():
            return path
    try:
        import importlib.util
        spec = importlib.util.find_spec("vllm.model_executor.models.qwen3")
    except Exception:
        return None
    if spec and spec.origin:
        return Path(spec.origin)
    return None


if __name__ == "__main__":
    main()
