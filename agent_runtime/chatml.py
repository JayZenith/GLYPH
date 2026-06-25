from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, TypeAlias, cast


DEFAULT_SYSTEM_PROMPT = "You are a Rust coding agent. Use tools when needed. After FINAL, stop immediately."

# Shared Glyph ChatML source of truth. This must stay byte-identical with the
# rendered SFT traces and eval prompts:
#   <|im_start|>role\n{content}\n<|im_end|>\n\n
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


class AttributeMessage(Protocol):
    role: object
    content: object


class ModelDumpMessage(Protocol):
    def model_dump(self) -> Mapping[str, object]: ...


class ChatTemplateTokenizer(Protocol):
    def apply_chat_template(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
    ) -> str: ...


MessageLike: TypeAlias = Mapping[str, object] | AttributeMessage | ModelDumpMessage

_MISSING = object()


def _message_value(message: MessageLike, key: str, default: str = "") -> object:
    if isinstance(message, Mapping):
        return message.get(key, default)
    value = getattr(message, key, _MISSING)
    if value is _MISSING and hasattr(message, "model_dump"):
        value = cast(ModelDumpMessage, message).model_dump().get(key, default)
    return default if value is None else value


def message_role(message: MessageLike) -> str:
    return str(_message_value(message, "role", ""))


def message_content(message: MessageLike) -> str:
    return str(_message_value(message, "content", ""))


def render_message(role: str, content: str) -> str:
    body = content.rstrip()
    rendered = f"<|im_start|>{role}\n{body}"
    if role != "assistant" or not body.endswith("<|im_end|>"):
        rendered += "\n<|im_end|>"
    return rendered


def render_messages(messages: Sequence[MessageLike], add_generation_prompt: bool = False) -> str:
    rendered = "".join(
        f"{render_message(message_role(message), message_content(message))}\n\n"
        for message in messages
        if message_role(message)
    )
    if add_generation_prompt:
        rendered += "<|im_start|>assistant\n"
    return rendered


def render_prompt(user_message: str, system_message: str | None = None) -> str:
    return render_messages(
        [
            {"role": "system", "content": system_message or DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        add_generation_prompt=True,
    )


def render_tool_turn(result_block: str) -> str:
    return f"\n\n{render_message('tool', result_block)}\n\n<|im_start|>assistant\n"


def assert_glyph_template_parity(tokenizer: ChatTemplateTokenizer | None = None) -> None:
    """Hard-fail if the tokenizer chat template drifts from this renderer."""
    messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "USR"},
        {"role": "assistant", "content": 'CALL read_file(id="c1", file_path="x")\n<|im_end|>'},
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
