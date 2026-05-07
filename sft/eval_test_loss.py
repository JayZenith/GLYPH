#!/usr/bin/env python3
"""Forward-pass loss on the held-out 10% test set (assistant-masked).

Reports mean and per-token loss for base vs SFT, plus per-example deltas.
"""
import argparse
import json
import math
from pathlib import Path

import torch
from datasets import load_from_disk
from transformers import AutoModelForCausalLM, AutoTokenizer


def load_model(path: str):
    tok = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            path, trust_remote_code=True, torch_dtype=torch.bfloat16,
            device_map="auto", attn_implementation="sdpa",
        )
    except Exception:
        model = AutoModelForCausalLM.from_pretrained(
            path, trust_remote_code=True, torch_dtype=torch.bfloat16, device_map="auto",
        )
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


def eval_model(model_path: str, dataset, name: str) -> dict:
    print(f"Loading {name}: {model_path}")
    model, _ = load_model(model_path)
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
    ap.add_argument("--test-set", required=True, help="Path to dataset saved with save_to_disk")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    ds = load_from_disk(args.test_set)
    print(f"Test set: {len(ds)} rows, cols: {ds.column_names}")

    base_r = eval_model(args.base, ds, "base")
    sft_r = eval_model(args.sft, ds, "sft")

    deltas = [b - s for b, s in zip(base_r["per_example_losses"], sft_r["per_example_losses"])]
    summary = {
        "base": {k: v for k, v in base_r.items() if k != "per_example_losses"},
        "sft": {k: v for k, v in sft_r.items() if k != "per_example_losses"},
        "delta_token_weighted_loss": base_r["mean_loss_token_weighted"] - sft_r["mean_loss_token_weighted"],
        "perplexity_ratio_base_over_sft": base_r["perplexity"] / sft_r["perplexity"],
        "n_examples_sft_better": sum(1 for d in deltas if d > 0),
    }
    payload = {"summary": summary, "per_example": {"base": base_r["per_example_losses"], "sft": sft_r["per_example_losses"]}}
    Path(args.output).write_text(json.dumps(payload, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
