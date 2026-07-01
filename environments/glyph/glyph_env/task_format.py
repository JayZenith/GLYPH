from __future__ import annotations

import json
import re
from pathlib import Path

CHATML_SEG_RE = re.compile(r"<\|im_start\|>(\w+)\n(.*?)<\|im_end\|>", re.DOTALL)
DEFAULT_SYSTEM = "You are a Rust coding agent. Use tools when needed. After FINAL, stop immediately."


def _chatml_to_messages(prompt: str) -> list[dict[str, str]]:
    """Convert stored ChatML prompts to chat messages for PRIME-RL.

    Passing a ChatML string as the dataset prompt makes verifiers wrap the whole
    thing inside a user message. That trains on nested ChatML markers instead of
    the SFT/eval protocol. Keep only non-empty system/user turns; generation
    starts at the assistant turn.
    """
    segments = [
        {"role": role, "content": body.strip()}
        for role, body in CHATML_SEG_RE.findall(prompt)
        if body.strip()
    ]
    messages = [m for m in segments if m["role"] in {"system", "user"}]
    if messages:
        return messages
    return [
        {"role": "system", "content": DEFAULT_SYSTEM},
        {"role": "user", "content": prompt.strip()},
    ]


# JSONL row {"prompt": "...", "expected_tool": "read_file", ...}
# becomes {"prompt": [{"role": "system", ...}, {"role": "user", ...}],
#          "expected_tool": "read_file", ...}.
# task_trace.py later moves selected metadata under the Dataset row's "info".
def load_prompts(
    data_path: str,
    max_samples: int | None = None,
) -> tuple[list[dict], dict]:
    """Read JSONL prompts, normalize prompt messages, and preserve metadata."""

    prompts: list[dict] = []
    stats = {
        "total": 0,
        "skipped_malformed": 0,
    }

    with Path(data_path).open(encoding="utf-8") as f:
        for line in f:
            if max_samples and len(prompts) >= max_samples:
                break
            stats["total"] += 1
            try:
                item = json.loads(line)

                if "prompt" in item:
                    prompt = _chatml_to_messages(str(item["prompt"]))
                    row = {k: v for k, v in item.items() if k != "prompt"}
                    row["prompt"] = prompt
                    prompts.append(row)
                    continue

                trace = item.get("trace", "")
                split = trace.split("<|im_start|>assistant", 1)
                if len(split) != 2:
                    stats["skipped_malformed"] += 1
                    continue

                prompt_part, assistant_segment = split
                prompts.append({"prompt": _chatml_to_messages(prompt_part)})
            except Exception:
                stats["skipped_malformed"] += 1

    return prompts, stats
