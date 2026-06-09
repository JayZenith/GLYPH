#!/usr/bin/env python3
"""Export a PRIME-RL broadcast LoRA checkpoint as a standard PEFT adapter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from safetensors.torch import load_file, save_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--adapter-dir",
        required=True,
        help="PRIME-RL broadcast step directory containing adapter_config.json and adapter_model.safetensors.",
    )
    parser.add_argument("--base-model", required=True, help="Base model repo/path for PEFT adapter_config.json.")
    parser.add_argument("--output", required=True, help="Output directory for the PEFT adapter.")
    return parser.parse_args()


def load_config(adapter_dir: Path) -> dict[str, Any]:
    path = adapter_dir / "adapter_config.json"
    if not path.exists():
        raise FileNotFoundError(f"missing adapter config: {path}")
    return json.loads(path.read_text())


def main() -> int:
    args = parse_args()
    adapter_dir = Path(args.adapter_dir)
    output = Path(args.output)

    weights_path = adapter_dir / "adapter_model.safetensors"
    if not weights_path.exists():
        raise FileNotFoundError(f"missing adapter weights: {weights_path}")

    cfg = load_config(adapter_dir)
    cfg = dict(cfg)
    cfg["base_model_name_or_path"] = args.base_model
    cfg.setdefault("inference_mode", True)
    cfg.setdefault("revision", None)

    state = load_file(str(weights_path), device="cpu")
    converted = {}
    for key, value in state.items():
        if key.startswith("base_model.model."):
            converted[key] = value
        else:
            converted[f"base_model.model.{key}"] = value

    lora_a = sum(1 for key in converted if key.endswith(".lora_A.weight"))
    lora_b = sum(1 for key in converted if key.endswith(".lora_B.weight"))
    if lora_a == 0 or lora_a != lora_b:
        raise RuntimeError(f"unsafe adapter conversion: lora_A={lora_a}, lora_B={lora_b}")

    output.mkdir(parents=True, exist_ok=True)
    (output / "adapter_config.json").write_text(json.dumps(cfg, indent=2) + "\n")
    save_file(converted, str(output / "adapter_model.safetensors"))
    (output / "prime_lora_adapter_export.json").write_text(
        json.dumps(
            {
                "base_model": args.base_model,
                "adapter_dir": str(adapter_dir),
                "rank": cfg.get("r"),
                "alpha": cfg.get("lora_alpha"),
                "lora_a": lora_a,
                "lora_b": lora_b,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Exported PEFT adapter with {lora_a} LoRA pairs to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
