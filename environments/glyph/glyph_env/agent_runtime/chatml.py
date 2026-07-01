"""Render structured message objects into Glyph ChatML.

This module is for JSONL/YAML/runtime message dictionaries, not raw model output
repair. Example: {"role": "user", "content": "Fix the bug"} renders as
<|im_start|>user\nFix the bug\n<|im_end|>.
"""

from __future__ import annotations

from typing import Any

IM_START = "<|im_start|>"
IM_END = "<|im_end|>"
DEFAULT_SYSTEM_PROMPT = (
    "You are a Rust coding agent. Use tools when needed. After FINAL, stop immediately."
)


def render_message(role: str, content: str) -> str:
    """Render one structured message as one ChatML turn."""
    body = content.rstrip()
    rendered = f"{IM_START}{role}\n{body}"

    # Stored assistant turns may already include the generated boundary. Avoid
    # doubling it; this renderer does not repair live model output.
    if role != "assistant" or not body.endswith(IM_END):
        rendered += f"\n{IM_END}"
    return rendered


def _message_value(message: Any, key: str, default: str = "") -> Any:
    """Read role/content from dicts, library objects, or Pydantic-style objects."""
    if isinstance(message, dict):
        return message.get(key, default)

    value = getattr(message, key, default)
    if value is default and hasattr(message, "model_dump"):
        value = message.model_dump().get(key, default)
    return default if value is None else value


def message_role(message: Any) -> str:
    return str(_message_value(message, "role", ""))


def message_content(message: Any) -> str:
    return str(_message_value(message, "content", ""))


def render_messages(messages: list[Any], add_generation_prompt: bool = False) -> str:
    """Render a structured transcript. Optionally open the next assistant turn."""
    rendered = "".join(
        f"{render_message(message_role(message), message_content(message))}\n\n"
        for message in messages
        if message_role(message)
    )
    if add_generation_prompt:
        rendered += f"{IM_START}assistant\n"
    return rendered


def render_prompt(user_message: str, system_message: str | None = None) -> str:
    """Render the standard eval/SFT prompt: system + user + open assistant."""
    return render_messages(
        [
            {"role": "system", "content": system_message or DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        add_generation_prompt=True,
    )


def render_tool_turn(result_block: str) -> str:
    """Inject a tool RESULT and reopen assistant generation."""
    return f"\n\n{render_message('tool', result_block)}\n\n{IM_START}assistant\n"


# Tokenizer-side copy of the same rendering rules. rl/train.py installs this
# into the local tokenizer view so PRIME-RL/vLLM render the same bytes.
GLYPH_CHAT_TEMPLATE = """{%- for message in messages %}
{%- set role = message['role'] %}
{%- set content = message['content'] %}
{%- if role == 'assistant' %}
{{- '<|im_start|>assistant\n' + content.rstrip() }}
{%- if not content.rstrip().endswith('<|im_end|>') %}
{{- '\n<|im_end|>' }}
{%- endif %}
{{- '\n\n' }}
{%- else %}
{{- '<|im_start|>' + role + '\n' + content.rstrip() + '\n<|im_end|>\n\n' }}
{%- endif %}
{%- endfor %}
{%- if add_generation_prompt %}
{{- '<|im_start|>assistant\n' }}
{%- endif %}"""


def assert_glyph_template_parity(tokenizer: Any | None = None) -> None:
    """Hard-fail if the tokenizer template and Python renderer diverge."""
    messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "USR"},
        {
            "role": "assistant",
            "content": 'CALL read_file {"id":"c1","file_path":"x"}\n<|im_end|>',
        },
        {"role": "tool", "content": "RESULT c1:\nstatus: success"},
    ]

    if tokenizer is not None:
        rendered = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    else:
        from jinja2.sandbox import ImmutableSandboxedEnvironment

        env = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
        rendered = env.from_string(GLYPH_CHAT_TEMPLATE).render(
            messages=messages, add_generation_prompt=True
        )

    expected = render_messages(messages, add_generation_prompt=True)
    if rendered != expected:
        raise RuntimeError(
            "GLYPH_CHAT_TEMPLATE no longer matches the shared ChatML renderer.\n"
            f"rendered: {rendered!r}\n"
            f"expected: {expected!r}"
        )


def install_glyph_chat_template(tokenizer: Any) -> Any:
    """Install Glyph ChatML into a tokenizer and verify byte parity."""
    tokenizer.chat_template = GLYPH_CHAT_TEMPLATE
    assert_glyph_template_parity(tokenizer)
    return tokenizer
