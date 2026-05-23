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
from huggingface_hub import snapshot_download
import tomli_w


CONFIG_DIR = Path(__file__).resolve().parent / "configs" / "task_trace"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch PRIME-RL. Default mode is full-finetune.")
    parser.add_argument("--model", default="JayZenith/GLYPH_SFT",
                        help="HF repo id for full-finetune init (default mode).")
    parser.add_argument("--adapter", default=None,
                        help="HF repo id for a PEFT adapter (LoRA mode). Disables full-FT default.")
    parser.add_argument("--base-model", help="Override the adapter base model (LoRA mode only).")
    parser.add_argument("--data", type=Path, help="Prompt dataset path.")
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
    parser.add_argument("--disable-orchestrator-lora", action="store_true")
    parser.add_argument("--served-model-name", action="append")
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--gpu-memory-utilization", type=float)
    parser.add_argument("--teacher-gpu-memory-utilization", type=float)
    parser.add_argument("--max-samples", type=int)
    parser.add_argument("--max-trace-chars", type=int)
    parser.add_argument("--max-tool-rounds", type=int)
    parser.add_argument("--nsjail-path")
    parser.add_argument("--tool-timeout", type=int)
    parser.add_argument("--clean-tool-boundary-bonus", type=float)
    parser.add_argument("--structure-valid-bonus", type=float)
    parser.add_argument("--penalty-unbalanced-braces", type=float)
    parser.add_argument("--penalty-unbalanced-brackets", type=float)
    parser.add_argument("--penalty-unbalanced-special-quotes", type=float)
    parser.add_argument("--penalty-garbage-after-final-response", type=float)
    parser.add_argument("--penalty-final-response-unclosed", type=float)
    parser.add_argument("--penalty-missing-response", type=float)
    parser.add_argument("--penalty-undefined-tags", type=float)
    parser.add_argument("--penalty-unsatisfied-todos", type=float)
    parser.add_argument("--penalty-repetition", type=float)
    parser.add_argument("--penalty-tool-calls-without-matching-result", type=float)
    parser.add_argument("--penalty-not-ended-cleanly-after-response", type=float)
    parser.add_argument("--no-call-penalty", type=float)
    parser.add_argument("--any-success-bonus", type=float)
    parser.add_argument("--missing-results-penalty", type=float)
    parser.add_argument("--response-presence-bonus", type=float)
    parser.add_argument("--exact-final-termination-bonus", type=float)
    parser.add_argument("--port", type=int)
    parser.add_argument("--rollout-init-model", help="HF repo id for the rollout runtime model.")
    parser.add_argument("--teacher-model", default="JayZenith/GLYPH_SFT")
    parser.add_argument("--teacher-port", type=int, default=8001)
    parser.add_argument("--teacher-tau", type=float, default=0.01)
    parser.add_argument("--training-mode", choices=("rl", "opd", "sft"))
    parser.add_argument("--teacher-anchor", action=argparse.BooleanOptionalAction, default=False,
                        help="Run a frozen teacher inference server with KL anchoring.")
    parser.add_argument("--enable-teacher-inference", action="store_true",
                        help=argparse.SUPPRESS)  # back-compat; honored if set
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


