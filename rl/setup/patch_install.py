#!/usr/bin/env python3
"""Patch an installed PRIME-RL checkout with the fixes GLYPH needs."""

from __future__ import annotations

import argparse
import re
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

    def _extract_token_logprobs(token_ids: list[int], prompt_logprobs: list[Any] | None) -> list[float]:
        values: list[float] = []
        for idx, entry in enumerate(prompt_logprobs or []):
            if entry is None:
                values.append(0.0)
                continue
            if isinstance(entry, (int, float)):
                values.append(float(entry))
                continue
            token_id = token_ids[idx] if idx < len(token_ids) else None
            token_entry = entry.get(str(token_id), entry.get(token_id)) if isinstance(entry, dict) else None
            if isinstance(token_entry, dict):
                values.append(float(token_entry.get(\"logprob\", 0.0)))
            elif token_entry is not None and hasattr(token_entry, \"logprob\"):
                values.append(float(token_entry.logprob))
            else:
                values.append(0.0)
        return values

    async def _compute_single(client_config: vf.ClientConfig, sample: TrainingSample) -> list[float]:
        token_ids = sample.prompt_ids + sample.completion_ids
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
                \"/inference/v1/generate\",
                json={
                    \"request_id\": f\"teacher-{id(sample)}\",
                    \"model\": model_name,
                    \"token_ids\": token_ids,
                    \"sampling_params\": {
                        \"max_tokens\": 1,
                        \"temperature\": 1.0,
                        \"top_p\": 1.0,
                        \"prompt_logprobs\": 1,
                    },
                },
            )
            response.raise_for_status()
            payload = response.json()

        return _extract_token_logprobs(token_ids, payload.get(\"prompt_logprobs\"))

    return await asyncio.gather(*[_compute_single(client, sample) for client, sample in zip(cycle(clients), samples)])
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

QWEN3_LOAD_WEIGHTS_OLD = """    def load_weights(self, weights: Iterable[tuple[str, torch.Tensor]]) -> set[str]:
        loader = AutoWeightsLoader(
            self,
            skip_prefixes=([\"lm_head.\"] if self.config.tie_word_embeddings else None),
        )
        return loader.load_weights(weights)
"""

QWEN3_LOAD_WEIGHTS_NEW = """    def load_weights(self, weights: Iterable[tuple[str, torch.Tensor]]) -> set[str]:
        stacked_params_mapping = [
            (\"qkv_proj\", \"q_proj\", \"q\"),
            (\"qkv_proj\", \"k_proj\", \"k\"),
            (\"qkv_proj\", \"v_proj\", \"v\"),
            (\"gate_up_proj\", \"gate_proj\", 0),
            (\"gate_up_proj\", \"up_proj\", 1),
        ]
        params_dict = dict(self.named_parameters(remove_duplicate=False))
        loaded_params: set[str] = set()
        for name, loaded_weight in weights:
            if \"rotary_emb.inv_freq\" in name:
                continue
            if self.quant_config is not None and (
                scale_name := self.quant_config.get_cache_scale(name)
            ):
                param = params_dict[scale_name]
                weight_loader = getattr(param, \"weight_loader\", default_weight_loader)
                loaded_weight = loaded_weight if loaded_weight.dim() == 0 else loaded_weight[0]
                weight_loader(param, loaded_weight)
                loaded_params.add(scale_name)
                continue
            for param_name, weight_name, shard_id in stacked_params_mapping:
                if weight_name not in name:
                    continue
                name = name.replace(weight_name, param_name)
                if name.endswith(\".bias\") and name not in params_dict:
                    continue
                if is_pp_missing_parameter(name, self):
                    continue
                if name.endswith(\"scale\"):
                    name = maybe_remap_kv_scale_name(name, params_dict)
                    if name is None:
                        continue
                if name not in params_dict:
                    continue
                param = params_dict[name]
                weight_loader = getattr(param, \"weight_loader\", default_weight_loader)
                if weight_loader == default_weight_loader:
                    weight_loader(param, loaded_weight)
                else:
                    weight_loader(param, loaded_weight, shard_id)
                break
            else:
                if name.endswith(\".bias\") and name not in params_dict:
                    continue
                name = maybe_remap_kv_scale_name(name, params_dict)
                if name is None:
                    continue
                if is_pp_missing_parameter(name, self):
                    continue
                if name not in params_dict:
                    continue
                param = params_dict[name]
                weight_loader = getattr(param, \"weight_loader\", default_weight_loader)
                weight_loader(param, loaded_weight)
            loaded_params.add(name)
        return loaded_params
"""


def patch_ckpt_py(path: Path) -> None:
    text = path.read_text()
    old = """        else:
            # For regular transformers models, revert internal format to original HF hub format
            from transformers.core_model_loading import revert_weight_conversion

            self.logger.debug(\"Reverting transformers internal format to HF hub format for weight checkpoint\")
            start_time = time.perf_counter()
            state_dict = revert_weight_conversion(model, state_dict)
            self.logger.debug(f\"Reverted to HF hub format in {time.perf_counter() - start_time:.2f} seconds\")
"""
    new = """        else:
            # For regular transformers models, revert internal format to original HF hub format
            try:
                from transformers.core_model_loading import revert_weight_conversion
            except ImportError:
                revert_weight_conversion = None

            if revert_weight_conversion is None:
                self.logger.warning(
                    \"transformers.core_model_loading.revert_weight_conversion is unavailable; \"
                    \"saving the trainer state_dict without that conversion\"
                )
            else:
                self.logger.debug(\"Reverting transformers internal format to HF hub format for weight checkpoint\")
                start_time = time.perf_counter()
                state_dict = revert_weight_conversion(model, state_dict)
                self.logger.debug(f\"Reverted to HF hub format in {time.perf_counter() - start_time:.2f} seconds\")
"""
    if old in text:
        path.write_text(text.replace(old, new, 1))


def patch_orchestrator_utils_py(path: Path) -> None:
    text = path.read_text()

    if "import os\n" not in text:
        text = text.replace("import asyncio\n", "import asyncio\nimport os\n", 1)
    if "import httpx\n" not in text:
        anchor = "import pandas as pd\n"
        if anchor in text:
            text = text.replace(anchor, "import httpx\n" + anchor, 1)
        else:
            text = "import httpx\n" + text

    if TEACHER_LOGPROB_BLOCK_OLD in text:
        text = text.replace(TEACHER_LOGPROB_BLOCK_OLD, TEACHER_LOGPROB_BLOCK_NEW, 1)
        path.write_text(text)
        return

    match = re.search(
        r"async def compute_teacher_logprobs\([\s\S]*?\n(?=def |async def |class |\Z)",
        text,
    )
    if match is None:
        print(f"[patch_install] skipping orchestrator utils patch; compute_teacher_logprobs not found in {path}")
        path.write_text(text)
        return
    text = text[: match.start()] + TEACHER_LOGPROB_BLOCK_NEW + "\n" + text[match.end() :]
    path.write_text(text)


def patch_vllm_filesystem_worker_py(path: Path) -> None:
    if path.read_text() != VLLM_WORKER_FILE:
        path.write_text(VLLM_WORKER_FILE)


def patch_vllm_qwen3_py(path: Path) -> None:
    text = path.read_text()
    original = text

    if "from vllm.model_executor.model_loader.weight_utils import" not in text:
        if QWEN3_WEIGHT_UTILS_IMPORT_ANCHOR not in text:
            raise RuntimeError("Could not find Qwen3 weight utils import anchor")
        text = text.replace(
            QWEN3_WEIGHT_UTILS_IMPORT_ANCHOR,
            QWEN3_WEIGHT_UTILS_IMPORT_BLOCK + QWEN3_WEIGHT_UTILS_IMPORT_ANCHOR,
            1,
        )

    if QWEN3_UTILS_IMPORT_SINGLE_OLD in text:
        text = text.replace(QWEN3_UTILS_IMPORT_SINGLE_OLD, QWEN3_UTILS_IMPORT_SINGLE_NEW, 1)
    elif QWEN3_UTILS_IMPORT_MULTI_OLD in text:
        text = text.replace(QWEN3_UTILS_IMPORT_MULTI_OLD, QWEN3_UTILS_IMPORT_MULTI_NEW, 1)

    if QWEN3_LOAD_WEIGHTS_NEW not in text:
        if QWEN3_LOAD_WEIGHTS_OLD not in text:
            raise RuntimeError("Could not find Qwen3 load_weights block to patch")
        text = text.replace(QWEN3_LOAD_WEIGHTS_OLD, QWEN3_LOAD_WEIGHTS_NEW, 1)

    if text != original:
        path.write_text(text)


def _find_vllm_qwen3_path(target: Path) -> Path | None:
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path, help="Path to PRIME-RL repo root or installed prime_rl package dir")
    args = parser.parse_args()

    target = args.target
    candidates = [
        (
            target / "trainer" / "ckpt.py",
            target / "orchestrator" / "utils.py",
            target / "inference" / "vllm" / "worker" / "filesystem.py",
        ),
        (
            target / "src" / "prime_rl" / "trainer" / "ckpt.py",
            target / "src" / "prime_rl" / "orchestrator" / "utils.py",
            target / "src" / "prime_rl" / "inference" / "vllm" / "worker" / "filesystem.py",
        ),
    ]

    matched = False
    for ckpt_py, orchestrator_utils_py, vllm_worker_py in candidates:
        if not (ckpt_py.exists() and orchestrator_utils_py.exists() and vllm_worker_py.exists()):
            continue
        matched = True
        patch_ckpt_py(ckpt_py)
        patch_orchestrator_utils_py(orchestrator_utils_py)
        patch_vllm_filesystem_worker_py(vllm_worker_py)

    if not matched:
        raise FileNotFoundError(f"Could not find PRIME-RL files under {target}")

    qwen3_py = _find_vllm_qwen3_path(target)
    if qwen3_py is None:
        raise FileNotFoundError("Could not locate installed vllm/model_executor/models/qwen3.py")
    patch_vllm_qwen3_py(qwen3_py)


if __name__ == "__main__":
    main()
