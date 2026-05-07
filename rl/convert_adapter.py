#!/usr/bin/env python3
"""
Convert a PRIME-RL LoRA broadcast/checkpoint adapter into a PEFT-compatible
adapter directory.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from safetensors.torch import load_file, save_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("src", type=Path, help="Source PRIME-RL adapter directory.")
    parser.add_argument("dst", type=Path, help="Destination PEFT adapter directory.")
    return parser.parse_args()


def convert_key(key: str) -> str:
    if key.startswith("base_model.model."):
        return key
    return f"base_model.model.{key}"


def main() -> None:
    args = parse_args()
    args.dst.mkdir(parents=True, exist_ok=True)

    src_weights = args.src / "adapter_model.safetensors"
    src_config = args.src / "adapter_config.json"

    state = load_file(src_weights)
    converted = {convert_key(key): value for key, value in state.items()}
    save_file(converted, str(args.dst / "adapter_model.safetensors"))

    config = json.loads(src_config.read_text())
    args.dst.joinpath("adapter_config.json").write_text(json.dumps(config, indent=2) + "\n")


if __name__ == "__main__":
    main()
