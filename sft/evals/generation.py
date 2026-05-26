"""Post-train generation helper for the simplified CALL/RESULT/FINAL eval."""
from __future__ import annotations

import re
from threading import Thread

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer


SEG_RE = re.compile(r"<\|im_start\|>(\w+)\n(.*?)<\|im_end\|>", re.DOTALL)
CALL_BLOCK_RE = re.compile(r"^\s*CALL\s+([A-Za-z_]\w*)\((.*?)\)\s*$", re.MULTILINE | re.DOTALL)
CALL_ID_RE = re.compile(r'\bid\s*=\s*"([^"]+)"')
RESULT_ID_RE = re.compile(r"^\s*RESULT\s+([A-Za-z0-9_\-]+):", re.MULTILINE)


def _segments(text: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in SEG_RE.finditer(text)]


def _extract_calls(text: str) -> list[tuple[str, str]]:
    assistant = "\n".join(body for role, body in _segments(text) if role == "assistant")
    calls: list[tuple[str, str]] = []
    for tool_name, arg_blob in CALL_BLOCK_RE.findall(assistant):
        match = CALL_ID_RE.search(arg_blob)
        if match:
            calls.append((tool_name, match.group(1)))
    return calls


def _extract_result_ids(text: str) -> list[str]:
    tool_text = "\n".join(body for role, body in _segments(text) if role == "tool")
    return RESULT_ID_RE.findall(tool_text)


def extract_pending_calls(text: str) -> list[tuple[str, str]]:
    calls = _extract_calls(text)
    result_ids = set(_extract_result_ids(text))
    return [(tool_name, call_id) for tool_name, call_id in calls if call_id not in result_ids]


def inject_mock_result(call_id: str, content: str) -> str:
    return (
        "\n\n"
        "<|im_start|>tool\n"
        f"RESULT {call_id}:\n"
        f"{content}\n"
        "<|im_end|>\n\n"
        "<|im_start|>assistant\n"
    )


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


def _generate_once(model, tokenizer, prompt: str, max_new_tokens: int, token_callback=None) -> tuple[str, int, bool]:
    inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(model.device)
    input_len = inputs["input_ids"].shape[1]
    stop_ids = [tokenizer.eos_token_id]
    im_end_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
    if im_end_id != tokenizer.unk_token_id:
        stop_ids.append(im_end_id)

    gen_kwargs = dict(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=stop_ids,
    )

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
    mock_results: list[dict] | None = None,
) -> tuple[str, int]:
    accumulated = ""
    total_new_tokens = 0
    remaining = max_new_tokens
    cur_prompt = prompt
    mock_results = list(mock_results or [])
    next_result_idx = 0

    for _ in range(max_tool_rounds + 1):
        if remaining <= 0:
            break
        chunk, n_tok, hit_stop = _generate_once(
            model,
            tokenizer,
            cur_prompt,
            remaining,
            token_callback=token_callback,
        )
        accumulated += chunk
        total_new_tokens += n_tok
        remaining -= n_tok
        pending = extract_pending_calls(accumulated)
        if hit_stop and not pending:
            break
        if not pending:
            break

        injections = []
        for tool_name, call_id in pending:
            if next_result_idx < len(mock_results):
                scripted = mock_results[next_result_idx]
                content = scripted["content"]
                scripted_tool = scripted.get("tool")
                if scripted_tool and scripted_tool != tool_name:
                    content = f"status: mocked mismatch\nexpected_tool: {scripted_tool}\nactual_tool: {tool_name}"
                next_result_idx += 1
            else:
                content = "status: success"
            injections.append(inject_mock_result(call_id, content))

        accumulated += "".join(injections)
        cur_prompt = prompt + accumulated

    return accumulated.strip(), total_new_tokens
