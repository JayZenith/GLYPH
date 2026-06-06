#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sft.eval_formal import prepare_eval_items
from sft.evals import (
    assert_no_prompt_overlap,
    build_prompt,
    generate,
    load_model,
    load_prompts,
    score_output,
    summarize,
)


DEFAULT_CANARY_NAMES = [
    # Common SFT/RLVR missing-FINAL failures.
    "eval100_040_patch_test_recover_006_route_action_enum_branch_recovery",
    "eval100_071_patch_run_recover_007_layered_flags_cli_precedence_recover",
    "eval100_022_patch_run_pass_003_department_report_filters_zero_and_formats_top",
    # SFT missing-FINAL but RLVR fixed once.
    "eval100_047_patch_test_recover_013_collect_visible_tags_skip_empty_and_keep_order",
    # RLVR-regressed missing-FINAL case.
    "eval100_051_patch_test_recover_017_csv_record_required_key_recovery",
    # Normal passing sanity case.
    "eval100_024_patch_run_pass_005_active_tags_filter_map_join",
]

CALL_RE = re.compile(r"CALL\s+([A-Za-z_]\w*)\(.*?\bid=\"([^\"]+)\"", re.DOTALL)
RESULT_RE = re.compile(r"RESULT\s+([^:]+):\nstatus:\s*(\w+)", re.MULTILINE)
VERIFIERS = {"cargo_test", "cargo_run"}


def _latest_step(weights_root: Path) -> Path:
    candidates = [
        path for path in weights_root.glob("step_*")
        if path.is_dir() and (path / "config.json").exists()
    ]
    if not candidates:
        raise FileNotFoundError(f"No step_* model dirs under {weights_root}")
    return max(candidates, key=lambda path: int(path.name.removeprefix("step_")))


def _select_prompts(items: list[dict], names: list[str]) -> list[dict]:
    by_name = {item["name"]: item for item in items}
    missing = [name for name in names if name not in by_name]
    if missing:
        raise KeyError(f"Canary prompt(s) not found: {missing}")
    return [dict(by_name[name]) for name in names]


def _empty_assistant_after_result(output: str) -> bool:
    return bool(
        re.search(
            r"<\|im_start\|>tool\nRESULT [\s\S]*<\|im_end\|>\s*<\|im_start\|>assistant\s*$",
            output,
        )
    )


def _tool_calls_after_successful_verifier(output: str) -> int:
    calls = CALL_RE.findall(output)
    result_status = {call_id: status for call_id, status in RESULT_RE.findall(output)}
    success_idx: int | None = None
    for idx, (tool, call_id) in enumerate(calls):
        if tool in VERIFIERS and result_status.get(call_id) == "success":
            success_idx = idx
            break
    if success_idx is None:
        return 0
    return sum(1 for _, call_id in calls[success_idx + 1 :] if call_id in result_status)


def _aggregate_canary(rows: list[dict], max_tool_rounds: int) -> dict:
    total = len(rows)
    if total == 0:
        return {}
    return {
        "num_prompts": total,
        "valid_trace": sum(r["metrics"]["valid_trace"] for r in rows),
        "has_final": sum(r["metrics"]["has_final"] for r in rows),
        "empty_assistant_after_result": sum(r["canary"]["empty_assistant_after_result"] for r in rows),
        "tool_calls_after_successful_verifier": sum(
            r["canary"]["tool_calls_after_successful_verifier"] for r in rows
        ),
        "terminal_tool_success": sum(r["metrics"]["terminal_tool_success"] for r in rows),
        "max_tool_rounds_hit": sum(
            len(r["metrics"]["call_sequence"]) >= max_tool_rounds + 1 for r in rows
        ),
    }