def build_config(args: argparse.Namespace, adapter_cfg: dict[str, Any] | None) -> dict[str, Any]:
    trainer, orchestrator, inference = load_templates()
    trainer.pop("buffer", None)

    use_lora = adapter_cfg is not None
    output_dir = args.output.resolve()
    data_path = args.data.resolve() if args.data else None

    if use_lora:
        base_model = args.base_model or adapter_cfg["base_model_name_or_path"]
        rank = int(adapter_cfg["r"])
        alpha = float(adapter_cfg["lora_alpha"])
        dropout = float(adapter_cfg.get("lora_dropout", 0.0))
        target_modules = list(adapter_cfg["target_modules"])
        modules_to_save = list(adapter_cfg.get("modules_to_save") or [])
        adapter_label = str(args.adapter).replace("/", "__")
        adapter_name = f"{adapter_label}-r{rank}-a{int(alpha)}"
        auto_lora_name = f"r{rank}-a{float(alpha)}"
    else:
        base_model = args.base_model or args.model
        adapter_name = None
        auto_lora_name = None
    rollout_model = args.rollout_init_model or base_model
    teacher_model_name = args.teacher_model or rollout_model

    trainer_model = trainer.setdefault("model", {})
    trainer_optim = trainer.setdefault("optim", {})
    trainer_loss = trainer.setdefault("loss", {})
    trainer_ckpt = trainer.setdefault("ckpt", {})

    trainer_model["name"] = base_model
    if use_lora:
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
    maybe_set(trainer_ckpt, "resume_step", args.resume_step)
    maybe_set(trainer, "max_steps", args.max_steps)

    orch_model = orchestrator.setdefault("model", {})
    orch_train = orchestrator.setdefault("train", {})
    orch_sampling = orch_train.setdefault("sampling", {})
    env_list = orch_train.setdefault("env", [{"id": "task-trace", "args": {}}])
    env_args = env_list[0].setdefault("args", {})
    orch_ckpt = orchestrator.setdefault("ckpt", {})

    orch_model["name"] = rollout_model
    if use_lora and not args.disable_orchestrator_lora:
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
    maybe_set(orch_ckpt, "resume_step", args.resume_step)
    maybe_set(orch_sampling, "temperature", args.temperature)
    maybe_set(orch_sampling, "max_completion_tokens", args.max_completion_tokens)
    add_invalid_token_logit_bias(orch_sampling, rollout_model)
    if data_path is not None:
        env_args["data_path"] = str(data_path)
    maybe_set(env_args, "max_samples", args.max_samples)
    maybe_set(env_args, "max_trace_chars", args.max_trace_chars)
    maybe_set(env_args, "max_tool_rounds", args.max_tool_rounds)
    maybe_set(env_args, "nsjail_path", args.nsjail_path)
    maybe_set(env_args, "timeout", args.tool_timeout)
    maybe_set(env_args, "clean_tool_boundary_bonus", args.clean_tool_boundary_bonus)
    maybe_set(env_args, "structure_valid_bonus", args.structure_valid_bonus)
    maybe_set(env_args, "penalty_unbalanced_braces", args.penalty_unbalanced_braces)
    maybe_set(env_args, "penalty_unbalanced_brackets", args.penalty_unbalanced_brackets)
    maybe_set(env_args, "penalty_unbalanced_special_quotes", args.penalty_unbalanced_special_quotes)
    maybe_set(env_args, "penalty_garbage_after_final_response", args.penalty_garbage_after_final_response)
    maybe_set(env_args, "penalty_final_response_unclosed", args.penalty_final_response_unclosed)
    maybe_set(env_args, "penalty_missing_response", args.penalty_missing_response)
    maybe_set(env_args, "penalty_undefined_tags", args.penalty_undefined_tags)
    maybe_set(env_args, "penalty_unsatisfied_todos", args.penalty_unsatisfied_todos)
    maybe_set(env_args, "penalty_repetition", args.penalty_repetition)
    maybe_set(
        env_args,
        "penalty_tool_calls_without_matching_result",
        args.penalty_tool_calls_without_matching_result,
    )
    maybe_set(
        env_args,
        "penalty_not_ended_cleanly_after_response",
        args.penalty_not_ended_cleanly_after_response,
    )
    maybe_set(env_args, "no_call_penalty", args.no_call_penalty)
    maybe_set(env_args, "any_success_bonus", args.any_success_bonus)
    maybe_set(env_args, "missing_results_penalty", args.missing_results_penalty)
    maybe_set(env_args, "response_presence_bonus", args.response_presence_bonus)
    maybe_set(env_args, "exact_final_termination_bonus", args.exact_final_termination_bonus)

    infer_model = inference.setdefault("model", {})
    infer_server = inference.setdefault("server", {})
    infer_model["name"] = rollout_model
    maybe_set(infer_model, "max_model_len", args.max_model_len)
    maybe_set(infer_server, "port", args.port)
    maybe_set(inference, "gpu_memory_utilization", args.gpu_memory_utilization)
    served_aliases: list[str] = []
    candidates = [rollout_model, base_model]
    if use_lora:
        candidates += [adapter_name, auto_lora_name]
    candidates += list(args.served_model_name or [])
    for name in candidates:
        if name and name not in served_aliases:
            served_aliases.append(name)
    inference.setdefault("vllm_extra", {})["served_model_name"] = served_aliases

    teacher_on = bool(args.teacher_anchor or args.enable_teacher_inference)
    training_mode = args.training_mode or ("opd" if teacher_on else "rl")

    config: dict[str, Any] = {
        "trainer": trainer,
        "orchestrator": orchestrator,
        "inference": inference,
        "output_dir": str(output_dir),
        "training_mode": training_mode,
        "wandb": {"offline": True, "shared": False},
        "deployment": {
            "type": "single_node",
            "gpus_per_node": 2,
            "num_train_gpus": 1,
            "num_infer_gpus": 1,
        },
    }
    if args.resume_step is not None:
        config["ckpt"] = {"resume_step": args.resume_step}
        if args.checkpoint_interval is not None:
            config["ckpt"]["interval"] = args.checkpoint_interval

    if teacher_on:
        orchestrator["teacher"] = {
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
            "CUDA_VISIBLE_DEVICES": "0",
        },
        stdout=teacher_log,
        stderr=subprocess.STDOUT,
        text=True,
    )


def main() -> None:
    args = parse_args()
    if args.adapter:
        adapter_dir = resolve_adapter_dir(args.adapter)
        adapter_cfg = load_adapter_config(adapter_dir)
    else:
        adapter_dir = None
        adapter_cfg = None
    raw_config = build_config(args, adapter_cfg)
    raw_config["metadata"] = {
        "mode": "lora" if adapter_cfg else "full_finetune",
        "init_model": args.adapter or args.model,
    }
    if adapter_dir is not None:
        raw_config["metadata"]["init_adapter_resolved_dir"] = str(adapter_dir)
    if args.rollout_init_model:
        raw_config["metadata"]["rollout_init_model_source"] = args.rollout_init_model

    if args.dump_config:
        args.dump_config.parent.mkdir(parents=True, exist_ok=True)
        args.dump_config.write_text(json.dumps(raw_config, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(raw_config, indent=2))
    if args.dry_run:
        return

    if adapter_dir is not None:
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

    teacher_on = bool(args.teacher_anchor or args.enable_teacher_inference)
    patch_gpu_mapping(teacher_on)
    teacher_process: subprocess.Popen[str] | None = None
    if teacher_on:
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
