#!/usr/bin/env python3
"""vLLM-backed pass@k scan. Identical output schema to sft/passk_scan.py, but the
k rollouts of each prompt are driven as one batched, multi-turn generation through
a single vllm.LLM (continuous batching) with cargo executed for the k rollouts in
parallel. Same CALL/RESULT/FINAL protocol, same real cargo, same banding.

Use on a free GPU while RL trains, e.g. CUDA_VISIBLE_DEVICES=0.
"""
from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from sft.evals import build_prompt, load_prompts, score_output
from sft.eval_formal import prepare_eval_items
from sft.evals.prompt_loader import build_prompt as _bp  # noqa: F401  (keep parity)

from agent_runtime.protocol import assistant_text, extract_pending_call_ids, tool_text
from agent_runtime.rust.executor import create_executor
from agent_runtime.rust.results import format_result_block, parse_call_blocks
from agent_runtime.rust.runtime import (
    ensure_sandbox_copy,
    execute_rust_tool,
    rewrite_params_for_sandbox,
)


@dataclass
class Rollout:
    prompt: str
    blueprint_root: str | None
    trace_prefix: str | None
    sandbox_path: str | None
    remaining: int
    accumulated: str = ""
    new_tokens: int = 0
    done: bool = False
    cur_prompt: str = field(default="")

    def __post_init__(self) -> None:
        self.cur_prompt = self.prompt


def write_results(path: Path, results: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(results, indent=2))
    tmp.replace(path)


def _cargo_verifier_success(trace: str) -> bool:
    for _tool, call_id in re.findall(r'CALL\s+(cargo_run|cargo_test)\(.*?\bid\s*=\s*"([^"]+)"', trace, re.DOTALL):
        match = re.search(
            r"RESULT\s+" + re.escape(call_id) + r":\n(.*?)(?=\n<\|im_end\|>|\nRESULT\s+[A-Za-z0-9_\-]+:|\Z)",
            trace,
            re.DOTALL,
        )
        if match and re.search(r"^status:\s*success\b", match.group(1), re.MULTILINE):
            return True
    return False


def _exec_round(rollout: Rollout, executor, expected_output: str | None) -> bool:
    """Run pending tool calls for one rollout, inject results. Return True if the
    rollout should continue (had pending calls), False if it is finished."""
    full_trace = rollout.prompt + rollout.accumulated
    assistant = assistant_text(full_trace)
    tools = tool_text(full_trace)
    pending_ids = extract_pending_call_ids(assistant, tools)
    if not pending_ids:
        return False

    injections = []
    for call in parse_call_blocks(assistant):
        if call["id"] not in pending_ids:
            continue
        params = call["params"]
        if rollout.trace_prefix and rollout.sandbox_path:
            params = rewrite_params_for_sandbox(params, rollout.trace_prefix, rollout.sandbox_path)
        result = execute_rust_tool(
            executor,
            call["tool"],
            params,
            expected_output=expected_output if call["tool"] == "cargo_run" else None,
        )
        block = format_result_block(call["id"], result)
        injections.append(
            "\n\n<|im_start|>tool\n" f"{block}\n" "<|im_end|>\n\n<|im_start|>assistant\n"
        )
    if not injections:
        return False
    rollout.accumulated += "".join(injections)
    rollout.cur_prompt = rollout.prompt + rollout.accumulated
    return True


