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
    {
        "name": "tool_plan_followthrough",
        "user": "Audit a CSV export for duplicate user IDs and tell me what cleanup steps to take.",
        "tools": [
            {"name": "load_csv", "description": "Load CSV", "params": {"path": {"type": "string"}}},
            {"name": "find_duplicates", "description": "Find duplicate values", "params": {"column": {"type": "string"}}},
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

    response = tokenizer.decode(outputs[0], skip_special_tokens=False)
    if "<|im_start|>assistant" in response:
        response = response.split("<|im_start|>assistant")[-1]
    if "<|im_end|>" in response:
        response = response.split("<|im_end|>")[0]
    return response.strip()


def score_output(prompt_text: str, output_text: str, tools: list[dict]) -> dict:
    full_trace = prompt_text + output_text
    validation = validate_trace(full_trace)
    metrics = {
        "valid_trace": validation.valid,
        "warning_count": len(validation.warnings),
        "error_count": len(validation.errors),
        "has_plan": "plan {" in output_text,
        "has_act": "act {" in output_text,
        "has_response": "response「" in output_text or "response\"" in output_text,
        "has_result": "result {" in output_text,
        "has_tool_call": "call ↦ {" in output_text,
        "has_think_block": "think ↦" in output_text,
        "raw_chars": len(output_text),
    }
    if tools:
        tool_names = [tool["name"] for tool in tools]
        metrics["mentions_any_tool_name"] = any(name in output_text for name in tool_names)
    else:
        metrics["mentions_any_tool_name"] = False

    score = 0
    score += 3 if metrics["valid_trace"] else 0
    score += 1 if metrics["has_plan"] else 0
    score += 1 if metrics["has_act"] else 0
    score += 1 if metrics["has_response"] else 0
    score += 1 if (metrics["has_tool_call"] if tools else metrics["has_think_block"]) else 0
    metrics["score"] = score
    metrics["validation_errors"] = validation.errors
    metrics["validation_warnings"] = validation.warnings
    return metrics


def summarize(name: str, rows: list[dict]) -> dict:
    total = len(rows)
    return {
        "model": name,
        "num_prompts": total,
        "valid_traces": sum(1 for row in rows if row["metrics"]["valid_trace"]),
        "avg_score": sum(row["metrics"]["score"] for row in rows) / total,
        "has_plan_rate": sum(1 for row in rows if row["metrics"]["has_plan"]) / total,
        "has_response_rate": sum(1 for row in rows if row["metrics"]["has_response"]) / total,
        "has_tool_call_rate": sum(1 for row in rows if row["metrics"]["has_tool_call"]) / total,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--sft-model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-new-tokens", type=int, default=320)
    args = parser.parse_args()

    print("Loading base model...")
    base_model, base_tok = load_model(args.base_model)
    print("Loading SFT model...")
    sft_model, sft_tok = load_model(args.sft_model)

    results = {"base": [], "sft": []}
    for item in PROMPTS:
        prompt = build_prompt(item["user"], item["tools"])

        print(f"Running {item['name']} on base...")
        base_out = generate(base_model, base_tok, prompt, args.max_new_tokens)
        results["base"].append(
            {
                "name": item["name"],
                "prompt": item["user"],
                "output": base_out,
                "metrics": score_output(prompt, base_out, item["tools"]),
            }
        )

        print(f"Running {item['name']} on sft...")
        sft_out = generate(sft_model, sft_tok, prompt, args.max_new_tokens)
        results["sft"].append(
            {
                "name": item["name"],
                "prompt": item["user"],
                "output": sft_out,
                "metrics": score_output(prompt, sft_out, item["tools"]),
            }
        )

    payload = {
        "summary": {
            "base": summarize("base", results["base"]),
            "sft": summarize("sft", results["sft"]),
        },
        "results": results,
    }
    Path(args.output).write_text(json.dumps(payload, indent=2))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
