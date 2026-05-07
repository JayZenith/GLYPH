#!/usr/bin/env python3
"""
Launch PRIME-RL in adapter-only LoRA mode.

This keeps the base model frozen, initializes PRIME-RL's internal LoRA weights
from an existing PEFT adapter, and routes inference through the base model with
LoRA enabled.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from prime_rl.configs.rl import RLConfig
import prime_rl.entrypoints.rl as rl_mod


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch PRIME-RL from a PEFT adapter.")
    parser.add_argument("--adapter", type=Path, required=True, help="Path to the PEFT adapter directory.")
    parser.add_argument("--base-model", help="Override the base model path or HF id.")
    parser.add_argument("--data", type=Path, default=Path("traces.processed.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("outputs/prime_rl"))
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--rollouts-per-example", type=int, default=4)
    parser.add_argument("--seq-len", type=int, default=1024)
    parser.add_argument("--max-model-len", type=int, default=1024)
    parser.add_argument("--max-completion-tokens", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=1e-6)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.2)
    parser.add_argument("--max-samples", type=int, default=512)
    parser.add_argument("--max-trace-chars", type=int, default=50000)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--share-single-gpu", action="store_true")
    return parser.parse_args()


def load_adapter_config(adapter_dir: Path) -> dict:
    path = adapter_dir / "adapter_config.json"
    with path.open() as f:
        return json.load(f)


def build_config(args: argparse.Namespace, adapter_cfg: dict) -> dict:
    base_model = args.base_model or adapter_cfg["base_model_name_or_path"]
    rank = int(adapter_cfg["r"])
    alpha = float(adapter_cfg["lora_alpha"])
    dropout = float(adapter_cfg.get("lora_dropout", 0.0))
    target_modules = list(adapter_cfg["target_modules"])
    adapter_name = f"{args.adapter.name}-r{rank}-a{int(alpha)}"

    return {
        "trainer": {
            "model": {
                "name": base_model,
                "seq_len": args.seq_len,
                "attn": "sdpa",
                "lora": {
                    "rank": rank,
                    "alpha": alpha,
                    "dropout": dropout,
                    "target_modules": target_modules,
                },
            },
            "optim": {
                "type": "adamw",
                "lr": args.learning_rate,
                "weight_decay": args.weight_decay,
            },
            "ckpt": {"interval": 20},
            "max_steps": args.max_steps,
        },
        "orchestrator": {
            "model": {
                "name": base_model,
                "lora": {
                    "name": adapter_name,
                    "rank": rank,
                    "alpha": alpha,
                },
            },
            "train": {
                "sampling": {
                    "temperature": args.temperature,
                    "max_completion_tokens": args.max_completion_tokens,
                },
                "env": [
                    {
                        "id": "task-trace",
                        "args": {
                            "data_path": str(args.data),
                            "max_samples": args.max_samples,
                            "max_trace_chars": args.max_trace_chars,
                        },
                    }
                ],
            },
            "batch_size": args.batch_size,
            "rollouts_per_example": args.rollouts_per_example,
            "seq_len": args.seq_len,
            "max_steps": args.max_steps,
            "ckpt": {"interval": 20},
        },
        "inference": {
            "model": {
                "name": base_model,
                "max_model_len": args.max_model_len,
            },
            "server": {"port": args.port},
            "gpu_memory_utilization": args.gpu_memory_utilization,
        },
        "output_dir": str(args.output),
        "wandb": {"offline": True, "shared": False},
        "deployment": {
            "type": "single_node",
            "gpus_per_node": 2 if args.share_single_gpu else 1,
            "num_train_gpus": 1,
            "num_infer_gpus": 1,
        },
    }


def main() -> None:
    args = parse_args()
    adapter_cfg = load_adapter_config(args.adapter)

    os.environ["PRIME_RL_INIT_ADAPTER"] = str(args.adapter.resolve())
    pythonpath = os.environ.get("PYTHONPATH")
    cwd = str(Path.cwd())
    os.environ["PYTHONPATH"] = cwd if not pythonpath else f"{cwd}:{pythonpath}"

    if args.share_single_gpu:
        rl_mod.get_physical_gpu_ids = lambda: [0, 0]

    config = RLConfig.model_validate(build_config(args, adapter_cfg))
    rl_mod.rl(config)


if __name__ == "__main__":
    main()
