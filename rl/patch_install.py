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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("site_packages", type=Path, help="Path to site-packages/prime_rl")
    args = parser.parse_args()

    model_py = args.site_packages / "trainer" / "model.py"
    ckpt_py = args.site_packages / "trainer" / "ckpt.py"
    patch_model_py(model_py)
    patch_ckpt_py(ckpt_py)


if __name__ == "__main__":
    main()
