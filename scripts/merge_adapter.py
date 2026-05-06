#!/usr/bin/env python3
"""Merge LoRA adapter (with modules_to_save lm_head) into base model.

Loads base on CPU in bf16. Applies adapter. Saves merged model.
"""
import argparse
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="Qwen/Qwen3-4B-Base")
    ap.add_argument("--adapter", required=True, help="Path to adapter dir (contains adapter_model.safetensors)")
    ap.add_argument("--output", required=True, help="Where to write merged model")
    args = ap.parse_args()

    print(f"Loading base: {args.base} (bf16, CPU)...")
    base = AutoModelForCausalLM.from_pretrained(
        args.base,
        torch_dtype=torch.bfloat16,
        device_map={"": "cpu"},
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)

    print(f"Applying adapter: {args.adapter}")
    model = PeftModel.from_pretrained(base, args.adapter)

    print("Merging...")
    merged = model.merge_and_unload()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    print(f"Saving to {out}")
    merged.save_pretrained(out, safe_serialization=True, max_shard_size="4GB")
    tokenizer.save_pretrained(out)
    print(f"Done. Files: {sorted(p.name for p in out.iterdir())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
