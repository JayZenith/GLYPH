"""Load eval prompts from evals/prompts_125.yaml and render them to TASK format."""
from pathlib import Path

import yaml

_PROMPTS_FILE = Path(__file__).parent / "prompts_125.yaml"


def load_prompts(section: str, prompt_file: str | None = None) -> list[dict]:
    """Load a named section from a prompt yaml file."""
    prompt_path = Path(prompt_file) if prompt_file else _PROMPTS_FILE
    data = yaml.safe_load(prompt_path.read_text())
    if section not in data:
        raise KeyError(f"Section {section!r} not in {prompt_path}; have {list(data)}")
    rows = data[section]
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


def build_prompt(user_message: str, tools: list[dict], system_message: str | None = None) -> str:
    """Render a TASK-format prompt up to the assistant header (greedy generation continues from here)."""
    parts = [
        "<|im_start|>system",
        f"system「{system_message or 'You are a helpful AI assistant that completes tasks step by step.'}」",
    ]
    for tool in tools:
        parts.append("tool {")
        parts.append(f"    name ↦ {tool['name']} •")
        if tool.get("description"):
            parts.append(f'    description ↦ "{tool["description"]}" •')
        if tool.get("params"):
            parts.append("    params ↦ {")
            param_lines = []
            for param_name, param_def in tool["params"].items():
                inner = []
                if "type" in param_def:
                    inner.append(f"type ↦ {param_def['type']}")
                if "enum" in param_def:
                    inner.append(f"enum ↦ [ {' • '.join(param_def['enum'])} ]")
                if "description" in param_def:
                    inner.append(f'description ↦ "{param_def["description"]}"')
                if param_def.get("required") is False:
                    inner.append("required ↦ false")
                param_lines.append(f"        {param_name} ↦ {{ {' • '.join(inner)} }}")
            parts.append(" •\n".join(param_lines))
            parts.append("    }")
        parts.append("}")
    parts.extend([
        "<|im_end|>",
        "",
        "<|im_start|>user",
        f"user「{user_message}」🏷 usr1",
        "<|im_end|>",
        "",
        "<|im_start|>assistant",
    ])
    return "\n".join(parts) + "\n"
