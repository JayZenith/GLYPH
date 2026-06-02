#!/usr/bin/env python3
"""Generate churn traces from SFT_V1 on the TRAIN set, then surgically convert
them into solve-then-stop SFT rows.

The model's only residual failure is termination: it reaches a passing verifier,
then keeps calling tools to the round cap and never emits FINAL. SFT only ever
showed it the teacher's clean states, so "stop after a deep success on my OWN
messy trajectory" is missing from the distribution -- and RL can't reinforce a
behavior the policy never samples (see rl/RLVR_NOTES.md).

This script closes that gap by rejection-sampling the model's own behavior:
  1. run SFT_V1 over training prompts (tools execute for real),
  2. KEEP only rollouts that solved (terminal verifier success) but did NOT end
     cleanly (churned past success / no FINAL),
  3. truncate each at the FIRST verifier success and append one clean FINAL.

Outputs:
  --output-raw : every kept churn trace + metrics (for inspection)
  --output-sft : surgically-fixed rows in signal_*.jsonl schema (ready to add to
                 the SFT mix and retrain SFT_V1.5)

NOTE: generate on TRAIN prompts only. Do NOT point --rl-prompts at the held-out
69 -- that is the test set; training on it is contamination.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from sft.evals import generate, load_model
from sft.evals.scoring import score_output
from agent_runtime.rust.results import parse_call_blocks

VERIFIERS = {"cargo_test", "cargo_run"}

# One tool RESULT turn as emitted by sft/evals/generation.py: a tool block, then
# a fresh assistant opener. We cut after the closing <|im_end|> of the success
# block and reuse the assistant opener that follows.
_TOOL_BLOCK = re.compile(
    r"<\|im_start\|>tool\n(RESULT\s+([A-Za-z0-9_\-]+):\n.*?)\n<\|im_end\|>",
    re.DOTALL,
)

# Kind-aware FINAL body. The exact wording does not matter for training the stop
# token; keep it short and truthful to the verifier that passed.
_FINAL_BY_KIND = {
    "patch_test_pass": "FINAL: Tests pass.",
    "patch_test_recover": "FINAL: Tests pass after the fix.",
    "patch_run_pass": "FINAL: Program output matches expected.",
    "patch_run_recover": "FINAL: Program output matches expected after the fix.",
    "run_only": "FINAL: Program output matches expected.",
    "test_only": "FINAL: Tests pass.",
}
_FINAL_DEFAULT = "FINAL: Done."


def _assistant_call_tools(full_trace: str) -> dict[str, str]:
    """Map call id -> tool name across all assistant turns in the trace."""
    id_to_tool: dict[str, str] = {}
    for body in re.findall(
        r"<\|im_start\|>assistant\n(.*?)(?:<\|im_end\|>|<\|im_start\|>|\Z)",
        full_trace,
        re.DOTALL,
    ):
        for call in parse_call_blocks(body):
            id_to_tool[call["id"]] = call["tool"]
    return id_to_tool


def _first_verifier_success(full_trace: str):
    """Return the regex match for the FIRST passing cargo_test/cargo_run RESULT
    block, or None if no verifier ever passed (i.e. the task was never solved)."""
    id_to_tool = _assistant_call_tools(full_trace)
    for m in _TOOL_BLOCK.finditer(full_trace):
        body, call_id = m.group(1), m.group(2)
        if id_to_tool.get(call_id) in VERIFIERS and "status: success" in body:
            return m
    return None


def churn_match(full_trace: str):
    """Return the first-verifier-success match IFF this is a genuine
    solve-then-churn trace: a verifier passed, but the model then ran more tools
    and/or never emitted FINAL. None means either never-solved (a real task
    failure, not churn) or solved-and-stopped-cleanly (nothing to fix)."""
    m = _first_verifier_success(full_trace)
    if m is None:
        return None  # never solved -> not churn, a capability failure
    tail = full_trace[m.end():]
    churned = ("<|im_start|>tool" in tail) or ("FINAL:" not in full_trace)
    return m if churned else None


def truncate_at_first_success(full_trace: str, kind: str) -> str | None:
    """Cut the trace right after the first passing verifier RESULT and append one
    clean FINAL. Returns None if it is not a genuine solve-then-churn trace."""
    m = churn_match(full_trace)
    if m is None:
        return None
    head = full_trace[: m.end()]  # up to and including the success </im_end>
    final = _FINAL_BY_KIND.get(kind, _FINAL_DEFAULT)
    return f"{head}\n\n<|im_start|>assistant\n{final}\n<|im_end|>"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="JayZenith/SFT_V1")
    p.add_argument("--rl-prompts", default="synthetic_data/rl_prompts_v2_1323.jsonl",
                   help="TRAIN task prompts (prompt + blueprint_root/trace_prefix/expected_output).")
    p.add_argument("--cases-root", default="runs/rlvr1/rust_cases/churn_gen",
                   help="Where per-rollout sandboxes are materialized.")
    p.add_argument("--output-raw", default="synthetic_data/churn_traces_raw.jsonl")
    p.add_argument("--output-sft", default="synthetic_data/churn_fixed_sft.jsonl")
    p.add_argument("--temperature", type=float, default=0.0,
                   help="0 = greedy. Use ~0.8 to surface off-mode churn (greedy mostly stops cleanly).")
    p.add_argument("--samples-per-prompt", type=int, default=1,
                   help="Rollouts per prompt; keep every churn one. Use with --temperature>0.")
    p.add_argument("--max-new-tokens", type=int, default=4000)
    p.add_argument("--max-tool-rounds", type=int, default=15)
    p.add_argument("--tool-timeout", type=int, default=30)
    p.add_argument("--nsjail-path", default=None)
    p.add_argument("--limit", type=int, default=None, help="First N prompts only.")
    p.add_argument("--kinds", default=None,
                   help="Comma-separated kinds to keep (e.g. recover kinds), where churn lives.")
    args = p.parse_args()

    keep_kinds = set(args.kinds.split(",")) if args.kinds else None
    rows = [json.loads(line) for line in Path(args.rl_prompts).read_text().splitlines() if line.strip()]
    if keep_kinds:
        rows = [r for r in rows if r.get("kind") in keep_kinds]
    if args.limit is not None:
        rows = rows[: args.limit]

    print(f"Loading {args.model} ...")
    model, tok = load_model(args.model)

    sandbox_root = Path(args.cases_root) / "_sandboxes"
    raw_f = Path(args.output_raw).open("w")
    sft_f = Path(args.output_sft).open("w")
    n_seen = n_churn = n_fixed = 0
    try:
        for i, row in enumerate(rows):
            prompt = row["prompt"]
            kind = row.get("kind", "other")
            item = {
                "kind": kind,
                "expected_tool_sequence": row.get("expected_tool_sequence", []),
                "expected_output": row.get("expected_output"),
            }
            tags = []  # one per sample
            for _ in range(max(args.samples_per_prompt, 1)):
                out, n_tok = generate(
                    model, tok, prompt, args.max_new_tokens,
                    max_tool_rounds=args.max_tool_rounds,
                    temperature=args.temperature,
                    execution={
                        "blueprint_root": row.get("blueprint_root"),
                        "trace_prefix": row.get("trace_prefix"),
                        "sandbox_root": sandbox_root,
                        "timeout": args.tool_timeout,
                        "nsjail_path": args.nsjail_path,
                        "expected_output": row.get("expected_output"),
                    },
                )
                n_seen += 1
                metrics = score_output(prompt, out, item, n_tok, args.max_new_tokens)
                full_trace = prompt + out
                fixed = truncate_at_first_success(full_trace, kind)
                if fixed is not None:
                    n_churn += 1
                    n_fixed += 1
                    tags.append("churn")
                    raw_f.write(json.dumps({
                        "case_id": row.get("case_id"), "kind": kind,
                        "trace": full_trace, "metrics": metrics,
                    }) + "\n")
                    sft_f.write(json.dumps({
                        "trace": fixed,
                        "family": kind,
                        "case_id": row.get("case_id"),
                        "difficulty": row.get("difficulty"),
                        "expected_tool_sequence": row.get("expected_tool_sequence", []),
                        "expected_output": row.get("expected_output"),
                    }) + "\n")
                elif _first_verifier_success(full_trace) is None:
                    tags.append("unsolved")
                else:
                    tags.append("clean")
            n_c = tags.count("churn")
            print(f"[{i+1}/{len(rows)}] {row.get('case_id')} -> churn={n_c}/{len(tags)} {tags}",
                  flush=True)
    finally:
        raw_f.close()
        sft_f.close()

    print(f"\nseen={n_seen}  churn={n_churn}  fixed={n_fixed}")
    print(f"raw  -> {args.output_raw}")
    print(f"sft  -> {args.output_sft}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
