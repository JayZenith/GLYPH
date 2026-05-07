#!/usr/bin/env python3
"""
SFT Training script for TASK format traces.
Supports multi-GPU training with DeepSpeed, checkpointing, and resumption.

Usage:
    # Single run
    accelerate launch --config_file accelerate_config.yaml train.py
    
    # Resume from checkpoint
    accelerate launch --config_file accelerate_config.yaml train.py --resume
"""

import argparse
import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import torch
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    TrainerCallback,
    DataCollatorForSeq2Seq,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training


import re as _re

from evals import build_prompt as _build_prompt, load_prompts as _load_prompts


def _render_gen_eval_prompts() -> list[dict]:
    """Load gen_eval prompts from evals/prompts.yaml and render to TASK strings."""
    return [
        {"name": p["name"], "prompt": _build_prompt(p["user"], p.get("tools", []))}
        for p in _load_prompts("gen_eval")
    ]


_REP_PATTERN = _re.compile(r"(.{20,200}?)\1{4,}", _re.DOTALL)
_TAIL_OK = _re.compile(r"[\s※⊨𝑝🏷•\[\]\w\d\.\-\"']*")


class GenEvalCallback(TrainerCallback):
    """Runs greedy generation on a few prompts after each evaluation; logs
    ends_with_response_rate / no_repetition_rate / not_truncated_rate."""

    def __init__(self, tokenizer, prompts=None, max_new_tokens: int = 5500, every_n_evals: int = 2):
        if prompts is None:
            prompts = _render_gen_eval_prompts()
        self.tokenizer = tokenizer
        self.prompts = prompts
        self.max_new_tokens = max_new_tokens
        self.every_n_evals = every_n_evals
        self._eval_count = 0

    def on_evaluate(self, args, state, control, model=None, **kwargs):
        if not state.is_world_process_zero or model is None:
            return
        self._eval_count += 1
        if self._eval_count % self.every_n_evals != 0:
            return
        try:
            im_end_id = self.tokenizer.convert_tokens_to_ids("<|im_end|>")
            stop_ids = [self.tokenizer.eos_token_id]
            if im_end_id != self.tokenizer.unk_token_id:
                stop_ids.append(im_end_id)

            ends = no_rep = not_trunc = 0
            was_training = model.training
            model.eval()
            with torch.no_grad():
                for item in self.prompts:
                    inputs = self.tokenizer(item["prompt"], return_tensors="pt").to(model.device)
                    in_len = inputs["input_ids"].shape[1]
                    out = model.generate(
                        **inputs,
                        max_new_tokens=self.max_new_tokens,
                        do_sample=False,
                        pad_token_id=self.tokenizer.pad_token_id,
                        eos_token_id=stop_ids,
                    )
                    new_tokens = out.shape[1] - in_len
                    text = self.tokenizer.decode(out[0, in_len:], skip_special_tokens=False)
                    if "<|im_end|>" in text:
                        text = text.split("<|im_end|>")[0]

                    last_resp = text.rfind("response「")
                    last_close = text.rfind("」")
                    tail = text[last_close + 1:].strip() if last_close >= 0 else ""
                    if last_resp >= 0 and last_close > last_resp and bool(_TAIL_OK.fullmatch(tail)):
                        ends += 1
                    if _REP_PATTERN.search(text) is None:
                        no_rep += 1
                    if new_tokens < self.max_new_tokens - 10:
                        not_trunc += 1
            if was_training:
                model.train()

            n = len(self.prompts)
            metrics = {
                "gen/ends_with_response_rate": ends / n,
                "gen/no_repetition_rate": no_rep / n,
                "gen/not_truncated_rate": not_trunc / n,
            }
            print(f"[gen-eval @ step {state.global_step}] {metrics}")
            state.log_history.append({**metrics, "step": state.global_step})
        except Exception as e:
            print(f"[gen-eval @ step {state.global_step}] FAILED: {e}")


class ParamGroupTrainer(Trainer):
    """Trainer that puts modules_to_save params in a separate optimizer group with their own LR."""

    def __init__(self, *args, lm_head_lr: float = 5e-6, lm_head_module_names=("lm_head",), **kwargs):
        self._lm_head_lr = lm_head_lr
        self._lm_head_module_names = tuple(lm_head_module_names)
        super().__init__(*args, **kwargs)

    def create_optimizer(self):
        if self.optimizer is not None:
            return self.optimizer

        head_params, other_params = [], []
        for n, p in self.model.named_parameters():
            if not p.requires_grad:
                continue
            if any(m in n for m in self._lm_head_module_names):
                head_params.append(p)
            else:
                other_params.append(p)

        optim_cls, optim_kwargs = Trainer.get_optimizer_cls_and_kwargs(self.args)
        param_groups = [
            {"params": other_params, "lr": self.args.learning_rate},
            {"params": head_params, "lr": self._lm_head_lr},
        ]
        self.optimizer = optim_cls(param_groups, **{k: v for k, v in optim_kwargs.items() if k != "lr"})
        print(f"✓ Param groups — trunk LR={self.args.learning_rate}, head LR={self._lm_head_lr} "
              f"({len(head_params)} head tensors, {len(other_params)} other tensors)")
        return self.optimizer


