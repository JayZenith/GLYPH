"""Training config dataclass for SFT runs."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TrainConfig:
    # Model
    model_name: str = "Qwen/Qwen3-4B-Base"
    tokenizer_name: Optional[str] = None

    # Data
    data_path: str = "synthetic_data/glyph_dataset.jsonl"
    max_seq_length: int = 8192
    masking_mode: str = "assistant_only"  # "assistant_only" | "full_trace"

    # Training
    output_dir: str = "runs/sft1"
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 8  # Effective batch = 8 on a single GPU
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
        "gate_proj", "up_proj", "down_proj",
    ])
    # Fully trained (not LoRA'd) so we can shift the vocab prior — needed for
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
