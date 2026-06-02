"""Post-train generation helper for the simplified CALL/RESULT/FINAL eval."""
from __future__ import annotations

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
