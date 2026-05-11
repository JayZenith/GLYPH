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
import sys
from pathlib import Path
from typing import Any

from huggingface_hub import snapshot_download


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch PRIME-RL from a PEFT adapter.")
    parser.add_argument(
        "--adapter",
        required=True,
        help="PEFT adapter source: local directory or HF repo id (for example JayZenith/glyph-sft-v1-adapter).",
    )
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
    parser.add_argument(
        "--reward-mode",
        default="verifier_only",
        choices=["verifier_only", "smoke_deterministic"],
        help="Reward function variant exposed by rl/task_trace.py.",
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--share-single-gpu", action="store_true")
    parser.add_argument(
        "--teacher-model",
        help="Optional teacher/reference model id or path, for example JayZenith/glyph-sft-v1.",
    )
    parser.add_argument(
        "--teacher-port",
        type=int,
        default=8100,
        help="Port for PRIME-RL teacher inference server when enabled.",
    )
    parser.add_argument(
        "--teacher-tau",
        type=float,
        default=0.0,
        help="Teacher KL weight. Set >0 to use teacher/reference logprobs in the RL loss.",
    )
    parser.add_argument(
        "--enable-teacher-inference",
        action="store_true",
        help="Start a dedicated teacher inference server for reference logprobs.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print config and exit without launching PRIME-RL.")
    parser.add_argument("--dump-config", type=Path, help="Optional path to write the resolved PRIME-RL config JSON.")
    return parser.parse_args()


def resolve_adapter_dir(adapter: str) -> Path:
    path = Path(adapter)
    if path.exists():
        return path.resolve()
    return Path(snapshot_download(repo_id=adapter, repo_type="model"))


def load_adapter_config(adapter_dir: Path) -> dict[str, Any]:
    path = adapter_dir / "adapter_config.json"
    with path.open() as f:
        return json.load(f)


def build_config(args: argparse.Namespace, adapter_cfg: dict) -> dict:
    base_model = args.base_model or adapter_cfg["base_model_name_or_path"]
    data_path = Path(args.data).resolve()
    output_dir = Path(args.output).resolve()
    rank = int(adapter_cfg["r"])
    alpha = float(adapter_cfg["lora_alpha"])
    dropout = float(adapter_cfg.get("lora_dropout", 0.0))
    target_modules = list(adapter_cfg["target_modules"])
    modules_to_save = list(adapter_cfg.get("modules_to_save") or [])
    adapter_label = Path(str(args.adapter)).name.replace("/", "__")
    adapter_name = f"{adapter_label}-r{rank}-a{int(alpha)}"

    train_gpu_slots = 1
    infer_gpu_slots = 1
    teacher_gpu_slots = 1 if args.enable_teacher_inference else 0
    total_gpu_slots = train_gpu_slots + infer_gpu_slots + teacher_gpu_slots

    config = {
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
                    "modules_to_save": modules_to_save,
                },
            },
            "optim": {
                "type": "adamw",
                "lr": args.learning_rate,
                "weight_decay": args.weight_decay,
            },
            "loss": {
                "type": "default",
                "teacher_tau": args.teacher_tau,
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
                            "data_path": str(data_path),
                            "max_samples": args.max_samples,
                            "max_trace_chars": args.max_trace_chars,
                            "reward_mode": args.reward_mode,
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
                "enforce_eager": True,
            },
            "server": {"port": args.port},
            "gpu_memory_utilization": args.gpu_memory_utilization,
        },
        "output_dir": str(output_dir),
        "wandb": {"offline": True, "shared": False},
        "deployment": {
            "type": "single_node",
            "gpus_per_node": total_gpu_slots,
            "num_train_gpus": train_gpu_slots,
            "num_infer_gpus": infer_gpu_slots,
        },
    }
    if args.enable_teacher_inference:
        teacher_model_name = args.teacher_model or base_model
        config["teacher_inference"] = {
            "model": {
                "name": teacher_model_name,
                "max_model_len": args.max_model_len,
                "enforce_eager": True,
            },
            "server": {"port": args.teacher_port},
            "gpu_memory_utilization": args.gpu_memory_utilization,
        }
        config["orchestrator"]["teacher_model"] = {
            "model": {
                "name": teacher_model_name,
            },
            "client": {
                "base_url": [f"http://127.0.0.1:{args.teacher_port}/v1"],
            },
        }
        config["deployment"]["num_teacher_gpus"] = teacher_gpu_slots
    return config


def main() -> None:
    args = parse_args()
    adapter_dir = resolve_adapter_dir(args.adapter)
    adapter_cfg = load_adapter_config(adapter_dir)
    os.environ["PRIME_RL_INIT_ADAPTER"] = str(adapter_dir)
    pythonpath = os.environ.get("PYTHONPATH")
    cwd = str(Path.cwd())
    os.environ["PYTHONPATH"] = cwd if not pythonpath else f"{cwd}:{pythonpath}"
    venv_bin = str(Path(sys.executable).parent)
    path = os.environ.get("PATH")
    os.environ["PATH"] = venv_bin if not path else f"{venv_bin}:{path}"

    raw_config = build_config(args, adapter_cfg)
    raw_config.setdefault("metadata", {})
    raw_config["metadata"]["init_adapter_source"] = args.adapter
    raw_config["metadata"]["init_adapter_resolved_dir"] = str(adapter_dir)
    if args.teacher_model:
        raw_config["metadata"]["teacher_model"] = args.teacher_model

    if args.dump_config:
        args.dump_config.parent.mkdir(parents=True, exist_ok=True)
        args.dump_config.write_text(json.dumps(raw_config, indent=2) + "\n")

    print(json.dumps(raw_config, indent=2))
    if args.dry_run:
        return

    from prime_rl.configs.rl import RLConfig
    import prime_rl.entrypoints.rl as rl_mod
    import torch

    if args.enable_teacher_inference:
        if args.share_single_gpu:
            rl_mod.get_physical_gpu_ids = lambda: [0, 0, 0]
        else:
            gpu_count = torch.cuda.device_count()
            if gpu_count >= 4:
                rl_mod.get_physical_gpu_ids = lambda: [0, 2, 3]
            elif gpu_count == 3:
                rl_mod.get_physical_gpu_ids = lambda: [0, 1, 2]
            elif gpu_count == 2:
                rl_mod.get_physical_gpu_ids = lambda: [0, 1, 1]
            else:
                raise RuntimeError(
                    "Teacher inference requires either share_single_gpu or at least 2 visible GPUs."
                )
    elif args.share_single_gpu:
        rl_mod.get_physical_gpu_ids = lambda: [0, 0]

    validated_config = dict(raw_config)
    validated_config.pop("metadata", None)
    config = RLConfig.model_validate(validated_config)
    rl_mod.rl(config)


if __name__ == "__main__":
    main()
