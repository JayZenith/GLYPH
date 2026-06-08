"""Post-train generation helper for the simplified CALL/RESULT/FINAL eval."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Thread

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

from agent_runtime.protocol import assistant_text, extract_pending_call_ids, tool_text
from agent_runtime.rust.executor import create_executor
from agent_runtime.rust.results import format_result_block, parse_call_blocks
from agent_runtime.rust.runtime import ensure_sandbox_copy, execute_rust_tool, rewrite_params_for_sandbox


def load_model(model_path: str):
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            attn_implementation="flash_attention",
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


def _generate_once(model, tokenizer, prompt: str, max_new_tokens: int, token_callback=None,
                   temperature: float | None = None) -> tuple[str, int, bool]:
    inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(model.device)
    input_len = inputs["input_ids"].shape[1]
    stop_ids = [tokenizer.eos_token_id]
    im_end_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
    if im_end_id != tokenizer.unk_token_id:
        stop_ids.append(im_end_id)

    gen_kwargs = dict(
        **inputs,
        max_new_tokens=max_new_tokens,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=stop_ids,
    )
    if temperature and temperature > 0:
        gen_kwargs.update(do_sample=True, temperature=temperature, top_p=1.0)
    else:
        gen_kwargs["do_sample"] = False

    if token_callback is not None:
        streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=False)
        gen_kwargs["streamer"] = streamer
        holder: dict[str, torch.Tensor] = {}

        def _run_generate():
            with torch.no_grad():
                holder["outputs"] = model.generate(**gen_kwargs)

        worker = Thread(target=_run_generate, daemon=True)
        worker.start()
        pieces: list[str] = []
        for piece in streamer:
            pieces.append(piece)
            token_callback(piece)
        worker.join()
        outputs = holder["outputs"]
        text = "".join(pieces)
    else:
        with torch.no_grad():
            outputs = model.generate(**gen_kwargs)
        text = tokenizer.decode(outputs[0, input_len:], skip_special_tokens=False)

    new_token_count = outputs.shape[1] - input_len
    last_tok = outputs[0, -1].item()
    hit_stop = last_tok in stop_ids
    return text, new_token_count, hit_stop


def _stop_ids(tokenizer) -> list[int]:
    stop_ids = [tokenizer.eos_token_id]
    im_end_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
    if im_end_id != tokenizer.unk_token_id:
        stop_ids.append(im_end_id)
    return [token_id for token_id in stop_ids if token_id is not None]


def _generate_batch_once(
    model,
    tokenizer,
    prompts: list[str],
    max_new_tokens: int,
    temperature: float | None = None,
) -> list[tuple[str, int, bool]]:
    if not prompts:
        return []
    original_padding_side = getattr(tokenizer, "padding_side", "right")
    tokenizer.padding_side = "left"
    try:
        inputs = tokenizer(prompts, return_tensors="pt", add_special_tokens=False, padding=True).to(model.device)
    finally:
        tokenizer.padding_side = original_padding_side

    input_width = inputs["input_ids"].shape[1]
    stop_ids = _stop_ids(tokenizer)
    gen_kwargs = dict(
        **inputs,
        max_new_tokens=max_new_tokens,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=stop_ids,
    )
    if temperature and temperature > 0:
        gen_kwargs.update(do_sample=True, temperature=temperature, top_p=1.0)
    else:
        gen_kwargs["do_sample"] = False

    with torch.no_grad():
        outputs = model.generate(**gen_kwargs)

    rows: list[tuple[str, int, bool]] = []
    for output in outputs:
        generated = output[input_width:]
        hit_stop = False
        stop_pos = len(generated)
        for idx, token_id in enumerate(generated.tolist()):
            if token_id in stop_ids:
                hit_stop = True
                stop_pos = idx + 1
                break
        trimmed = generated[:stop_pos]
        text = tokenizer.decode(trimmed, skip_special_tokens=False)
        rows.append((text, int(trimmed.shape[0]), hit_stop))
    return rows


@dataclass
class _BatchState:
    prompt: str
    accumulated: str
    total_new_tokens: int
    remaining: int
    cur_prompt: str
    execution: dict
    executor: object
    sandbox_path: Path | None
    done: bool = False


def generate(
    model,
    tokenizer,
    prompt: str,
    max_new_tokens: int,
    max_tool_rounds: int = 5,
    token_callback=None,
    execution: dict | None = None,
    temperature: float | None = None,
) -> tuple[str, int]:
    accumulated = ""
    total_new_tokens = 0
    remaining = max_new_tokens
    cur_prompt = prompt
    execution = execution or {}
    executor = create_executor(
        nsjail_path=execution.get("nsjail_path"),
        timeout=execution.get("timeout", 30),
    )
    blueprint_root = execution.get("blueprint_root")
    trace_prefix = execution.get("trace_prefix") or blueprint_root
    sandbox_root = execution.get("sandbox_root")
    sandbox_path = None
    if blueprint_root and sandbox_root:
        _, sandbox_path = ensure_sandbox_copy(blueprint_root, Path(sandbox_root))

    for _ in range(max_tool_rounds + 1):
        if remaining <= 0:
            break
        chunk, n_tok, hit_stop = _generate_once(
            model,
            tokenizer,
            cur_prompt,
            remaining,
            token_callback=token_callback,
            temperature=temperature,
        )
        accumulated += chunk
        total_new_tokens += n_tok
        remaining -= n_tok

        full_trace = prompt + accumulated
        assistant = assistant_text(full_trace)
        tools = tool_text(full_trace)
        pending_ids = extract_pending_call_ids(assistant, tools)
        if hit_stop and not pending_ids:
            break
        if not pending_ids:
            break

        injections = []
        for call in parse_call_blocks(assistant):
            if call["id"] not in pending_ids:
                continue
            params = call["params"]
            if trace_prefix and sandbox_path:
                params = rewrite_params_for_sandbox(params, trace_prefix, sandbox_path)
            result = execute_rust_tool(
                executor,
                call["tool"],
                params,
                expected_output=execution.get("expected_output") if call["tool"] == "cargo_run" else None,
            )
            result_block = format_result_block(call["id"], result)
            injections.append(
                "\n\n"
                "<|im_start|>tool\n"
                f"{result_block}\n"
                "<|im_end|>\n\n"
                "<|im_start|>assistant\n"
            )

        if not injections:
            break
        accumulated += "".join(injections)
        cur_prompt = prompt + accumulated

    return accumulated.strip(), total_new_tokens


def generate_batch(
    model,
    tokenizer,
    prompts: list[str],
    max_new_tokens: int,
    max_tool_rounds: int = 5,
    executions: list[dict] | None = None,
    temperature: float | None = None,
    tool_workers: int | None = None,
) -> list[tuple[str, int]]:
    executions = executions or [{} for _ in prompts]
    if len(executions) != len(prompts):
        raise ValueError("executions must have the same length as prompts")
    states: list[_BatchState] = []
    for prompt, execution in zip(prompts, executions):
        executor = create_executor(
            nsjail_path=execution.get("nsjail_path"),
            timeout=execution.get("timeout", 30),
        )
        blueprint_root = execution.get("blueprint_root")
        sandbox_root = execution.get("sandbox_root")
        sandbox_path = None
        if blueprint_root and sandbox_root:
            _, sandbox_path = ensure_sandbox_copy(blueprint_root, Path(sandbox_root))
        states.append(
            _BatchState(
                prompt=prompt,
                accumulated="",
                total_new_tokens=0,
                remaining=max_new_tokens,
                cur_prompt=prompt,
                execution=execution,
                executor=executor,
                sandbox_path=sandbox_path,
            )
        )

    for _ in range(max_tool_rounds + 1):
        active = [state for state in states if not state.done and state.remaining > 0]
        if not active:
            break
        chunk_budget = min(state.remaining for state in active)
        generated = _generate_batch_once(
            model,
            tokenizer,
            [state.cur_prompt for state in active],
            chunk_budget,
            temperature=temperature,
        )

        tool_jobs_by_state: list[tuple[_BatchState, list[tuple[dict, dict]]]] = []
        for state, (chunk, n_tok, hit_stop) in zip(active, generated):
            state.accumulated += chunk
            state.total_new_tokens += n_tok
            state.remaining -= n_tok

            full_trace = state.prompt + state.accumulated
            assistant = assistant_text(full_trace)
            tools = tool_text(full_trace)
            pending_ids = extract_pending_call_ids(assistant, tools)
            if hit_stop and not pending_ids:
                state.done = True
                continue
            if not pending_ids:
                state.done = True
                continue

            trace_prefix = state.execution.get("trace_prefix") or state.execution.get("blueprint_root")
            state_jobs: list[tuple[dict, dict]] = []
            for call in parse_call_blocks(assistant):
                if call["id"] not in pending_ids:
                    continue
                params = call["params"]
                if trace_prefix and state.sandbox_path:
                    params = rewrite_params_for_sandbox(params, trace_prefix, state.sandbox_path)
                state_jobs.append((call, params))

            if state_jobs:
                tool_jobs_by_state.append((state, state_jobs))
            else:
                state.done = True

        def _run_state_tools(job):
            state, state_jobs = job
            result_blocks = []
            for call, params in state_jobs:
                result = execute_rust_tool(
                    state.executor,
                    call["tool"],
                    params,
                    expected_output=state.execution.get("expected_output") if call["tool"] == "cargo_run" else None,
                )
                result_blocks.append(format_result_block(call["id"], result))
            return state, result_blocks

        if tool_jobs_by_state:
            workers = tool_workers or min(8, len(tool_jobs_by_state))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for state, result_blocks in pool.map(_run_state_tools, tool_jobs_by_state):
                    for result_block in result_blocks:
                        state.accumulated += (
                            "\n\n"
                            "<|im_start|>tool\n"
                            f"{result_block}\n"
                            "<|im_end|>\n\n"
                            "<|im_start|>assistant\n"
                        )
                    state.cur_prompt = state.prompt + state.accumulated

    return [(state.accumulated.strip(), state.total_new_tokens) for state in states]
