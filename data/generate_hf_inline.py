#!/usr/bin/env python3
"""Generate TASK traces with a local HF model. Run: python -m data.generate_hf_inline"""
import argparse
import json
import random
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from data.generate import DOMAINS, EXAMPLE_TRACE, INLINE_TRACE_PROMPT, TRACE_SYSTEM_PROMPT
from core.validator import validate_trace


def build_messages(domain: str, has_tools: bool, has_follow_ups: bool, num_steps: int, include_error: bool):
    follow_up_instruction = (
        """
6. Then for each follow-up: user message (usr2, usr3...) → new plan → more act phases → response
   - Each turn should have its own plan that references the prior context
   - Continue numbering todos across turns or start fresh per turn
   - Final response should wrap up the entire conversation
"""
        if has_follow_ups
        else ""
    )
    error_instruction = "Include a realistic tool error and recovery." if include_error else ""
    prompt = INLINE_TRACE_PROMPT.format(
        domain=domain,
        has_tools=has_tools,
        has_follow_ups=has_follow_ups,
        num_steps=num_steps,
        include_error=include_error,
        follow_up_instruction=follow_up_instruction,
        error_instruction=error_instruction,
    )
    return [
        {"role": "system", "content": TRACE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Here's an example trace:\n\n{EXAMPLE_TRACE}"},
        {"role": "assistant", "content": "I understand the TASK format. I'll generate traces following this exact syntax."},
        {"role": "user", "content": prompt},
    ]


def main():
    parser = argparse.ArgumentParser(description="Generate TASK traces with a local HF model.")
    parser.add_argument("--model", default="mistralai/Mistral-Small-24B-Instruct-2501")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--output", default="traces.hf.jsonl")
    parser.add_argument("--max-new-tokens", type=int, default=4096)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--min-steps", type=int, default=5)
    parser.add_argument("--max-steps", type=int, default=18)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    valid = 0
    with output_path.open("a") as f:
        for i in range(args.count):
            has_tools = random.random() > 0.2
            has_follow_ups = random.random() < 0.3
            include_error = has_tools and random.random() < 0.2
            num_steps = random.randint(args.min_steps, args.max_steps)
            domain = random.choice(DOMAINS)
            messages = build_messages(domain, has_tools, has_follow_ups, num_steps, include_error)
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(text, return_tensors="pt").to(model.device)
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=args.max_new_tokens,
                    temperature=args.temperature,
                    top_p=args.top_p,
                    do_sample=True,
                    pad_token_id=tokenizer.eos_token_id,
                )
            gen = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
            validation = validate_trace(gen)
            if validation.valid:
                valid += 1
                f.write(json.dumps({"trace": gen}) + "\n")
                f.flush()
                print(f"[{i + 1}/{args.count}] valid")
            else:
                print(f"[{i + 1}/{args.count}] invalid: {validation.errors[:2]}")

    print(f"done: {valid}/{args.count} valid -> {output_path}")


if __name__ == "__main__":
    main()
