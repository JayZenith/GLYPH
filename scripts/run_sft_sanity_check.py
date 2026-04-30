#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from validator import validate_trace


PROMPTS = [
    {
        "name": "reasoning_no_tools",
        "user": "Explain whether a small coffee shop should open a second location now or wait six months, using a clear step-by-step plan and final recommendation.",
        "tools": [],
    },
    {
        "name": "tool_using_search",
        "user": "Find the latest CPU benchmark results for Ryzen 9 9950X and compare them to Intel Core Ultra 9 285K.",
        "tools": [
            {"name": "search_web", "description": "Search the web", "params": {"query": {"type": "string"}}},
            {"name": "fetch_page", "description": "Fetch a webpage", "params": {"url": {"type": "string"}}},
        ],
    },
    {
        "name": "long_horizon",
        "user": "Plan a 3-phase migration from a monolith to services for a 12-engineer startup. Include risks, order of operations, and checkpoints.",
        "tools": [
            {"name": "list_services", "description": "List candidate services", "params": {"system": {"type": "string"}}},
        ],
    },
    {
        "name": "error_recovery",
        "user": "Check the weather for Yosemite this weekend and tell me if hiking conditions look good.",
        "tools": [
            {"name": "get_weather", "description": "Fetch weather", "params": {"location": {"type": "string"}, "date": {"type": "string"}}},
        ],
    },
]


def build_prompt(user_message: str, tools: list[dict]) -> str:
    parts = [
        "<|im_start|>system",
        "system「You are a helpful AI assistant that completes tasks step by step.」🏷 sys1",
    ]
    for tool in tools:
        parts.append("tool {")
        parts.append(f"    name ↦ {tool['name']} •")
        if tool.get("description"):
            parts.append(f'    description ↦ "{tool["description"]}" •')
        if tool.get("params"):
            parts.append("    params ↦ {")
            for param_name, param_def in tool["params"].items():
                parts.append(f"        {param_name} ↦ {{ type ↦ {param_def['type']} }}")
            parts.append("    }")
        parts.append("}")
    parts.extend(
        [
            "<|im_end|>",
            "",
            "<|im_start|>user",
            f"user「{user_message}」🏷 usr1",
            "<|im_end|>",
            "",
            "<|im_start|>assistant",
        ]
    )
    return "\n".join(parts)


def load_model(model_path: str):
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            attn_implementation="flash_attention_2",
        )
    except Exception:
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            attn_implementation="sdpa",
        )
    model.eval()
    return model, tokenizer


def generate(model, tokenizer, prompt: str, max_new_tokens: int) -> str:
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    stop_ids = [tokenizer.eos_token_id]
    im_end_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
    if im_end_id != tokenizer.unk_token_id:
        stop_ids.append(im_end_id)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=stop_ids,
        )

    text = tokenizer.decode(outputs[0], skip_special_tokens=False)
    if "<|im_start|>assistant" in text:
        text = text.split("<|im_start|>assistant")[-1]
    if "<|im_end|>" in text:
        text = text.split("<|im_end|>")[0]
    return text.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    args = parser.parse_args()

    model, tokenizer = load_model(args.model)

    rows = []
    for item in PROMPTS:
        prompt = build_prompt(item["user"], item["tools"])
        output = generate(model, tokenizer, prompt, args.max_new_tokens)
        validation = validate_trace(prompt + output)
        rows.append(
            {
                "name": item["name"],
                "prompt": item["user"],
                "output": output,
                "valid_trace": validation.valid,
                "errors": validation.errors,
                "warnings": validation.warnings,
            }
        )

    Path(args.output).write_text(json.dumps(rows, indent=2))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
