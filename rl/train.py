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

from transformers import AutoConfig, AutoTokenizer
import tomli_w


CONFIG_DIR = Path(__file__).resolve().parent / "configs" / "task_trace"


# turns "0,2,3" into [0,2,3] for --prime-rl-gpu-ids
def parse_int_list(value: str) -> list[int]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("Expected a comma-separated list of GPU ids.")
    try:
        return [int(item) for item in items]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("GPU ids must be integers.") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch PRIME-RL.")
    parser.add_argument("--model", default="JayZenith/SFT_V1",
                        help="HF repo id for trainer and rollout initialization.")
    parser.add_argument("--data", type=Path, default=Path("synthetic_data/rl_prompts_1062.jsonl"), help="Prompt dataset path.")
    parser.add_argument("--output", type=Path, default=Path("outputs/prime_rl"))
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--rollouts-per-example", type=int)
    parser.add_argument("--seq-len", type=int)
    parser.add_argument("--max-model-len", type=int)
    parser.add_argument("--teacher-max-model-len", type=int)
    parser.add_argument("--max-completion-tokens", type=int)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--weight-decay", type=float)
    parser.add_argument("--checkpoint-interval", type=int)
    parser.add_argument("--resume-step", type=int)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--gpu-memory-utilization", type=float)
    parser.add_argument("--teacher-gpu-memory-utilization", type=float)
    parser.add_argument("--max-samples", type=int)
    parser.add_argument("--max-tool-rounds", type=int)
    parser.add_argument("--nsjail-path")
    parser.add_argument("--tool-timeout", type=int)
    parser.add_argument("--port", type=int)
    parser.add_argument("--teacher-model", default="JayZenith/SFT_V1")
    parser.add_argument("--teacher-port", type=int, default=8001)
    parser.add_argument("--teacher-device", type=int, default=0)
    parser.add_argument("--teacher-tau", type=float, default=0.01)
    parser.add_argument("--prime-rl-gpu-ids", type=parse_int_list,
                        help="Comma-separated physical GPU ids managed by PRIME-RL. "
                             "Inference uses the first N infer GPUs; training uses the remaining train GPUs.")
    parser.add_argument("--num-train-gpus", type=int,
                        help="Number of GPUs reserved for trainer workers.")
    parser.add_argument("--num-infer-gpus", type=int,
                        help="Number of GPUs reserved for rollout inference.")
    parser.add_argument("--gpus-per-node", type=int,
                        help="Visible GPU count exposed to PRIME-RL for this run.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dump-config", type=Path)
    return parser.parse_args()


# Reads one TOML file into Python dict
def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def load_templates() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        load_toml(CONFIG_DIR / "trainer.toml"),
        load_toml(CONFIG_DIR / "orchestrator.toml"),
        load_toml(CONFIG_DIR / "inference.toml"),
    )

