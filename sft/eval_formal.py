#!/usr/bin/env python3
"""Format-quality eval. Loads base + sft, generates on each prompt, scores
with the validator, writes JSON.

Run: python -m sft.eval_formal --base-model ... --sft-model ... --output ...
"""
import argparse
import json
from pathlib import Path

from sft.evals import (
    build_prompt,
    generate,
    load_model,
    load_prompts,
    score_output,
    summarize,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--sft-model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-new-tokens", type=int, default=6000)
    parser.add_argument("--max-tool-rounds", type=int, default=4,
                        help="Max rounds of mocked-tool-result injection per prompt")
    args = parser.parse_args()

    print("Loading base model...")
    base_model, base_tok = load_model(args.base_model)
    print("Loading SFT model...")
    sft_model, sft_tok = load_model(args.sft_model)

    prompts = load_prompts("formal_eval")
    results = {"base": [], "sft": []}
    for item in prompts:
        prompt = build_prompt(item["user"], item.get("tools", []))
        tools = item.get("tools", [])

        print(f"Running {item['name']} on base...")
        base_out, base_n = generate(base_model, base_tok, prompt, args.max_new_tokens, max_tool_rounds=args.max_tool_rounds)
        results["base"].append({
            "name": item["name"],
            "prompt": item["user"],
            "output": base_out,
            "metrics": score_output(prompt, base_out, tools, base_n, args.max_new_tokens),
        })

        print(f"Running {item['name']} on sft...")
        sft_out, sft_n = generate(sft_model, sft_tok, prompt, args.max_new_tokens, max_tool_rounds=args.max_tool_rounds)
        results["sft"].append({
            "name": item["name"],
            "prompt": item["user"],
            "output": sft_out,
            "metrics": score_output(prompt, sft_out, tools, sft_n, args.max_new_tokens),
        })

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
