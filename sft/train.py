#!/usr/bin/env python3
"""SFT training entry point. Run from repo root:

    python -m sft.train [flags]

To resume from latest checkpoint: --resume
To enable expensive greedy gen-eval at every eval step: --enable-gen-eval
To merge LoRA into base at end of training: --enable-merge (default off)
"""
import argparse
import os
from pathlib import Path

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq,
)
from peft import LoraConfig, get_peft_model

from sft.config import TrainConfig
from sft.data import load_traces, create_dataset
from sft.trainers import ParamGroupTrainer
from sft.evals import GenEvalCallback


def setup_model_and_tokenizer(config: TrainConfig):
    """Load model + tokenizer; apply LoRA before grad checkpointing."""
    print(f"Loading model: {config.model_name}")
    tokenizer_name = config.tokenizer_name or config.model_name

    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_name, trust_remote_code=True, padding_side="right",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

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

    # LoRA must be applied before gradient_checkpointing_enable, else PEFT's
    # trainable params won't get grads through the checkpointed graph.
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
    parser.add_argument("--enable-merge", action="store_true",
                        help="Merge LoRA into base at end of training (default off; merge locally instead)")
    parser.add_argument("--enable-gen-eval", action="store_true",
                        help="Run greedy generation eval after each evaluate() (expensive)")
    parser.add_argument("--cache-dir", type=str, default=".cache", help="Cache directory for tokenized data")
    args = parser.parse_args()

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

    if args.resume_from:
        config.resume_from_checkpoint = args.resume_from
    elif args.resume:
        checkpoint_dir = Path(config.output_dir)
        if checkpoint_dir.exists():
            checkpoints = sorted(
                [d for d in checkpoint_dir.iterdir() if d.is_dir() and d.name.startswith("checkpoint-")],
                key=lambda x: int(x.name.split("-")[1]),
            )
            if checkpoints:
                config.resume_from_checkpoint = str(checkpoints[-1])
                print(f"Resuming from: {config.resume_from_checkpoint}")

    model, tokenizer = setup_model_and_tokenizer(config)

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

    data_collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, padding=True, pad_to_multiple_of=8)

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
        deepspeed=None,
        ddp_find_unused_parameters=False,
    )

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
    if args.enable_gen_eval:
        trainer.add_callback(GenEvalCallback(tokenizer))

    print("\n" + "=" * 60)
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
    print("=" * 60 + "\n")

    trainer.train(resume_from_checkpoint=config.resume_from_checkpoint)

    print("\nSaving final model...")
    trainer.save_model(os.path.join(config.output_dir, "final"))
    tokenizer.save_pretrained(os.path.join(config.output_dir, "final"))

    if config.use_lora and args.enable_merge:
        print("Merging LoRA adapter into base model...")
        merged_model = trainer.model.merge_and_unload()
        merged_dir = os.path.join(config.output_dir, "merged")
        merged_model.save_pretrained(merged_dir)
        tokenizer.save_pretrained(merged_dir)
        print(f"Merged checkpoint saved to: {merged_dir}")
    elif config.use_lora:
        print("Skipping merge (use --enable-merge to merge in-process; default is off so disk is light).")

    print("Training complete!")


if __name__ == "__main__":
    main()
