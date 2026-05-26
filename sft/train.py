#!/usr/bin/env python3
"""SFT training entry point. Run from repo root:
    python -m sft.train [flags]
To resume from latest checkpoint: --resume
"""
import argparse
from pathlib import Path

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq,
)

from sft.config import TrainConfig
from sft.data import load_traces, create_dataset

def setup_model_and_tokenizer(config: TrainConfig):
    """Load model + tokenizer for full fine-tuning."""
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
            attn_implementation="flash_attention",
        )
        print("✓ Using Flash Attention")
    except Exception as e:
        raise RuntimeError(f"Failed to load flash attention backend: {e}")

    if config.gradient_checkpointing:
        if hasattr(model, "enable_input_require_grads"):
            model.enable_input_require_grads()
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        print("✓ Gradient checkpointing enabled")

    return model, tokenizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="Qwen/Qwen3-4B-Base")
    parser.add_argument("--data", type=str, required=True,
                        help="Path to a local JSONL dataset file")
    parser.add_argument("--output", type=str, default="runs/sft1")
    parser.add_argument("--tokenizer", type=str, help="Tokenizer name/path; defaults to --model")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--warmup-ratio", type=float, default=0.03)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--lr-scheduler-type", type=str, default="cosine")
    parser.add_argument("--max-seq-length", type=int, default=1536)
    parser.add_argument("--resume", action="store_true", help="Resume from latest checkpoint")
    parser.add_argument("--resume-from", type=str, help="Resume from specific checkpoint")
    parser.add_argument("--bf16", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--tf32", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--gradient-checkpointing", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--save-strategy", type=str, default="steps")
    parser.add_argument("--save-steps", type=int, default=500)
    parser.add_argument("--save-total-limit", type=int, default=3)
    parser.add_argument("--eval-steps", type=int, default=25)
    parser.add_argument("--eval-batch-size", type=int, default=1)
    parser.add_argument("--load-best-model-at-end", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--no-train-split", action="store_true",
                        help="Train on the full dataset with no internal train/val/test split.")
    parser.add_argument("--logging-steps", type=int, default=10)
    parser.add_argument("--logging-first-step", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--report-to", type=str, default="tensorboard")
    parser.add_argument("--cache-dir", type=str, default=".cache", help="Cache directory for tokenized data")
    args = parser.parse_args()

    config = TrainConfig(
        model_name=args.model,
        tokenizer_name=args.tokenizer,
        data_path=args.data,
        output_dir=args.output,
        cache_dir=args.cache_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        warmup_ratio=args.warmup_ratio,
        weight_decay=args.weight_decay,
        lr_scheduler_type=args.lr_scheduler_type,
        max_seq_length=args.max_seq_length,
        masking_mode="assistant_only",
        bf16=args.bf16,
        tf32=args.tf32,
        gradient_checkpointing=args.gradient_checkpointing,
        save_strategy=args.save_strategy,
        save_steps=args.save_steps,
        save_total_limit=args.save_total_limit,
        logging_steps=args.logging_steps,
        logging_first_step=args.logging_first_step,
        report_to=args.report_to,
    )

    # resume from checkpoint
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

    # deduplication regardless of split or not
    seen = set()
    deduped = []
    for trace in traces:
        if trace["text"] not in seen:
            seen.add(trace["text"])
            deduped.append(trace)

    if len(deduped) != len(traces):
        print(f"Removed {len(traces) - len(deduped)} duplicate traces")

    full_dataset = create_dataset(
        deduped,
        tokenizer,
        config.max_seq_length,
        config.cache_dir,
    )

    if args.no_train_split:
        dataset = full_dataset
        eval_dataset = None
        print(f"Train: {len(dataset)}")
    else:
        first = full_dataset.train_test_split(test_size=0.2, seed=42)
        dataset = first["train"]

        holdout = first["test"].train_test_split(test_size=0.5, seed=42)
        eval_dataset = holdout["train"]
        test_dataset = holdout["test"]

        test_dir = Path(config.output_dir) / "test_set"
        test_dir.parent.mkdir(parents=True, exist_ok=True)
        test_dataset.save_to_disk(str(test_dir))

        print(
            f"Train: {len(dataset)}, "
            f"Val: {len(eval_dataset)}, "
            f"Test: {len(test_dataset)} "
            f"(saved to {test_dir})"
        )

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
        eval_strategy="no" if args.no_train_split else "steps",
        eval_steps=args.eval_steps,
        per_device_eval_batch_size=args.eval_batch_size,
        load_best_model_at_end=False if args.no_train_split else args.load_best_model_at_end,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        logging_steps=config.logging_steps,
        logging_first_step=config.logging_first_step,
        report_to=config.report_to,
        dataloader_num_workers=4,
        dataloader_pin_memory=True,
        remove_unused_columns=False,
        save_only_model=True,
        save_safetensors=True,
    )

    trainer_kwargs = dict(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=data_collator,
        processing_class=tokenizer,
    )
    if eval_dataset is not None:
        trainer_kwargs["eval_dataset"] = eval_dataset
    trainer = Trainer(**trainer_kwargs)
    print("\n" + "=" * 60)
    print("Starting training...")
    print(f"  Model: {config.model_name}")
    print(f"  Data: {config.data_path}")
    print(f"  Train samples: {len(dataset)}")
    if eval_dataset is not None:
        print(f"  Val samples: {len(eval_dataset)}")
    print(f"  Train split: {'disabled' if args.no_train_split else '80/10/10'}")
    print("  Masking mode: assistant_only")
    print(f"  Epochs: {config.num_train_epochs}")
    print(f"  Batch size per device: {config.per_device_train_batch_size}")
    print(f"  Gradient accumulation: {config.gradient_accumulation_steps}")
    print(f"  Effective batch size: {config.per_device_train_batch_size * config.gradient_accumulation_steps}")
    print(f"  Learning rate: {config.learning_rate}")
    print(f"  Max seq length: {config.max_seq_length}")
    print(f"  BF16: {config.bf16}")
    print(f"  Gradient checkpointing: {config.gradient_checkpointing}")
    print(f"  Output: {config.output_dir}")
    print(f"  Resume: {config.resume_from_checkpoint or 'none'}")
    print("=" * 60 + "\n")

    trainer.train(resume_from_checkpoint=config.resume_from_checkpoint)

    print("\nSaving final model...")
    final_dir = Path(config.output_dir) / "final"
    trainer.save_model(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))

    print("Training complete!")


if __name__ == "__main__":
    main()