@dataclass
class TrainConfig:
    # Model
    model_name: str = "Qwen/Qwen3-4B-Base"
    tokenizer_name: Optional[str] = None
    
    # Data
    data_path: str = "traces.processed.jsonl"
    max_seq_length: int = 32768  # Qwen3 supports 32k
    
    # Training (optimized for 8xH200 140GB with 32k context)
    output_dir: str = "./checkpoints"
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 1  # Single A100 80GB; bf16 + LoRA fits with 8k seq
    gradient_accumulation_steps: int = 8  # Effective batch = 1 * 8 * 1 GPU = 8
    learning_rate: float = 2e-5
    warmup_ratio: float = 0.03
    weight_decay: float = 0.01
    lr_scheduler_type: str = "cosine"
    
    # LoRA (default True; set False for full fine-tune)
    use_lora: bool = True
    lora_r: int = 64
    lora_alpha: int = 64
    lora_dropout: float = 0.05
    lora_target_modules: list = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ])
    # Fully trained (not LoRA'd) so we can shift the vocab prior — should be needed for
    # termination/repetition fixes. Qwen3-4B-Base has tied embeddings, so
    # training lm_head also updates embed_tokens.
    lora_modules_to_save: list = field(default_factory=lambda: ["lm_head"])
    # Separate LR for lm_head. Bumped to match trunk LR after 5e-6 didn't move
    # the vocab prior enough to teach termination.
    lm_head_lr: float = 2e-5
    
    # Optimization
    bf16: bool = True
    tf32: bool = True
    gradient_checkpointing: bool = True
    
    # Checkpointing
    save_strategy: str = "steps"
    save_steps: int = 500
    save_total_limit: int = 3
    
    # Logging
    logging_steps: int = 10
    logging_first_step: bool = True
    report_to: str = "tensorboard"
    
    # Resume
    resume_from_checkpoint: Optional[str] = None


def load_traces(data_path: str) -> list[dict]:
    """Load processed traces from JSONL."""
    traces = []
    with open(data_path) as f:
        for line in f:
            try:
                item = json.loads(line)
                traces.append({"text": item["trace"]})
            except:
                pass
    print(f"Loaded {len(traces)} traces from {data_path}")
    return traces


def create_dataset(traces: list[dict], tokenizer, max_seq_length: int, cache_dir: str = ".cache") -> Dataset:
    """Create tokenized dataset from traces with caching."""
    import hashlib
    
    # Create cache key from data + tokenizer + max_seq_length
    cache_key = hashlib.md5(
        f"v2_assistant_mask_{len(traces)}_{tokenizer.name_or_path}_{max_seq_length}".encode()
    ).hexdigest()[:12]
    cache_path = Path(cache_dir) / f"tokenized_{cache_key}"
    
    # Try to load from cache
    if cache_path.exists():
        print(f"✓ Loading tokenized dataset from cache: {cache_path}")
        dataset = Dataset.load_from_disk(str(cache_path))
        print(f"  Loaded {len(dataset)} samples")
        return dataset
    
    print(f"Tokenizing dataset (will cache to {cache_path})...")
    
    # First pass: get true lengths without truncation
    true_lengths = []
    for trace in traces:
        tokens = tokenizer(trace["text"], truncation=False, add_special_tokens=True)
        true_lengths.append(len(tokens["input_ids"]))
    
    # Report truncation stats
    truncated = sum(1 for l in true_lengths if l > max_seq_length)
    if truncated > 0:
        over_lengths = [l for l in true_lengths if l > max_seq_length]
        print(f"\n⚠️  Truncation warning:")
        print(f"   {truncated}/{len(traces)} traces exceed max_seq_length ({max_seq_length})")
        print(f"   Max length: {max(true_lengths)}, Median: {sorted(true_lengths)[len(true_lengths)//2]}")
        print(f"   Truncated lengths: min={min(over_lengths)}, max={max(over_lengths)}, avg={sum(over_lengths)//len(over_lengths)}")
    else:
        print(f"✓ No truncation needed (max trace: {max(true_lengths)} tokens)")
    
    # Mask everything except assistant turns. Each assistant span runs from after
    # `<|im_start|>assistant\n` up to and INCLUDING the next `<|im_end|>` (so the
    # model is trained to actually emit the stop token).
    asst_header_ids = tokenizer.encode("<|im_start|>assistant\n", add_special_tokens=False)
    im_end_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
    H = len(asst_header_ids)

    def make_labels(ids):
        labels = [-100] * len(ids)
        i = 0
        while i <= len(ids) - H:
            if ids[i:i + H] == asst_header_ids:
                j = i + H
                while j < len(ids) and ids[j] != im_end_id:
                    labels[j] = ids[j]
                    j += 1
                if j < len(ids):
                    labels[j] = ids[j]
                    i = j + 1
                else:
                    break
            else:
                i += 1
        return labels

    def tokenize(examples):
        tokenized = tokenizer(
            examples["text"],
            truncation=True,
            max_length=max_seq_length,
            padding=False,
            return_attention_mask=True,
        )
        tokenized["labels"] = [make_labels(ids) for ids in tokenized["input_ids"]]
        return tokenized
    
    dataset = Dataset.from_list(traces)
    dataset = dataset.map(
        tokenize,
        batched=True,
        remove_columns=["text"],
        num_proc=4,
        desc="Tokenizing"
    )
    
    # Filter out sequences that are too short
    original_len = len(dataset)
    dataset = dataset.filter(lambda x: len(x["input_ids"]) > 100)
    print(f"Filtered {original_len - len(dataset)} short sequences")
    
    # Save to cache
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.save_to_disk(str(cache_path))
    print(f"✓ Cached tokenized dataset to {cache_path}")
    
    return dataset


