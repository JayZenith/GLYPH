#!/usr/bin/env python3
"""pass@k scan: how often does the model SOLVE (terminal verifier success) each
prompt under sampling? Identifies RLVR-addressable cases: 0 < pass@k < 1 means
the model solves it sometimes -> there is gradient for RL to push the rate up.
pass@k == 0 is a capability gap RL can't cross; == 1 is already solved.

Measure-only on the held-out 69 (we do NOT train on these). Use --names to
restrict to the cases SFT_V1 failed on.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sft.evals import generate, load_model, load_prompts
from sft.evals.scoring import score_output
from sft.eval_formal import prepare_eval_items
from sft.evals.prompt_loader import build_prompt


def write_results(path: Path, results: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(results, indent=2))
    tmp.replace(path)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sft-model", default="JayZenith/SFT_V1")
    p.add_argument("--prompt-file", default="sft/evals/eval_prompts_heldout_69.yaml")
    p.add_argument("--prompt-section", default="post_eval_heldout_69")
    p.add_argument("--cases-root", default="runs/rlvr1/rust_cases/eval_heldout_69")
    p.add_argument("--names", default=None, help="Comma-separated prompt names to keep.")
    p.add_argument("--names-from", default=None,
                   help="eval_formal JSON; keep only its non-valid (failed) prompts.")
    p.add_argument("-k", "--samples", type=int, default=8)
    p.add_argument("--temperature", type=float, default=0.8)
    p.add_argument("--max-new-tokens", type=int, default=4000)
    p.add_argument("--max-tool-rounds", type=int, default=15)
    p.add_argument("--tool-timeout", type=int, default=30)
    p.add_argument("--output", default="results/passk_failed.json")
    p.add_argument("--no-resume", action="store_true",
                   help="Ignore an existing output JSON instead of skipping completed prompt names.")
    p.add_argument("--skip-bands", default=None,
                   help="Comma-separated existing-output bands to omit from the scan on resume, e.g. solved.")
    args = p.parse_args()

    keep = None
    if args.names:
        keep = set(args.names.split(","))
    elif args.names_from:
        d = json.load(open(args.names_from))
        rows = d["results"][next(iter(d["results"]))]
        keep = {r["name"] for r in rows if not r["metrics"]["valid_trace"]}

    prompts = load_prompts(args.prompt_section, args.prompt_file)
    prompts = prepare_eval_items(prompts, Path(args.cases_root))
    if keep:
        prompts = [p_ for p_ in prompts if p_["name"] in keep]

    output_path = Path(args.output)
    results = []
    completed: set[str] = set()
    skip_bands = set(args.skip_bands.split(",")) if args.skip_bands else None
    if output_path.exists() and not args.no_resume:
        results = json.loads(output_path.read_text())
        if skip_bands:
            results = [r for r in results if r.get("band") not in skip_bands]
            write_results(output_path, results)
        completed = {r["name"] for r in results}
        prompts = [p_ for p_ in prompts if p_["name"] not in completed]
        print(f"resuming from {args.output}: {len(completed)} complete, {len(prompts)} remaining",
              flush=True)

    total = len(prompts) + len(completed)
    print(f"{len(prompts)} prompts remaining ({total} total), k={args.samples} @ T={args.temperature}",
          flush=True)

    model, tok = load_model(args.sft_model)
    sandbox_root = Path(args.cases_root) / "_sandboxes"
    for i, item in enumerate(prompts):
        prompt = build_prompt(item["user"], item.get("system"))
        solves = 0
        for _ in range(args.samples):
            out, n = generate(
                model, tok, prompt, args.max_new_tokens,
                max_tool_rounds=args.max_tool_rounds, temperature=args.temperature,
                execution={
                    "blueprint_root": item.get("blueprint_root"),
                    "trace_prefix": item.get("trace_prefix"),
                    "sandbox_root": sandbox_root,
                    "timeout": args.tool_timeout,
                    "expected_output": item.get("expected_output"),
                },
            )
            m = score_output(prompt, out, item, n, args.max_new_tokens)
            solves += int(bool(m["terminal_tool_success"]))
        rate = solves / args.samples
        band = "rlvr-target" if 0 < solves < args.samples else ("solved" if solves else "capability-gap")
        results.append({"name": item["name"], "solves": solves, "k": args.samples, "pass_at_k": rate, "band": band})
        write_results(output_path, results)
        done = len(completed) + i + 1
        print(f"[{done}/{total}] {item['name']} -> {solves}/{args.samples} {band}", flush=True)

    write_results(output_path, results)
    tgt = [r for r in results if r["band"] == "rlvr-target"]
    print(f"\nrlvr-targets (0<pass<k): {len(tgt)}  capability-gap: "
          f"{sum(r['band']=='capability-gap' for r in results)}  solved: "
          f"{sum(r['band']=='solved' for r in results)}")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
