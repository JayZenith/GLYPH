#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tomllib
from copy import deepcopy
from pathlib import Path
from typing import Any

from huggingface_hub import snapshot_download
import tomli_w


CONFIG_DIR = Path(__file__).resolve().parent / "configs" / "task_trace"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch PRIME-RL from a PEFT adapter.")
    parser.add_argument("--adapter", required=True, help="HF repo id for the PEFT adapter.")
    parser.add_argument("--base-model", help="Override the adapter base model.")
    parser.add_argument("--data", type=Path, help="Prompt dataset path.")
    parser.add_argument("--output", type=Path, default=Path("outputs/prime_rl"))
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--rollouts-per-example", type=int)
    parser.add_argument("--seq-len", type=int)
    parser.add_argument("--max-model-len", type=int)
    parser.add_argument("--max-completion-tokens", type=int)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--weight-decay", type=float)
    parser.add_argument("--checkpoint-interval", type=int)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--gpu-memory-utilization", type=float)
    parser.add_argument("--teacher-gpu-memory-utilization", type=float)
    parser.add_argument("--max-samples", type=int)
    parser.add_argument("--max-trace-chars", type=int)
    parser.add_argument("--nsjail-path")
    parser.add_argument("--tool-timeout", type=int)
    parser.add_argument("--port", type=int)
    parser.add_argument("--rollout-init-model", help="HF repo id for the rollout runtime model.")
    parser.add_argument("--teacher-model")
    parser.add_argument("--teacher-port", type=int)
    parser.add_argument("--teacher-tau", type=float)
    parser.add_argument("--enable-teacher-inference", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dump-config", type=Path)
    return parser.parse_args()


def resolve_adapter_dir(adapter: str) -> Path:
    return Path(snapshot_download(repo_id=adapter, repo_type="model"))


def load_adapter_config(adapter_dir: Path) -> dict[str, Any]:
    path = adapter_dir / "adapter_config.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def load_templates() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        load_toml(CONFIG_DIR / "trainer.toml"),
        load_toml(CONFIG_DIR / "orchestrator.toml"),
        load_toml(CONFIG_DIR / "inference.toml"),
    )


