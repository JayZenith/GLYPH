#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path
from typing import Any

from huggingface_hub import snapshot_download
from transformers import AutoConfig, AutoTokenizer

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent_runtime.chatml import GLYPH_CHAT_TEMPLATE, assert_glyph_template_parity

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
    parser.add_argument("--lora-rank", type=int,
                        help="Train a LoRA adapter on --model.")
    parser.add_argument("--lora-alpha", type=float,
                        help="LoRA alpha for --lora-rank. Defaults to 2 * rank.")
    parser.add_argument("--lora-dropout", type=float, default=0.0)
    parser.add_argument("--lora-target-modules",
                        default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj")
    parser.add_argument("--lora-modules-to-save", default="")
    parser.add_argument("--lora-name",
                        help="Served adapter name for fresh LoRA mode.")
    parser.add_argument("--data", type=Path, default=Path("synthetic_data/rl_prompts_signal_v3_pool_b_mixed.jsonl"), help="Prompt dataset path.")
    parser.add_argument("--output", type=Path, default=Path("outputs/prime_rl"))
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--rollouts-per-example", type=int)
    parser.add_argument("--seq-len", type=int)
    parser.add_argument("--max-model-len", type=int)
    parser.add_argument("--max-completion-tokens", type=int)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--weight-decay", type=float)
    parser.add_argument("--activation-checkpointing", action="store_true",
                        help="Enable PRIME-RL full activation checkpointing for long-context training.")
    parser.add_argument("--activation-offloading", action="store_true",
                        help="Enable PRIME-RL activation CPU offloading; also enables activation checkpointing.")
    parser.add_argument("--optim-cpu-offload", action="store_true",
                        help="Offload optimizer state to CPU to reduce trainer GPU memory.")
    parser.add_argument("--fused-lm-head-token-chunk-size",
                        help="PRIME-RL fused LM head chunk size, e.g. 'auto' or an integer.")
    parser.add_argument("--checkpoint-interval", type=int)
    parser.add_argument("--resume-step", type=int)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--gpu-memory-utilization", type=float)
    parser.add_argument("--max-samples", type=int)
    parser.add_argument("--max-tool-rounds", type=int)
    parser.add_argument("--tool-timeout", type=int)
    parser.add_argument("--structure-valid-bonus", type=float)
    parser.add_argument("--no-call-penalty", type=float)
    parser.add_argument("--malformed-call-penalty", type=float)
    parser.add_argument("--no-verifier-penalty", type=float)
    parser.add_argument("--bad-cargo-project-path-penalty", type=float)
    parser.add_argument("--bad-final-hygiene-penalty", type=float)
    parser.add_argument("--tool-budget-exhausted-penalty", type=float)
    parser.add_argument("--final-once-bonus", type=float)
    parser.add_argument("--missing-final-penalty", type=float)
    parser.add_argument("--verifier-success-bonus", type=float)
    parser.add_argument("--verifier-success-clean-final-bonus", type=float)
    parser.add_argument("--tool-after-success-penalty", type=float)
    parser.add_argument("--failed-verifier-penalty", type=float)
    parser.add_argument("--max-failed-verifier-penalty", type=float)
    parser.add_argument("--port", type=int)
    parser.add_argument("--teacher-model", default="JayZenith/SFT_V1")
    parser.add_argument("--teacher-base-url",
                        help="External teacher inference base URL. Defaults to http://127.0.0.1:<teacher-port>.")
    parser.add_argument("--teacher-port", type=int, default=8001)
    # Anchor to the SFT reference. 0.01 was effectively no KL: the policy drifted
    # and collapsed (clean_end 0.75->0.33, terminal success 0.99->0.70). RL here
    # is a nudge, not a rewrite -- keep it close to SFT.
    parser.add_argument("--teacher-tau", type=float, default=0.2)
    parser.add_argument("--enforce-gibberish-filter", action="store_true",
                        help="Drop gibberish-filtered rollout groups instead of only monitoring them.")
    parser.add_argument("--enforce-repetition-filter", action="store_true",
                        help="Drop repetition-filtered rollout groups instead of only monitoring them.")
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


def _safe_model_dir_name(model_name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "__" for ch in model_name)


def materialize_glyph_chat_model(model_name: str, output_dir: Path) -> str:
    """Create a local model view whose tokenizer renders Glyph ChatML.

    Qwen's default template renders `role=tool` as a user `<tool_response>`
    block. SFT/eval use literal `<|im_start|>tool` blocks, so RL must point
    tokenizer-loading code at a local model view with the Glyph template.
    """
    local = Path(model_name)
    source = local.resolve() if local.exists() else Path(snapshot_download(repo_id=model_name, repo_type="model"))
    dest = output_dir / "glyph_chat_models" / _safe_model_dir_name(model_name)
    dest.mkdir(parents=True, exist_ok=True)

    for item in source.iterdir():
        target = dest / item.name
        if target.exists() or target.is_symlink():
            continue
        if item.is_dir():
            target.symlink_to(item, target_is_directory=True)
        else:
            target.symlink_to(item)

    tokenizer = AutoTokenizer.from_pretrained(str(source))
    tokenizer.chat_template = GLYPH_CHAT_TEMPLATE
    assert_glyph_template_parity(tokenizer)
    for name in (
        "chat_template.jinja",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "tokenizer.json",
    ):
        target = dest / name
        if target.exists() or target.is_symlink():
            target.unlink()
    tokenizer.save_pretrained(str(dest))
    (dest / "chat_template.jinja").write_text(GLYPH_CHAT_TEMPLATE, encoding="utf-8")
    return str(dest)


# write CLI vlaue into config if user passes it
def maybe_set(container: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        container[key] = value


def set_filter_enforcement(orchestrator: dict[str, Any], filter_type: str, enforce: bool) -> None:
    filters = orchestrator.setdefault("filters", [])
    for item in filters:
        if item.get("type") == filter_type:
            item["enforce"] = enforce
            return
    filters.append({"type": filter_type, "enforce": enforce})


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

def build_config(args: argparse.Namespace) -> dict[str, Any]:
    trainer, orchestrator, inference = load_templates()
    trainer.pop("buffer", None)
    orchestrator.pop("model", None)

    output_dir = args.output.resolve()
    data_path = args.data.resolve() if args.data else None
    use_lora = args.lora_rank is not None
    adapter_name = None
    auto_lora_name = None

    base_model = args.model
    if use_lora:
        rank = args.lora_rank
        alpha = float(args.lora_alpha if args.lora_alpha is not None else 2 * rank)
        dropout = float(args.lora_dropout)
        target_modules = [m.strip() for m in args.lora_target_modules.split(",") if m.strip()]
        modules_to_save = [m.strip() for m in args.lora_modules_to_save.split(",") if m.strip()]
        adapter_name = args.lora_name or f"glyph-rlvr-r{rank}-a{int(alpha)}"
        auto_lora_name = f"r{rank}-a{float(alpha)}"

    teacher_model_name = args.teacher_model or base_model
    if not args.dry_run:
        base_model = materialize_glyph_chat_model(base_model, output_dir)
        teacher_model_name = materialize_glyph_chat_model(teacher_model_name, output_dir)

    trainer_model = trainer.setdefault("model", {})
    trainer_optim = trainer.setdefault("optim", {})
    trainer_loss = trainer.setdefault("loss", {})
    trainer_ckpt = trainer.setdefault("ckpt", {})

    # set trainable model name and trainer configs
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
    if args.activation_checkpointing:
        trainer_model["ac"] = {"mode": "full", "freq": 1}
    if args.activation_offloading:
        trainer_model["ac_offloading"] = {"pin_memory": True, "max_inflight_activations": 5}
    if args.optim_cpu_offload:
        trainer_model["optim_cpu_offload"] = True
    if args.fused_lm_head_token_chunk_size is not None:
        value: str | int = args.fused_lm_head_token_chunk_size
        if value not in {"auto", "disabled"}:
            value = int(value)
        trainer_model["fused_lm_head_token_chunk_size"] = value
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
    orch_student_model = orch_student.setdefault("model", {})
    orch_student_model["name"] = base_model
    if use_lora:
        orch_student_model["lora"] = {
            "name": adapter_name,
            "rank": rank,
            "alpha": alpha,
        }
    student_port = args.port if args.port is not None else inference.get("server", {}).get("port", 8000)
    orch_student_client["base_url"] = [f"http://localhost:{student_port}/v1"]
    maybe_set(orchestrator, "batch_size", args.batch_size)
    maybe_set(orchestrator, "rollouts_per_example", args.rollouts_per_example)
    maybe_set(orchestrator, "seq_len", args.seq_len)
    maybe_set(orchestrator, "max_steps", args.max_steps)
    maybe_set(orch_ckpt, "interval", args.checkpoint_interval)
    maybe_set(orch_ckpt, "resume_step", args.resume_step)
    if args.enforce_gibberish_filter:
        set_filter_enforcement(orchestrator, "gibberish", True)
    if args.enforce_repetition_filter:
        set_filter_enforcement(orchestrator, "repetition", True)
    maybe_set(orch_sampling, "temperature", args.temperature)
    maybe_set(orch_sampling, "max_completion_tokens", args.max_completion_tokens)
    if not args.dry_run:
        add_invalid_token_logit_bias(orch_sampling, base_model)
        add_chat_boundary_stop_tokens(orch_sampling, base_model)

    # env args
    if data_path is not None:
        env_args["data_path"] = str(data_path)
    maybe_set(env_args, "max_samples", args.max_samples)
    maybe_set(env_args, "max_tool_rounds", args.max_tool_rounds)
    maybe_set(env_args, "timeout", args.tool_timeout)
    maybe_set(env_args, "structure_valid_bonus", args.structure_valid_bonus)
    maybe_set(env_args, "no_call_penalty", args.no_call_penalty)
    maybe_set(env_args, "malformed_call_penalty", args.malformed_call_penalty)
    maybe_set(env_args, "no_verifier_penalty", args.no_verifier_penalty)
    maybe_set(env_args, "bad_cargo_project_path_penalty", args.bad_cargo_project_path_penalty)
    maybe_set(env_args, "bad_final_hygiene_penalty", args.bad_final_hygiene_penalty)
    maybe_set(env_args, "tool_budget_exhausted_penalty", args.tool_budget_exhausted_penalty)
    maybe_set(env_args, "final_once_bonus", args.final_once_bonus)
    maybe_set(env_args, "missing_final_penalty", args.missing_final_penalty)
    maybe_set(env_args, "verifier_success_bonus", args.verifier_success_bonus)
    maybe_set(env_args, "verifier_success_clean_final_bonus", args.verifier_success_clean_final_bonus)
    maybe_set(env_args, "tool_after_success_penalty", args.tool_after_success_penalty)
    maybe_set(env_args, "failed_verifier_penalty", args.failed_verifier_penalty)
    maybe_set(env_args, "max_failed_verifier_penalty", args.max_failed_verifier_penalty)

    # Inference
    infer_model = inference.setdefault("model", {})
    infer_server = inference.setdefault("server", {})
    infer_model["name"] = base_model
    maybe_set(infer_model, "max_model_len", args.max_model_len)
    maybe_set(infer_server, "port", args.port)
    maybe_set(inference, "gpu_memory_utilization", args.gpu_memory_utilization)
    served_aliases: list[str] = []
    candidates = [base_model]
    if use_lora:
        candidates += [adapter_name, auto_lora_name]
    for name in candidates:
        if name and name not in served_aliases:
            served_aliases.append(name)
    inference.setdefault("vllm_extra", {})["served_model_name"] = served_aliases

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
            "base_url": [args.teacher_base_url or f"http://127.0.0.1:{args.teacher_port}"],
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


def main() -> None:
    args = parse_args()
    raw_config = build_config(args)

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

    config = RLConfig.model_validate(raw_config)
    rl_mod.rl_local(config)


if __name__ == "__main__":
    main()
