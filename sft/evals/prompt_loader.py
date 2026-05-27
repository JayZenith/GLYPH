"""Load eval prompts from evals/eval_prompts.yaml and render them to CALL/RESULT format."""
import json
import re
from pathlib import Path

import yaml

_PROMPTS_FILE = Path(__file__).parent / "eval_prompts.yaml"
_USER_RE = re.compile(r"<\|im_start\|>user\n(.*?)\n<\|im_end\|>", re.DOTALL)
_STRICT_EVAL_SUFFIX = (
    "Respond in English only. "
    "Use only the expected trace format with plain assistant text plus CALL/RESULT/FINAL blocks. "
    "Do not include chain-of-thought, meta commentary, markdown fences, or any text after FINAL."
)

def load_prompts(section: str, prompt_file: str | None = None) -> list[dict]:
    """Load a named section from a prompt yaml file."""
    prompt_path = Path(prompt_file) if prompt_file else _PROMPTS_FILE
    # read/prase YAML into python dicts/lists
    data = yaml.safe_load(prompt_path.read_text())
    if section not in data:
        raise KeyError(f"Section {section!r} not in {prompt_path}; have {list(data)}")
    rows = data[section]
    # if section already directly contains prompt list, return immediately
    if isinstance(rows, list):
        return rows
    if not isinstance(rows, dict) or "include_from" not in rows or "names" not in rows:
        raise TypeError(
            f"Section {section!r} in {prompt_path} must be a list or an include_from/names mapping."
        )
    base_section = rows["include_from"]
    if base_section not in data or not isinstance(data[base_section], list):
        raise KeyError(f"Included section {base_section!r} is missing or not a list in {prompt_path}")
    base_rows = {row["name"]: row for row in data[base_section]}
    selected: list[dict] = []
    for name in rows["names"]:
        if name not in base_rows:
            raise KeyError(f"Prompt {name!r} not found in included section {base_section!r}")
        selected.append(dict(base_rows[name]))
    return selected


def build_prompt(user_message: str, system_message: str | None = None) -> str:
    """Render a simple CALL/RESULT prompt up to the assistant header."""
    base_system = system_message or "You are a Rust coding agent. Use tools when needed. After FINAL, stop immediately."
    system = f"{base_system} {_STRICT_EVAL_SUFFIX}"
    parts = [
        "<|im_start|>system",
        system,
        "<|im_end|>",
        "",
        "<|im_start|>user",
        user_message,
        "<|im_end|>",
        "",
        "<|im_start|>assistant",
    ]
    return "\n".join(parts) + "\n"


def assert_no_prompt_overlap(prompts: list[dict], train_data_path: str) -> None:
    """Raise if any eval prompt user string appears exactly in the train dataset."""
    train_path = Path(train_data_path)
    if not train_path.exists():
        raise FileNotFoundError(f"Train data file not found: {train_path}")

    prompt_to_names: dict[str, list[str]] = {}
    for item in prompts:
        prompt_to_names.setdefault(item["user"], []).append(item["name"])

    overlaps: list[tuple[str, list[str]]] = []
    with train_path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            trace = obj.get("trace")
            if not isinstance(trace, str):
                raise ValueError(f"{train_path}:{line_no} is missing string field 'trace'")
            match = _USER_RE.search(trace)
            if not match:
                raise ValueError(f"{train_path}:{line_no} is missing a user block")
            user_text = match.group(1)
            if user_text in prompt_to_names:
                overlaps.append((user_text, prompt_to_names[user_text]))

    if overlaps:
        details = "; ".join(
            f"{'/'.join(names)} -> {user[:120]!r}"
            for user, names in overlaps[:5]
        )
        raise ValueError(
            f"Eval/train contamination detected in {train_path}: "
            f"{len(overlaps)} exact prompt overlaps. {details}"
        )