def maybe_set(container: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        container[key] = value


def build_teacher_inference_config(
    inference: dict[str, Any],
    teacher_model_name: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    teacher_inference = deepcopy(inference)
    teacher_inference.setdefault("model", {})["name"] = teacher_model_name
    maybe_set(teacher_inference.setdefault("server", {}), "port", args.teacher_port)
    if args.teacher_gpu_memory_utilization is not None:
        teacher_inference["gpu_memory_utilization"] = args.teacher_gpu_memory_utilization
    else:
        teacher_inference["gpu_memory_utilization"] = min(
            float(teacher_inference.get("gpu_memory_utilization", 0.7)),
            0.12,
        )
    return teacher_inference


def build_config(args: argparse.Namespace, adapter_cfg: dict[str, Any]) -> dict[str, Any]:
    trainer, orchestrator, inference = load_templates()
    trainer.pop("buffer", None)

    base_model = args.base_model or adapter_cfg["base_model_name_or_path"]
    output_dir = args.output.resolve()
    data_path = args.data.resolve() if args.data else None

    rank = int(adapter_cfg["r"])
    alpha = float(adapter_cfg["lora_alpha"])
    dropout = float(adapter_cfg.get("lora_dropout", 0.0))
    target_modules = list(adapter_cfg["target_modules"])
    modules_to_save = list(adapter_cfg.get("modules_to_save") or [])
    adapter_label = str(args.adapter).replace("/", "__")
    adapter_name = f"{adapter_label}-r{rank}-a{int(alpha)}"
    rollout_model = args.rollout_init_model or base_model
    teacher_model_name = args.teacher_model or rollout_model

    trainer_model = trainer.setdefault("model", {})
    trainer_optim = trainer.setdefault("optim", {})
    trainer_loss = trainer.setdefault("loss", {})
    trainer_ckpt = trainer.setdefault("ckpt", {})

    trainer_model["name"] = base_model
    trainer_model["lora"] = {
        "rank": rank,
        "alpha": alpha,
        "dropout": dropout,
        "target_modules": target_modules,
        "modules_to_save": modules_to_save,
    }
    maybe_set(trainer_model, "seq_len", args.seq_len)
    maybe_set(trainer_optim, "lr", args.learning_rate)
    maybe_set(trainer_optim, "weight_decay", args.weight_decay)
    maybe_set(trainer_loss, "teacher_tau", args.teacher_tau)
    maybe_set(trainer_ckpt, "interval", args.checkpoint_interval)
    maybe_set(trainer, "max_steps", args.max_steps)

    orch_model = orchestrator.setdefault("model", {})
    orch_train = orchestrator.setdefault("train", {})
    orch_sampling = orch_train.setdefault("sampling", {})
    env_list = orch_train.setdefault("env", [{"id": "task-trace", "args": {}}])
    env_args = env_list[0].setdefault("args", {})
    orch_ckpt = orchestrator.setdefault("ckpt", {})

    orch_model["name"] = rollout_model
    orch_model["lora"] = {
        "name": adapter_name,
        "rank": rank,
        "alpha": alpha,
    }
    maybe_set(orchestrator, "batch_size", args.batch_size)
    maybe_set(orchestrator, "rollouts_per_example", args.rollouts_per_example)
    maybe_set(orchestrator, "seq_len", args.seq_len)
    maybe_set(orchestrator, "max_steps", args.max_steps)
    maybe_set(orch_ckpt, "interval", args.checkpoint_interval)
    maybe_set(orch_sampling, "temperature", args.temperature)
    maybe_set(orch_sampling, "max_completion_tokens", args.max_completion_tokens)
    if data_path is not None:
        env_args["data_path"] = str(data_path)
    maybe_set(env_args, "max_samples", args.max_samples)
    maybe_set(env_args, "max_trace_chars", args.max_trace_chars)
    maybe_set(env_args, "nsjail_path", args.nsjail_path)
    maybe_set(env_args, "timeout", args.tool_timeout)

    infer_model = inference.setdefault("model", {})
    infer_server = inference.setdefault("server", {})
    infer_model["name"] = rollout_model
    maybe_set(infer_model, "max_model_len", args.max_model_len)
    maybe_set(infer_server, "port", args.port)
    maybe_set(inference, "gpu_memory_utilization", args.gpu_memory_utilization)

    config: dict[str, Any] = {
        "trainer": trainer,
        "orchestrator": orchestrator,
        "inference": inference,
        "output_dir": str(output_dir),
        "wandb": {"offline": True, "shared": False},
        "deployment": {
            "type": "single_node",
            "gpus_per_node": 2,
            "num_train_gpus": 1,
            "num_infer_gpus": 1,
        },
    }

    if args.enable_teacher_inference:
        orchestrator["teacher_model"] = {
            "model": {"name": teacher_model_name},
            "client": {
                "base_url": [f"http://127.0.0.1:{args.teacher_port}/v1"],
            },
        }

    return config


def patch_gpu_mapping(enable_teacher_inference: bool) -> None:
    import prime_rl.entrypoints.rl as rl_mod
    import torch

    if not enable_teacher_inference:
        return

    gpu_count = torch.cuda.device_count()
    if gpu_count != 2:
        raise RuntimeError(
            f"This launcher is pinned to the 2-GPU setup, but found {gpu_count} visible GPUs."
        )

    # PRIME-RL allocates inference first, then trainer. Keep rollout inference
    # on GPU 0 and trainer on GPU 1. The external teacher server also runs on GPU 0.
    rl_mod.get_physical_gpu_ids = lambda: [0, 1]
    rl_mod.check_gpus_available = lambda gpu_ids: None


def launch_teacher_inference(raw_config: dict[str, Any], args: argparse.Namespace) -> subprocess.Popen[str]:
    teacher_model_name = args.teacher_model or raw_config["trainer"]["model"]["name"]
    teacher_inference = build_teacher_inference_config(raw_config["inference"], teacher_model_name, args)
    config_dir = Path(raw_config["output_dir"]) / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    teacher_path = config_dir / "teacher_inference.toml"
    with teacher_path.open("wb") as f:
        tomli_w.dump(teacher_inference, f)

    return subprocess.Popen(
        ["inference", "@", str(teacher_path)],
        env={
            **os.environ,
            "CUDA_VISIBLE_DEVICES": "0",
        },
    )


def main() -> None:
    args = parse_args()
    adapter_dir = resolve_adapter_dir(args.adapter)
    adapter_cfg = load_adapter_config(adapter_dir)
    raw_config = build_config(args, adapter_cfg)
    raw_config["metadata"] = {
        "init_adapter_source": args.adapter,
        "init_adapter_resolved_dir": str(adapter_dir),
    }
    if args.rollout_init_model:
        raw_config["metadata"]["rollout_init_model_source"] = args.rollout_init_model

    if args.dump_config:
        args.dump_config.parent.mkdir(parents=True, exist_ok=True)
        args.dump_config.write_text(json.dumps(raw_config, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(raw_config, indent=2))
    if args.dry_run:
        return

    os.environ["PRIME_RL_INIT_ADAPTER"] = str(adapter_dir)
    os.environ["PRIME_RL_INFERENCE_FULL_WEIGHTS"] = "1"
    cwd = str(Path.cwd())
    rl_dir = str(Path.cwd() / "rl")
    pythonpath = os.environ.get("PYTHONPATH")
    path_parts = [cwd, rl_dir]
    if pythonpath:
        path_parts.append(pythonpath)
    os.environ["PYTHONPATH"] = ":".join(path_parts)

    from prime_rl.configs.rl import RLConfig
    import prime_rl.entrypoints.rl as rl_mod

    patch_gpu_mapping(args.enable_teacher_inference)
    teacher_process: subprocess.Popen[str] | None = None
    if args.enable_teacher_inference:
        teacher_process = launch_teacher_inference(raw_config, args)

    validated_config = dict(raw_config)
    validated_config.pop("metadata", None)
    config = RLConfig.model_validate(validated_config)
    try:
        rl_mod.rl_local(config)
    finally:
        if teacher_process is not None and teacher_process.poll() is None:
            teacher_process.terminate()


if __name__ == "__main__":
    main()
