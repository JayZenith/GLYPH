"""Training config dataclass for SFT runs."""
from dataclasses import dataclass
from typing import Optional

@dataclass
class TrainConfig:
    # Model
    model_name: str = "Qwen/Qwen3-4B-Base"
    tokenizer_name: Optional[str] = None

    # Data
    data_path: Optional[str] = None
    max_seq_length: int = 1536
    masking_mode: str = "assistant_only"

    # Training
    output_dir: str = "runs/sft1"
    cache_dir: str = ".cache"
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 8  # Effective batch = 8 on a single GPU
    learning_rate: float = 2e-5
    warmup_ratio: float = 0.03
    weight_decay: float = 0.01
    lr_scheduler_type: str = "cosine"

    # Optimization
    bf16: bool = True
    tf32: bool = True
    gradient_checkpointing: bool = False

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