def run_prompt(llm, tokenizer, sampling_cls, item, k, max_new_tokens, max_tool_rounds,
               temperature, executor, sandbox_root, save_rollouts: bool = False):
    blueprint_root = item.get("blueprint_root")
    trace_prefix = item.get("trace_prefix") or blueprint_root
    expected_output = item.get("expected_output")
    prompt = build_prompt(item["user"], item.get("system"))
    stop_ids = [tokenizer.eos_token_id,
                tokenizer.convert_tokens_to_ids("<|im_end|>"),
                tokenizer.convert_tokens_to_ids("<|im_start|>")]

    rollouts: list[Rollout] = []
    for _ in range(k):
        sandbox_path = None
        if blueprint_root:
            _, sandbox_path = ensure_sandbox_copy(blueprint_root, Path(sandbox_root))
        rollouts.append(Rollout(prompt, blueprint_root, trace_prefix, sandbox_path, max_new_tokens))

    for _ in range(max_tool_rounds + 1):
        active = [r for r in rollouts if not r.done and r.remaining > 0]
        if not active:
            break
        params = [
            sampling_cls(
                n=1,
                temperature=temperature if temperature and temperature > 0 else 0.0,
                top_p=1.0,
                max_tokens=r.remaining,
                stop_token_ids=stop_ids,
            )
            for r in active
        ]
        token_prompts = [
            {"prompt_token_ids": tokenizer(r.cur_prompt, add_special_tokens=False)["input_ids"]}
            for r in active
        ]
        outs = llm.generate(token_prompts, params, use_tqdm=False)
        for r, out in zip(active, outs):
            comp = out.outputs[0]
            text = comp.text
            # vLLM strips the stop special token from the text; the protocol
            # parser needs <|im_end|> to close the assistant segment.
            if comp.finish_reason == "stop":
                text += "<|im_end|>"
            r.accumulated += text
            n = len(comp.token_ids)
            r.new_tokens += n
            r.remaining -= n

        # execute cargo for the active rollouts in parallel, mark finished ones
        with ThreadPoolExecutor(max_workers=len(active)) as pool:
            cont = list(pool.map(lambda r: _exec_round(r, executor, expected_output), active))
        for r, keep_going in zip(active, cont):
            if not keep_going:
                r.done = True

    cargo_solves = 0
    valid_solves = 0
    rollout_rows = []
    for r in rollouts:
        trace = r.prompt + r.accumulated.strip()
        m = score_output(r.prompt, r.accumulated.strip(), item, r.new_tokens, max_new_tokens)
        cargo_success = _cargo_verifier_success(trace)
        valid_trace = bool(m["valid_trace"]) and cargo_success
        cargo_solves += int(cargo_success)
        valid_solves += int(valid_trace)
        if save_rollouts:
            rollout_rows.append({
                "cargo_verifier_success": cargo_success,
                "terminal_tool_success_metric": bool(m["terminal_tool_success"]),
                "valid_trace": valid_trace,
                "clean_end": bool(m["clean_end"]),
                "call_sequence": m["call_sequence"],
                "new_tokens": r.new_tokens,
                "trace": trace,
            })
    return cargo_solves, valid_solves, rollout_rows


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sft-model", default="JayZenith/SFT_V1")
    p.add_argument("--prompt-file", default="sft/evals/eval_prompts_heldout_69.yaml")
    p.add_argument("--prompt-section", default="post_eval_heldout_69")
    p.add_argument("--cases-root", default="runs/rlvr1/rust_cases/eval_heldout_69")
    p.add_argument("--names", default=None, help="Comma-separated prompt names to keep.")
    p.add_argument("-k", "--samples", type=int, default=8)
    p.add_argument("--temperature", type=float, default=0.8)
    p.add_argument("--max-new-tokens", type=int, default=4000)
    p.add_argument("--max-tool-rounds", type=int, default=15)
    p.add_argument("--tool-timeout", type=int, default=30)
    p.add_argument("--output", default="results/passk_failed.json")
    p.add_argument("--no-resume", action="store_true")
    p.add_argument("--gpu-memory-utilization", type=float, default=0.85)
    p.add_argument("--max-model-len", type=int, default=12288)
    p.add_argument("--dtype", default="bfloat16")
    p.add_argument("--save-rollouts", action="store_true",
                   help="Store per-rollout traces and strict cargo-verifier metrics.")
    args = p.parse_args()

    keep = set(args.names.split(",")) if args.names else None

    prompts = load_prompts(args.prompt_section, args.prompt_file)
    prompts = prepare_eval_items(prompts, Path(args.cases_root))
    if keep:
        prompts = [p_ for p_ in prompts if p_["name"] in keep]

    output_path = Path(args.output)
    results: list[dict] = []
    completed: set[str] = set()
    if output_path.exists() and not args.no_resume:
        results = json.loads(output_path.read_text())
        completed = {r["name"] for r in results}
        prompts = [p_ for p_ in prompts if p_["name"] not in completed]
        print(f"resuming: {len(completed)} complete, {len(prompts)} remaining", flush=True)

    total = len(prompts) + len(completed)
    print(f"{len(prompts)} prompts remaining ({total} total), k={args.samples} @ T={args.temperature}",
          flush=True)

    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams

    tokenizer = AutoTokenizer.from_pretrained(args.sft_model, trust_remote_code=True)
    llm = LLM(
        model=args.sft_model,
        dtype=args.dtype,
        gpu_memory_utilization=args.gpu_memory_utilization,
        max_model_len=args.max_model_len,
        trust_remote_code=True,
        enforce_eager=False,
    )
    executor = create_executor(timeout=args.tool_timeout)
    sandbox_root = Path(args.cases_root) / "_sandboxes"

    for i, item in enumerate(prompts):
        cargo_solves, valid_solves, rollout_rows = run_prompt(
            llm, tokenizer, SamplingParams, item, args.samples, args.max_new_tokens,
            args.max_tool_rounds, args.temperature, executor, sandbox_root, args.save_rollouts,
        )
        band = "rlvr-target" if 0 < cargo_solves < args.samples else ("solved" if cargo_solves else "capability-gap")
        row = {"name": item["name"], "solves": cargo_solves, "k": args.samples,
               "pass_at_k": cargo_solves / args.samples, "band": band,
               "solve_metric": "cargo_verifier_success",
               "cargo_solves": cargo_solves,
               "cargo_pass_at_k": cargo_solves / args.samples,
               "valid_trace_solves": valid_solves,
               "valid_trace_pass_at_k": valid_solves / args.samples}
        if args.save_rollouts:
            row["rollouts"] = rollout_rows
        results.append(row)
        write_results(output_path, results)
        done = len(completed) + i + 1
        print(
            f"[{done}/{total}] {item['name']} -> cargo {cargo_solves}/{args.samples}, "
            f"valid {valid_solves}/{args.samples} {band}",
            flush=True,
        )

    write_results(output_path, results)
    tgt = sum(r["band"] == "rlvr-target" for r in results)
    print(f"\nrlvr-targets: {tgt}  capability-gap: "
          f"{sum(r['band']=='capability-gap' for r in results)}  solved: "
          f"{sum(r['band']=='solved' for r in results)}")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
