#!/usr/bin/env python3
"""Format-quality eval. Run: python -m sft.eval_formal [flags]"""
import argparse
import json
import re
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from core.validator import validate_trace
from sft.evals import build_prompt, load_prompts


REPETITION_PATTERN = re.compile(r"(.{20,200}?)\1{4,}", re.DOTALL)
CALL_ID_PATTERN = re.compile(r"call\s*↦\s*\{[^}]*?id\s*↦\s*([\w\"\-]+)", re.DOTALL)
ACT_BLOCK_END = re.compile(r"act\s*\{[^}]*\}\s*$", re.DOTALL)


def extract_pending_call_ids(text: str) -> list[str]:
    """Find call ids in the latest act block that don't yet have a matching result."""
    call_ids = CALL_ID_PATTERN.findall(text)
    result_ids = re.findall(r"result\s*\{[^}]*?\}\s*🏷\s*([\w\"\-]+)", text, re.DOTALL)
    result_ids += re.findall(r'data\s*↦\s*[^🏷]*🏷\s*([\w\"\-]+)', text, re.DOTALL)
    pending = [cid.strip('"') for cid in call_ids if cid.strip('"') not in {r.strip('"') for r in result_ids}]
    return pending


def inject_mock_result(call_id: str) -> str:
    return f'\n\nresult {{\n    data ↦ "Mocked tool result for {call_id}." 🏷 {call_id}\n}}\n\n'




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


def _generate_once(model, tokenizer, prompt: str, max_new_tokens: int) -> tuple[str, int, bool]:
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    input_len = inputs["input_ids"].shape[1]
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

    new_token_count = outputs.shape[1] - input_len
    last_tok = outputs[0, -1].item()
    hit_stop = last_tok in stop_ids
    text = tokenizer.decode(outputs[0, input_len:], skip_special_tokens=False)
    if "<|im_end|>" in text:
        text = text.split("<|im_end|>")[0]
    return text, new_token_count, hit_stop


def generate(model, tokenizer, prompt: str, max_new_tokens: int, max_tool_rounds: int = 4) -> tuple[str, int]:
    """Multi-round generation that injects mocked tool results when the model calls a tool."""
    accumulated = ""
    total_new_tokens = 0
    remaining = max_new_tokens
    cur_prompt = prompt
    for _ in range(max_tool_rounds + 1):
        if remaining <= 0:
            break
        chunk, n_tok, hit_stop = _generate_once(model, tokenizer, cur_prompt, remaining)
        accumulated += chunk
        total_new_tokens += n_tok
        remaining -= n_tok
        pending = extract_pending_call_ids(accumulated)
        if hit_stop and not pending:
            break
        if not pending:
            break
        injection = "".join(inject_mock_result(cid) for cid in pending)
        accumulated += injection
        cur_prompt = prompt + accumulated
    return accumulated.strip(), total_new_tokens


def score_output(
    prompt_text: str,
    output_text: str,
    tools: list[dict],
    new_token_count: int,
    max_new_tokens: int,
) -> dict:
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

    metrics["no_repetition"] = REPETITION_PATTERN.search(output_text) is None
    last_resp = output_text.rfind("response「")
    last_close = output_text.rfind("」")
    tail = output_text[last_close + 1 :].strip() if last_close >= 0 else ""
    tail_ok = bool(re.fullmatch(r"[\s※⊨𝑝🏷•\[\]\w\d\.\-\"']*", tail))
    metrics["ends_with_response"] = last_resp >= 0 and last_close > last_resp and tail_ok
    metrics["not_truncated"] = new_token_count < max_new_tokens - 10
    metrics["new_token_count"] = new_token_count

    score = 0
    score += 3 if metrics["valid_trace"] and metrics["no_repetition"] else 0
    score += 1 if metrics["has_plan"] else 0
    score += 1 if metrics["has_response"] and metrics["ends_with_response"] else 0
    score += 1 if (metrics["has_tool_call"] if tools else metrics["has_think_block"]) else 0
    score += 1 if metrics["not_truncated"] else 0
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
        "no_repetition_rate": sum(1 for row in rows if row["metrics"]["no_repetition"]) / total,
        "ends_with_response_rate": sum(1 for row in rows if row["metrics"]["ends_with_response"]) / total,
        "not_truncated_rate": sum(1 for row in rows if row["metrics"]["not_truncated"]) / total,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--sft-model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-new-tokens", type=int, default=6000)
    args = parser.parse_args()

    print("Loading base model...")
    base_model, base_tok = load_model(args.base_model)
    print("Loading SFT model...")
    sft_model, sft_tok = load_model(args.sft_model)

    prompts = load_prompts("formal_eval")
    results = {"base": [], "sft": []}
    for item in prompts:
        prompt = build_prompt(item["user"], item.get("tools", []))

        print(f"Running {item['name']} on base...")
        base_out, base_n = generate(base_model, base_tok, prompt, args.max_new_tokens)
        results["base"].append(
            {
                "name": item["name"],
                "prompt": item["user"],
                "output": base_out,
                "metrics": score_output(prompt, base_out, item.get("tools", []), base_n, args.max_new_tokens),
            }
        )

        print(f"Running {item['name']} on sft...")
        sft_out, sft_n = generate(sft_model, sft_tok, prompt, args.max_new_tokens)
        results["sft"].append(
            {
                "name": item["name"],
                "prompt": item["user"],
                "output": sft_out,
                "metrics": score_output(prompt, sft_out, item.get("tools", []), sft_n, args.max_new_tokens),
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
