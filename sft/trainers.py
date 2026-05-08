"""Custom Trainer subclasses for SFT."""
from transformers import Trainer


class ParamGroupTrainer(Trainer):
    """Puts modules_to_save params in a separate optimizer group with their own LR.

    Used so the fully-trained `lm_head` can have a different learning rate from
    the LoRA-adapted trunk (set via `lm_head_lr`).
    """

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
