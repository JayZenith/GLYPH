#!/usr/bin/env python3
"""Format-quality eval. Loads SFT (and optionally base), generates on each
prompt, scores with the validator, writes JSON.

Run: python -m sft.eval_formal --output ... [--include-base] [--limit N]
"""
import argparse
import json
import subprocess
from datetime import datetime, timezone
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
    parser.add_argument("--base-model", default="Qwen/Qwen3-4B-Base")
    parser.add_argument("--sft-model", default="JayZenith/glyph-sft-v1")
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-new-tokens", type=int, default=6000)
    parser.add_argument("--max-tool-rounds", type=int, default=4,
                        help="Max rounds of mocked-tool-result injection per prompt")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit to first N prompts (for smoke runs)")
    parser.add_argument("--include-base", action="store_true",
                        help="Also evaluate the base model (default off; base output is fixed across ablations)")
    args = parser.parse_args()

    if args.include_base:
        print("Loading base model...")
        base_model, base_tok = load_model(args.base_model)
    print("Loading SFT model...")
    sft_model, sft_tok = load_model(args.sft_model)

    prompts = load_prompts("formal_eval")
    if args.limit is not None:
        prompts = prompts[:args.limit]
    results = {"sft": []}
    if args.include_base:
        results["base"] = []
    for item in prompts:
        prompt = build_prompt(item["user"], item.get("tools", []))
        tools = item.get("tools", [])

        if args.include_base:
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

    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        commit = None

    summary = {"sft": summarize("sft", results["sft"])}
    if args.include_base:
        summary["base"] = summarize("base", results["base"])

    payload = {
        "run": {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": commit,
            "args": vars(args),
            "n_prompts": len(prompts),
        },
        "summary": summary,
        "results": results,
    }
    Path(args.output).write_text(json.dumps(payload, indent=2))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