def _jsonable_args(args: argparse.Namespace) -> dict:
    out = vars(args).copy()
    for key, value in list(out.items()):
        if isinstance(value, Path):
            out[key] = str(value)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a tiny heldout canary eval for RL checkpoints.")
    parser.add_argument("--model", help="Model repo/path to evaluate.")
    parser.add_argument("--weights-root", type=Path,
                        help="If set, evaluate the latest step_* model directory under this root.")
    parser.add_argument("--train-data", default="synthetic_data/signal_1062.jsonl")
    parser.add_argument("--prompt-file", default="sft/evals/eval_prompts_heldout_69.yaml")
    parser.add_argument("--prompt-section", default="post_eval_heldout_69")
    parser.add_argument(
        "--names",
        nargs="*",
        default=None,
        help="Prompt names to evaluate. Omit to use the default heldout canary names; pass with no values to evaluate the full selected prompt section.",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-new-tokens", type=int, default=4000)
    parser.add_argument("--max-tool-rounds", type=int, default=15)
    parser.add_argument("--cases-root", default="runs/rlvr1/rust_cases/eval_canary")
    parser.add_argument("--tool-timeout", type=int, default=30)
    parser.add_argument("--nsjail-path", default=None)
    parser.add_argument("--min-exact-call-syntax-rate", type=float, default=1.0)
    parser.add_argument("--min-valid-traces", type=int, default=1)
    args = parser.parse_args()

    model_path = args.model
    if args.weights_root:
        model_path = str(_latest_step(args.weights_root))
    if not model_path:
        raise ValueError("Pass --model or --weights-root")

    prompts = load_prompts(args.prompt_section, args.prompt_file)
    if args.names == []:
        prompts = [dict(item) for item in prompts]
    else:
        prompts = _select_prompts(prompts, args.names or DEFAULT_CANARY_NAMES)
    prompts = prepare_eval_items(prompts, Path(args.cases_root))
    assert_no_prompt_overlap(prompts, args.train_data)

    model, tokenizer = load_model(model_path)
    rows = []
    for item in prompts:
        prompt = build_prompt(item["user"], item.get("system"))
        print(f"Running canary {item['name']}...")
        output, new_tokens = generate(
            model,
            tokenizer,
            prompt,
            args.max_new_tokens,
            max_tool_rounds=args.max_tool_rounds,
            execution={
                "blueprint_root": item.get("blueprint_root"),
                "trace_prefix": item.get("trace_prefix"),
                "sandbox_root": Path(args.cases_root) / "_sandboxes",
                "timeout": args.tool_timeout,
                "nsjail_path": args.nsjail_path,
                "expected_output": item.get("expected_output"),
            },
        )
        metrics = score_output(prompt, output, item, new_tokens, args.max_new_tokens)
        rows.append(
            {
                "name": item["name"],
                "kind": item.get("kind"),
                "metrics": metrics,
                "canary": {
                    "empty_assistant_after_result": _empty_assistant_after_result(output),
                    "tool_calls_after_successful_verifier": _tool_calls_after_successful_verifier(output),
                },
                "output": output,
            }
        )

    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        commit = None

    payload = {
        "run": {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": commit,
            "model": model_path,
            "args": _jsonable_args(args),
        },
        "summary": {
            "formal": summarize("canary", [{"metrics": row["metrics"]} for row in rows]),
            "canary": _aggregate_canary(rows, args.max_tool_rounds),
        },
        "results": rows,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {output_path}")
    formal = payload["summary"]["formal"]
    failures = []
    if formal.get("exact_call_syntax_rate", 0.0) < args.min_exact_call_syntax_rate:
        failures.append(
            f"exact_call_syntax_rate={formal.get('exact_call_syntax_rate', 0.0):.4f} "
            f"< {args.min_exact_call_syntax_rate:.4f}"
        )
    if formal.get("valid_traces", 0) < args.min_valid_traces:
        failures.append(f"valid_traces={formal.get('valid_traces', 0)} < {args.min_valid_traces}")
    if failures:
        print("Canary failed: " + "; ".join(failures), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
