#!/usr/bin/env python3
"""Forward-pass loss on the held-out 10% test set (assistant-masked).

Reports mean and per-token loss for base vs SFT, plus per-example deltas.
"""
import argparse
import json
import math
from pathlib import Path

from peft import PeftModel
import torch
from datasets import load_from_disk
from transformers import AutoModelForCausalLM, AutoTokenizer


def _is_adapter_dir(path: str) -> bool:
    p = Path(path)
    return p.is_dir() and (p / "adapter_config.json").exists()


def _has_local_tokenizer(path: str) -> bool:
    p = Path(path)
    if not p.is_dir():
        return False
    return any((p / name).exists() for name in (
        "tokenizer_config.json",
        "tokenizer.json",
        "vocab.json",
        "merges.txt",
    ))


def load_model(path: str, base_model: str | None = None):
    is_adapter = _is_adapter_dir(path)
    model_source = base_model if is_adapter else path
    tok_source = path if _has_local_tokenizer(path) else (base_model or path)
    tok = AutoTokenizer.from_pretrained(tok_source, trust_remote_code=True)
    try:
        base = AutoModelForCausalLM.from_pretrained(
            model_source, trust_remote_code=True, torch_dtype=torch.bfloat16,
            device_map="auto", attn_implementation="sdpa",
        )
    except Exception:
        base = AutoModelForCausalLM.from_pretrained(
            model_source, trust_remote_code=True, torch_dtype=torch.bfloat16, device_map="auto",
        )
    model = PeftModel.from_pretrained(base, path) if is_adapter else base
    model.eval()
    return model, tok


@torch.no_grad()
def loss_for(model, ids, labels, attn) -> tuple[float, int]:
    ids = torch.tensor(ids, device=model.device).unsqueeze(0)
    labels = torch.tensor(labels, device=model.device).unsqueeze(0)
    attn = torch.tensor(attn, device=model.device).unsqueeze(0)
    n_tokens = int((labels != -100).sum().item())
    if n_tokens == 0:
        return 0.0, 0
    out = model(input_ids=ids, attention_mask=attn, labels=labels)
    return float(out.loss.item()), n_tokens


def eval_model(model_path: str, dataset, name: str, base_model: str | None = None) -> dict:
    load_desc = f"{model_path} (base={base_model})" if base_model else model_path
    print(f"Loading {name}: {load_desc}")
    model, _ = load_model(model_path, base_model=base_model)
    losses = []
    token_counts = []
    for i, row in enumerate(dataset):
        loss, n = loss_for(model, row["input_ids"], row["labels"], row["attention_mask"])
        if n > 0:
            losses.append(loss)
            token_counts.append(n)
        if (i + 1) % 20 == 0:
            print(f"  {name}: {i + 1}/{len(dataset)}  running_mean={sum(losses)/len(losses):.4f}")
    del model
    torch.cuda.empty_cache()
    total_tokens = sum(token_counts)
    weighted = sum(l * n for l, n in zip(losses, token_counts)) / total_tokens
    return {
        "model": name,
        "n_examples": len(losses),
        "total_unmasked_tokens": total_tokens,
        "mean_loss_unweighted": sum(losses) / len(losses),
        "mean_loss_token_weighted": weighted,
        "perplexity": math.exp(weighted),
        "per_example_losses": losses,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--sft", required=True)
    ap.add_argument("--sft-base-model", default=None,
                    help="Base model to apply when --sft points to a PEFT adapter dir")
    ap.add_argument("--test-set", required=True, help="Path to dataset saved with save_to_disk")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    ds = load_from_disk(args.test_set)
    print(f"Test set: {len(ds)} rows, cols: {ds.column_names}")

    base_r = eval_model(args.base, ds, "base")
    sft_r = eval_model(args.sft, ds, "sft", base_model=args.sft_base_model)

    deltas = [b - s for b, s in zip(base_r["per_example_losses"], sft_r["per_example_losses"])]
    summary = {
        "base": {k: v for k, v in base_r.items() if k != "per_example_losses"},
        "sft": {k: v for k, v in sft_r.items() if k != "per_example_losses"},
        "delta_token_weighted_loss": base_r["mean_loss_token_weighted"] - sft_r["mean_loss_token_weighted"],
        "delta_mean_loss_unweighted": base_r["mean_loss_unweighted"] - sft_r["mean_loss_unweighted"],
        "perplexity_ratio_base_over_sft": base_r["perplexity"] / sft_r["perplexity"],
        "n_examples_sft_better": sum(1 for d in deltas if d > 0),
    }
    payload = {"summary": summary, "per_example": {"base": base_r["per_example_losses"], "sft": sft_r["per_example_losses"]}}
    Path(args.output).write_text(json.dumps(payload, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
