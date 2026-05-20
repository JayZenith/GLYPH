"""Post-train generation helper for formal eval.

It runs greedy assistant turns and, when the model emits a tool call, injects
a mocked `tool` turn so the next assistant turn can continue. This mirrors the
SFT/RL chat structure closely enough for offline format checks.
"""
import re

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


# Match the standalone `id ↦ ...` field inside a call block, not substrings
# like `run_id`.
CALL_ID_PATTERN = re.compile(r"call\s*↦\s*\{[^}]*?(?<![\w])id\s*↦\s*([\w\"\-]+)", re.DOTALL)
_RESULT_BLOCK_TAG = re.compile(r"result\s*\{[^}]*?\}\s*🏷\s*([\w\"\-]+)", re.DOTALL)
_RESULT_INNER_TAG = re.compile(r'data\s*↦\s*[^🏷]*🏷\s*([\w\"\-]+)', re.DOTALL)


def extract_pending_call_ids(text: str) -> list[str]:
    """Call ids in the trace so far that don't yet have a matching result."""
    call_ids = CALL_ID_PATTERN.findall(text)
    result_ids = _RESULT_BLOCK_TAG.findall(text) + _RESULT_INNER_TAG.findall(text)
    seen = {r.strip('"') for r in result_ids}
    return [cid.strip('"') for cid in call_ids if cid.strip('"') not in seen]


def inject_mock_result(call_id: str) -> str:
    return (
        "\n\n"
        "<|im_start|>tool\n"
        f'result {{\n    data ↦ "Mocked tool result for {call_id}." 🏷 {call_id}\n}}\n'
        "<|im_end|>\n\n"
        "<|im_start|>assistant\n"
    )


def load_model(model_path: str):
    """Load model + tokenizer; try flash-attn-2, fall back to sdpa."""
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            attn_implementation="flash_attention_2",
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


def _generate_once(model, tokenizer, prompt: str, max_new_tokens: int) -> tuple[str, int, bool]:
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    input_len = inputs["input_ids"].shape[1]
    stop_ids = [tokenizer.eos_token_id]
    im_end_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
    if im_end_id != tokenizer.unk_token_id:
        stop_ids.append(im_end_id)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=stop_ids,
        )

    new_token_count = outputs.shape[1] - input_len
    last_tok = outputs[0, -1].item()
    hit_stop = last_tok in stop_ids
    text = tokenizer.decode(outputs[0, input_len:], skip_special_tokens=False)
    return text, new_token_count, hit_stop


def generate(model, tokenizer, prompt: str, max_new_tokens: int, max_tool_rounds: int = 4) -> tuple[str, int]:
    """Multi-round greedy generation with mocked tool-role results."""
    accumulated = ""
    total_new_tokens = 0
    remaining = max_new_tokens
    cur_prompt = prompt
    for _ in range(max_tool_rounds + 1):
        if remaining <= 0:
            break
        chunk, n_tok, hit_stop = _generate_once(model, tokenizer, cur_prompt, remaining)
        accumulated += chunk
        total_new_tokens += n_tok
        remaining -= n_tok
        pending = extract_pending_call_ids(accumulated)
        if hit_stop and not pending:
            break
        if not pending:
            break
        injection = "".join(inject_mock_result(cid) for cid in pending)
        accumulated += injection
        cur_prompt = prompt + accumulated
    return accumulated.strip(), total_new_tokens