def setup_model_and_tokenizer(config: TrainConfig):
    """Load model and tokenizer."""
    
    print(f"Loading model: {config.model_name}")
    tokenizer_name = config.tokenizer_name or config.model_name
    
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_name,
        trust_remote_code=True,
        padding_side="right",
    )
    
    # Ensure pad token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # Load model
    try:
        model = AutoModelForCausalLM.from_pretrained(
            config.model_name,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16 if config.bf16 else torch.float32,
            attn_implementation="flash_attention_2",
        )
        print("✓ Using Flash Attention 2")
    except Exception as e:
        print(f"⚠️  Flash Attention 2 failed ({e}), falling back to SDPA")
        model = AutoModelForCausalLM.from_pretrained(
            config.model_name,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16 if config.bf16 else torch.float32,
            attn_implementation="sdpa",
        )
    
    # Apply LoRA FIRST (before grad checkpointing) so PEFT can wire trainable params correctly.
    if config.use_lora:
        print("Applying LoRA...")
        lora_config = LoraConfig(
            r=config.lora_r,
            lora_alpha=config.lora_alpha,
            lora_dropout=config.lora_dropout,
            target_modules=config.lora_target_modules,
            modules_to_save=config.lora_modules_to_save,
            bias="none",
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora_config)
        model.print_trainable_parameters()

    # Enable gradient checkpointing AFTER LoRA. With frozen base weights, input
    # embeddings need explicit require_grads or grads won't flow through.
    if config.gradient_checkpointing:
        if hasattr(model, "enable_input_require_grads"):
            model.enable_input_require_grads()
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        print("✓ Gradient checkpointing enabled")
    
    return model, tokenizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="Qwen/Qwen3-4B-Base")
    parser.add_argument("--data", type=str, default="synthetic_data/sft_train_1098_official.jsonl")
    parser.add_argument("--output", type=str, default="runs/sft1")
    parser.add_argument("--tokenizer", type=str, help="Tokenizer name/path; defaults to --model")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-seq-length", type=int, default=8192)
    parser.add_argument("--use-lora", action=argparse.BooleanOptionalAction, default=True,
                        help="Use LoRA (default True). Disable with --no-use-lora for full fine-tune.")
    parser.add_argument("--lora-r", type=int, default=64)
    parser.add_argument("--lora-alpha", type=int, default=64)
    parser.add_argument("--resume", action="store_true", help="Resume from latest checkpoint")
    parser.add_argument("--resume-from", type=str, help="Resume from specific checkpoint")
    parser.add_argument("--save-steps", type=int, default=500)
    parser.add_argument("--save-total-limit", type=int, default=3)
    parser.add_argument("--skip-merge", action="store_true", help="Skip merged-model save (do it locally instead)")
    parser.add_argument("--cache-dir", type=str, default=".cache", help="Cache directory for tokenized data")
    args = parser.parse_args()
    
    # Build config
    config = TrainConfig(
        model_name=args.model,
        tokenizer_name=args.tokenizer,
        data_path=args.data,
        output_dir=args.output,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        max_seq_length=args.max_seq_length,
        use_lora=args.use_lora,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,
    )
    
    # Handle resume
    if args.resume_from:
        config.resume_from_checkpoint = args.resume_from
    elif args.resume:
        # Find latest checkpoint
        checkpoint_dir = Path(config.output_dir)
        if checkpoint_dir.exists():
            checkpoints = sorted(
                [d for d in checkpoint_dir.iterdir() if d.is_dir() and d.name.startswith("checkpoint-")],
                key=lambda x: int(x.name.split("-")[1])
            )
            if checkpoints:
                config.resume_from_checkpoint = str(checkpoints[-1])
                print(f"Resuming from: {config.resume_from_checkpoint}")
    
    # Setup
    model, tokenizer = setup_model_and_tokenizer(config)
    
    # Load and prepare data
    traces = load_traces(config.data_path)
    full_dataset = create_dataset(traces, tokenizer, config.max_seq_length, args.cache_dir)

    # 80/10/10 train/val/test split with fixed seed.
    # val: in-loop loss tracking + early stopping
    # test: HELD OUT — never touched during training/HP tuning. Final eval only.
    first = full_dataset.train_test_split(test_size=0.2, seed=42)
    dataset = first["train"]
    holdout = first["test"].train_test_split(test_size=0.5, seed=42)
    eval_dataset = holdout["train"]
    test_dataset = holdout["test"]

    test_dir = Path(config.output_dir) / "test_set"
    test_dir.parent.mkdir(parents=True, exist_ok=True)
    test_dataset.save_to_disk(str(test_dir))
    print(f"Train: {len(dataset)}, Val: {len(eval_dataset)}, Test: {len(test_dataset)} (saved to {test_dir})")
    print(f"Sample token lengths (train): {[len(dataset[i]['input_ids']) for i in range(min(5, len(dataset)))]}")
    
    # Data collator - handles padding for variable length sequences
    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        padding=True,
        pad_to_multiple_of=8,  # Efficient for tensor cores
    )
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=config.output_dir,
        num_train_epochs=config.num_train_epochs,
        per_device_train_batch_size=config.per_device_train_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        warmup_ratio=config.warmup_ratio,
        weight_decay=config.weight_decay,
        lr_scheduler_type=config.lr_scheduler_type,
        bf16=config.bf16,
        tf32=config.tf32,
        gradient_checkpointing=config.gradient_checkpointing,
        save_strategy=config.save_strategy,
        save_steps=config.save_steps,
        save_total_limit=config.save_total_limit,
        eval_strategy="steps",
        eval_steps=25,
        per_device_eval_batch_size=1,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        logging_steps=config.logging_steps,
        logging_first_step=config.logging_first_step,
        report_to=config.report_to,
        dataloader_num_workers=4,
        dataloader_pin_memory=True,
        remove_unused_columns=False,
        # DeepSpeed will be configured via accelerate
        deepspeed=None,
        # For multi-GPU
        ddp_find_unused_parameters=False,
    )
    
    # Trainer
    trainer_cls = ParamGroupTrainer if config.use_lora and config.lora_modules_to_save else Trainer
    trainer_kwargs = dict(
        model=model,
        args=training_args,
        train_dataset=dataset,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
        processing_class=tokenizer,
    )
    if trainer_cls is ParamGroupTrainer:
        trainer_kwargs["lm_head_lr"] = config.lm_head_lr
        trainer_kwargs["lm_head_module_names"] = tuple(config.lora_modules_to_save)
    trainer = trainer_cls(**trainer_kwargs)
    trainer.add_callback(GenEvalCallback(tokenizer))
    
    # Train
    print("\n" + "="*60)
    print("Starting training...")
    print(f"  Model: {config.model_name}")
    print(f"  Data: {config.data_path} ({len(dataset)} samples)")
    print(f"  Epochs: {config.num_train_epochs}")
    print(f"  Batch size per device: {config.per_device_train_batch_size}")
    print(f"  Gradient accumulation: {config.gradient_accumulation_steps}")
    print(f"  Learning rate: {config.learning_rate}")
    print(f"  Max seq length: {config.max_seq_length}")
    print(f"  LoRA: {config.use_lora}")
    print(f"  Output: {config.output_dir}")
    if config.resume_from_checkpoint:
        print(f"  Resuming from: {config.resume_from_checkpoint}")
    print("="*60 + "\n")
    
    trainer.train(resume_from_checkpoint=config.resume_from_checkpoint)
    
    # Save final model
    print("\nSaving final model...")
    trainer.save_model(os.path.join(config.output_dir, "final"))
    tokenizer.save_pretrained(os.path.join(config.output_dir, "final"))

    if config.use_lora and not args.skip_merge:
        print("Merging LoRA adapter into base model...")
        merged_model = trainer.model.merge_and_unload()
        merged_dir = os.path.join(config.output_dir, "merged")
        merged_model.save_pretrained(merged_dir)
        tokenizer.save_pretrained(merged_dir)
        print(f"Merged checkpoint saved to: {merged_dir}")
    elif config.use_lora:
        print("Skipping merge (use --skip-merge=False to enable; merge locally instead).")
    
    print("Training complete!")


if __name__ == "__main__":
    main()