# write CLI vlaue into config if user passes it
def maybe_set(container: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        container[key] = value

# loads model config + tokenizer, if model vocab > tokenizer vocab we ban extra token IDs with logit bias -100
# prevents vLLM from sampling garbage invalid tokens
def add_invalid_token_logit_bias(sampling: dict[str, Any], model_name: str) -> None:
    cfg = AutoConfig.from_pretrained(model_name)
    tok = AutoTokenizer.from_pretrained(model_name)
    tokenizer_len = len(tok)
    model_vocab = int(getattr(cfg, "vocab_size", tokenizer_len))
    if model_vocab <= tokenizer_len:
        return

    extra_body = sampling.setdefault("extra_body", {})
    logit_bias = extra_body.setdefault("logit_bias", {})
    for token_id in range(tokenizer_len, model_vocab):
        logit_bias[token_id] = -100.0


def add_chat_boundary_stop_tokens(sampling: dict[str, Any], model_name: str) -> None:
    tok = AutoTokenizer.from_pretrained(model_name)
    stop_ids = [
        token_id
        for token_id in (
            tok.convert_tokens_to_ids("<|im_start|>"),
            tok.convert_tokens_to_ids("<|im_end|>"),
        )
        if isinstance(token_id, int) and token_id >= 0
    ]
    if not stop_ids:
        return
    extra_body = sampling.setdefault("extra_body", {})
    existing = extra_body.setdefault("stop_token_ids", [])
    extra_body["stop_token_ids"] = sorted({*existing, *stop_ids})
    extra_body["stop"] = ["<|im_end|>", "<|im_start|>"]

# clone inference config, swap in teacher model, sets teacher context length, sets teacher port,
# and lowers taecher GPU mem usage if I did not override it
def build_teacher_inference_config(
    inference: dict[str, Any],
    teacher_model_name: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    teacher_inference = deepcopy(inference)
    teacher_model = teacher_inference.setdefault("model", {})
    teacher_model["name"] = teacher_model_name
    if args.teacher_max_model_len is not None:
        teacher_model["max_model_len"] = args.teacher_max_model_len
    elif args.seq_len is not None:
        # Teacher only needs enough context to score rollout sequences.
        teacher_model["max_model_len"] = args.seq_len
    maybe_set(teacher_inference.setdefault("server", {}), "port", args.teacher_port)
    if args.teacher_gpu_memory_utilization is not None:
        teacher_inference["gpu_memory_utilization"] = args.teacher_gpu_memory_utilization
    else:
        teacher_inference["gpu_memory_utilization"] = max(
            0.2,
            min(float(teacher_inference.get("gpu_memory_utilization", 0.7)), 0.25),
        )
    return teacher_inference

# loads 3 TOML files and deletes trainer["buffer"] as this wrapper wants
# PRIME-RL's current config shape, not old buffer block
def build_config(args: argparse.Namespace) -> dict[str, Any]:
    trainer, orchestrator, inference = load_templates()
    trainer.pop("buffer", None)
    orchestrator.pop("model", None)

    # resolve paths and  model names
    output_dir = args.output.resolve()
    data_path = args.data.resolve() if args.data else None
    base_model = args.model
    rollout_model = base_model
    teacher_model_name = args.teacher_model or rollout_model

    trainer_model = trainer.setdefault("model", {})
    trainer_optim = trainer.setdefault("optim", {})
    trainer_loss = trainer.setdefault("loss", {})
    trainer_ckpt = trainer.setdefault("ckpt", {})

    # set trainable model name and trainer configs
    trainer_model["name"] = base_model
    maybe_set(trainer_model, "seq_len", args.seq_len)
    maybe_set(trainer_optim, "lr", args.learning_rate)
    maybe_set(trainer_optim, "weight_decay", args.weight_decay)
    maybe_set(trainer_loss, "teacher_tau", args.teacher_tau)
    maybe_set(trainer_ckpt, "interval", args.checkpoint_interval)
    maybe_set(trainer_ckpt, "resume_step", args.resume_step)
    maybe_set(trainer, "max_steps", args.max_steps)

    orch_student = orchestrator.setdefault("student", {})
    orch_student_client = orch_student.setdefault("client", {})
    orch_train = orchestrator.setdefault("train", {})
    orch_sampling = orch_train.setdefault("sampling", {})
    env_list = orch_train.setdefault("env", [{"id": "task-trace", "args": {}}])
    env_args = env_list[0].setdefault("args", {})
    orch_ckpt = orchestrator.setdefault("ckpt", {})

    # set rollout model and related configs
    orch_student.setdefault("model", {})["name"] = rollout_model
    orch_student_client["base_url"] = [f"http://localhost:{args.port}/v1"]
    maybe_set(orchestrator, "batch_size", args.batch_size)
    maybe_set(orchestrator, "rollouts_per_example", args.rollouts_per_example)
    maybe_set(orchestrator, "seq_len", args.seq_len)
    maybe_set(orchestrator, "max_steps", args.max_steps)
    maybe_set(orch_ckpt, "interval", args.checkpoint_interval)
    maybe_set(orch_ckpt, "resume_step", args.resume_step)
    maybe_set(orch_sampling, "temperature", args.temperature)
    maybe_set(orch_sampling, "max_completion_tokens", args.max_completion_tokens)
    add_invalid_token_logit_bias(orch_sampling, rollout_model)
    add_chat_boundary_stop_tokens(orch_sampling, rollout_model)

    # env args
    if data_path is not None:
        env_args["data_path"] = str(data_path)
    maybe_set(env_args, "max_samples", args.max_samples)
    maybe_set(env_args, "max_tool_rounds", args.max_tool_rounds)
    maybe_set(env_args, "nsjail_path", args.nsjail_path)
    maybe_set(env_args, "timeout", args.tool_timeout)

    # Inference
    infer_model = inference.setdefault("model", {})
    infer_server = inference.setdefault("server", {})
    infer_model["name"] = rollout_model
    maybe_set(infer_model, "max_model_len", args.max_model_len)
    maybe_set(infer_server, "port", args.port)
    maybe_set(inference, "gpu_memory_utilization", args.gpu_memory_utilization)
    inference.setdefault("vllm_extra", {})["served_model_name"] = [rollout_model]

    # teacher section
    training_mode = "opd"

    # GPU section
    managed_gpu_ids = args.prime_rl_gpu_ids
    num_train_gpus = args.num_train_gpus if args.num_train_gpus is not None else 1
    num_infer_gpus = args.num_infer_gpus if args.num_infer_gpus is not None else 1
    gpus_per_node = args.gpus_per_node
    if managed_gpu_ids is not None:
        required_gpus = num_train_gpus + num_infer_gpus
        if len(managed_gpu_ids) != required_gpus:
            raise ValueError(
                f"--prime-rl-gpu-ids must provide exactly {required_gpus} GPU ids "
                f"for {num_infer_gpus} infer + {num_train_gpus} train GPUs."
            )
        if gpus_per_node is None:
            gpus_per_node = len(managed_gpu_ids)
    elif gpus_per_node is None:
        gpus_per_node = 2

    config: dict[str, Any] = {
        "trainer": trainer,
        "orchestrator": orchestrator,
        "inference": inference,
        "output_dir": str(output_dir),
        "training_mode": training_mode,
        "wandb": {"offline": True, "shared": False},
        "deployment": {
            "type": "single_node",
            "gpus_per_node": gpus_per_node,
            "num_train_gpus": num_train_gpus,
            "num_infer_gpus": num_infer_gpus,
        },
    }
    if args.resume_step is not None:
        config["ckpt"] = {"resume_step": args.resume_step}
        if args.checkpoint_interval is not None:
            config["ckpt"]["interval"] = args.checkpoint_interval

    orchestrator["teacher"] = {
        "model": {"name": teacher_model_name},
        "client": {
            "base_url": [f"http://127.0.0.1:{args.teacher_port}"],
        },
    }

    return config


def patch_gpu_mapping(managed_gpu_ids: list[int] | None) -> None:
    import prime_rl.entrypoints.rl as rl_mod
    import torch

    if managed_gpu_ids is None:
        return

    gpu_count = torch.cuda.device_count()
    if len(set(managed_gpu_ids)) != len(managed_gpu_ids):
        raise RuntimeError(
            f"Managed GPU ids must be unique, got {managed_gpu_ids}."
        )
    if any(gpu_id < 0 or gpu_id >= gpu_count for gpu_id in managed_gpu_ids):
        raise RuntimeError(
            f"Managed GPU ids {managed_gpu_ids} are invalid for {gpu_count} visible GPUs."
        )

    # PRIME-RL allocates inference first, then trainer. This override allows
    # explicit placement while an external teacher vLLM uses its own GPU.
    rl_mod.get_physical_gpu_ids = lambda: list(managed_gpu_ids)
    rl_mod.check_gpus_available = lambda gpu_ids: None


def patch_prime_orchestrator_httpx_import() -> None:
    import prime_rl.orchestrator.utils as utils_mod

    path = Path(utils_mod.__file__).resolve()
    text = path.read_text(encoding="utf-8")
    if "httpx.AsyncClient" not in text or "import httpx\n" in text:
        return
    anchor = "import asyncio\n"
    if anchor in text:
        text = text.replace(anchor, anchor + "import httpx\n", 1)
    else:
        text = "import httpx\n" + text
    path.write_text(text, encoding="utf-8")
    print(f"Patched missing httpx import in {path}")


def launch_teacher_inference(raw_config: dict[str, Any], args: argparse.Namespace) -> subprocess.Popen[str]:
    teacher_model_name = args.teacher_model or raw_config["trainer"]["model"]["name"]
    teacher_inference = build_teacher_inference_config(raw_config["inference"], teacher_model_name, args)
    config_dir = Path(raw_config["output_dir"]) / "configs"
    log_dir = Path(raw_config["output_dir"]) / "logs"
    config_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    teacher_path = config_dir / "teacher_inference.toml"
    teacher_log_path = log_dir / "teacher_inference.log"
    with teacher_path.open("wb") as f:
        tomli_w.dump(teacher_inference, f)

    prime_rl_dir = Path(os.environ.get("PRIME_RL_DIR", "/workspace/prime-rl-src"))
    inference_bin = prime_rl_dir / ".venv/bin/inference"
    if not inference_bin.exists():
        inference_bin = Path("inference")

    teacher_log = teacher_log_path.open("a", encoding="utf-8")
    return subprocess.Popen(
        [str(inference_bin), "@", str(teacher_path)],
        env={
            **os.environ,
            "CUDA_VISIBLE_DEVICES": str(args.teacher_device),
        },
        stdout=teacher_log,
        stderr=subprocess.STDOUT,
        text=True,
    )


def main() -> None:
    args = parse_args()
    raw_config = build_config(args)
    raw_config["metadata"] = {
        "mode": "full_finetune",
        "init_model": args.model,
    }
    if args.dump_config:
        args.dump_config.parent.mkdir(parents=True, exist_ok=True)
        args.dump_config.write_text(json.dumps(raw_config, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(raw_config, indent=2))
    if args.dry_run:
        return

    cwd = str(Path.cwd())
    rl_dir = str(Path.cwd() / "rl")
    pythonpath = os.environ.get("PYTHONPATH")
    path_parts = [cwd, rl_dir]
    if pythonpath:
        path_parts.append(pythonpath)
    os.environ["PYTHONPATH"] = ":".join(path_parts)

    from prime_rl.configs.rl import RLConfig
    import prime_rl.entrypoints.rl as rl_mod

    patch_prime_orchestrator_httpx_import()
    managed_gpu_ids = args.prime_rl_gpu_ids
    if managed_gpu_ids is None:
        managed_gpu_ids = [0, 1]
    patch_gpu_mapping(managed_gpu_ids)
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
