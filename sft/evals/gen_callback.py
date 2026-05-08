"""GenEvalCallback — runs greedy generation on a small held-out prompt set
after each Trainer evaluation and logs ends_with_response / no_repetition /
not_truncated rates. Imported by sft/train.py.
"""
import re

import torch
from transformers import TrainerCallback

from .prompt_loader import build_prompt, load_prompts


_REP_PATTERN = re.compile(r"(.{20,200}?)\1{4,}", re.DOTALL)
_TAIL_OK = re.compile(r"[\s※⊨𝑝🏷•\[\]\w\d\.\-\"']*")


def _render_gen_eval_prompts() -> list[dict]:
    """Load gen_eval prompts from evals/prompts.yaml and render to TASK strings."""
    return [
        {"name": p["name"], "prompt": build_prompt(p["user"], p.get("tools", []))}
        for p in load_prompts("gen_eval")
    ]


class GenEvalCallback(TrainerCallback):
    """Greedy gen-eval after each eval; logs ends_with_response_rate /
    no_repetition_rate / not_truncated_rate."""

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
