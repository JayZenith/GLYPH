#!/usr/bin/env python3
"""Format-quality eval for the SFT model only."""
import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sft.evals import (
    assert_no_prompt_overlap,
    assert_prompt_similarity_below,
    build_prompt,
    generate,
    generate_batch,
    load_model,
    load_prompts,
    score_output,
    summarize,
)


_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _sanitize_stream_piece(piece: str) -> str:
    cleaned = _CONTROL_CHARS_RE.sub("", piece).replace("\ufffd", "")
    return "".join(ch for ch in cleaned if ch in "\n\r\t" or 32 <= ord(ch) <= 126)


def prepare_eval_items(items: list[dict], cases_root: Path) -> list[dict]:
    prepared: list[dict] = []
    for item in items:
        row = dict(item)
        if row.get("blueprint_root"):
            row["blueprint_root"] = str(row["blueprint_root"])
            row["trace_prefix"] = row.get("trace_prefix") or row["blueprint_root"]
        prepared.append(row)
    return prepared


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None


def _write_eval_payload(
    output: Path,
    args: argparse.Namespace,
    results: dict[str, list[dict]],
    n_prompts: int,
    commit: str | None,
) -> None:
    payload = {
        "run": {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": commit,
            "args": vars(args),
            "n_prompts": n_prompts,
        },
        "summary": {"sft": summarize("sft", results["sft"])},
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sft-model", required=True)
    parser.add_argument(
        "--sft-adapter",
        default=None,
        help="Optional PEFT adapter to load on top of --sft-model. Use this for RLVR LoRA checkpoints.",
    )
    parser.add_argument("--prompt-section", default="post_eval_heldout_150")
    parser.add_argument("--prompt-file", default=None,
                        help="Optional yaml file to load prompts from instead of the default heldout-150 prompt file")
    parser.add_argument("--train-data", required=True,
                        help="Train dataset JSONL used to reject exact eval prompt overlap")
    parser.add_argument("--max-prompt-similarity", type=float, default=None,
                        help="Optional legacy lexical prompt similarity hard-fail threshold")
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-new-tokens", type=int, default=6000)
    parser.add_argument("--max-tool-rounds", type=int, default=8,
                        help="Max rounds of real tool execution/result injection per prompt")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit to first N prompts (for smoke runs)")
    parser.add_argument("--cases-root", default="runs/heldout150_eval",
                        help="Root directory where held-out eval Rust cases are materialized")
    parser.add_argument("--tool-timeout", type=int, default=30)
    parser.add_argument("--stream-output", action="store_true",
                        help="Print each completed model output as soon as that prompt finishes")
    parser.add_argument("--stream-output-chars", type=int, default=0,
                        help="If > 0, truncate streamed output to this many chars")
    parser.add_argument("--token-stream", action="store_true",
                        help="Print generated text token-by-token as each prompt runs")
    parser.add_argument("--prompt-batch-size", type=int, default=1,
                        help="Number of eval prompts to generate together. Default 1 preserves legacy serial behavior.")
    parser.add_argument("--tool-workers", type=int, default=None,
                        help="Max parallel Rust tool executions in batched mode. Defaults to min(8, pending calls).")
    parser.add_argument("--no-resume", action="store_true",
                        help="Ignore an existing output JSON instead of skipping completed prompt names.")
    args = parser.parse_args()
    if args.prompt_batch_size < 1:
        raise ValueError("--prompt-batch-size must be >= 1")
    if args.token_stream and args.prompt_batch_size > 1:
        raise ValueError("--token-stream is only supported with --prompt-batch-size 1")

    print("Loading SFT model...")
    sft_model, sft_tok = load_model(args.sft_model, args.sft_adapter)

    prompts = load_prompts(args.prompt_section, args.prompt_file)
    prompts = prepare_eval_items(prompts, Path(args.cases_root))
    assert_no_prompt_overlap(prompts, args.train_data)
    if args.max_prompt_similarity is not None:
        assert_prompt_similarity_below(prompts, args.train_data, args.max_prompt_similarity)
    if args.limit is not None:
        prompts = prompts[:args.limit]
    output_path = Path(args.output)
    results = {"sft": []}
    prompt_names = {item["name"] for item in prompts}
    completed: set[str] = set()
    if output_path.exists() and not args.no_resume:
        existing = json.loads(output_path.read_text())
        results["sft"] = [
            row for row in existing.get("results", {}).get("sft", [])
            if row.get("name") in prompt_names
        ]
        completed = {row["name"] for row in results["sft"]}
        prompts = [item for item in prompts if item["name"] not in completed]
        print(f"resuming: {len(completed)} complete, {len(prompts)} remaining", flush=True)

    total_prompts = len(prompts) + len(completed)
    commit = _git_commit()
    for start in range(0, len(prompts), args.prompt_batch_size):
        batch = prompts[start:start + args.prompt_batch_size]
        batch_prompts = [build_prompt(item["user"], item.get("system")) for item in batch]
        batch_executions = [
            {
                "blueprint_root": item.get("blueprint_root"),
                "trace_prefix": item.get("trace_prefix"),
                "sandbox_root": Path(args.cases_root) / "_sandboxes",
                "timeout": args.tool_timeout,
                "expected_output": item.get("expected_output"),
            }
            for item in batch
        ]
        names = ", ".join(item["name"] for item in batch)
        print(f"Running batch {start + 1}-{start + len(batch)}/{len(prompts)} on sft: {names}")

        if args.prompt_batch_size == 1:
            item = batch[0]

            def make_token_callback() -> None:
                if not args.token_stream:
                    return None
                started = False

                def _cb(piece: str) -> None:
                    nonlocal started
                    if not started:
                        print(f"\n===== {item['name']} | sft =====\n", end="", flush=True)
                        started = True
                    cleaned = _sanitize_stream_piece(piece)
                    if cleaned:
                        print(cleaned, end="", flush=True)

                return _cb

            output_rows = [
                generate(
                    sft_model,
                    sft_tok,
                    batch_prompts[0],
                    args.max_new_tokens,
                    max_tool_rounds=args.max_tool_rounds,
                    token_callback=make_token_callback(),
                    execution=batch_executions[0],
                )
            ]
            if args.token_stream:
                print("\n", flush=True)
        else:
            output_rows = generate_batch(
                sft_model,
                sft_tok,
                batch_prompts,
                args.max_new_tokens,
                max_tool_rounds=args.max_tool_rounds,
                executions=batch_executions,
                tool_workers=args.tool_workers,
            )

        for item, prompt, (sft_out, sft_n) in zip(batch, batch_prompts, output_rows):
            if args.stream_output:
                shown = sft_out if args.stream_output_chars <= 0 else sft_out[:args.stream_output_chars]
                print(f"\n===== {item['name']} | sft =====\n{shown}\n", flush=True)
            results["sft"].append({
                "name": item["name"],
                "prompt": item["user"],
                "output": sft_out,
                "metrics": score_output(prompt, sft_out, item, sft_n, args.max_new_tokens),
            })
        _write_eval_payload(output_path, args, results, total_prompts, commit)

    if results["sft"]:
        _write_eval_payload(output_path, args, results, total_prompts, commit)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
