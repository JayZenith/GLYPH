from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from openai import AsyncOpenAI


class VLLMCompletionClient:
    """Stream raw completions from vLLM's OpenAI-compatible API.

    GLYPH renders ChatML locally and uses /v1/completions rather than
    /v1/chat/completions. That keeps the bytes identical to SFT, RLVR, and eval
    instead of asking the serving layer to choose a chat template.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "EMPTY",
        temperature: float = 0.2,
        max_tokens: int = 4000,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        normalized_url = base_url.rstrip("/")
        if not normalized_url.endswith("/v1"):
            normalized_url += "/v1"
        self.base_url = normalized_url
        self._client = AsyncOpenAI(base_url=normalized_url, api_key=api_key)

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        response = await self._client.completions.create(
            model=self.model,
            prompt=prompt,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=1.0,
            stop=["<|im_end|>", "<|im_start|>"],
            stream=True,
        )
        async for chunk in response:
            if not chunk.choices:
                continue
            text = chunk.choices[0].text
            if text:
                yield text

    async def close(self) -> None:
        await self._client.close()


class ScriptedCompletionClient:
    """Deterministic offline backend for inspecting the TUI without vLLM.

    The script intentionally emits the same CALL/RESULT/FINAL shape as the real
    model loop. Tool calls still execute through the local Rust runtime against
    the disposable crate copy created by ``GlyphDemoSession``.
    """

    def __init__(
        self,
        trace_prefix: str = "runs/rlvr1/rust_cases/eval100_013_patch_test_pass_014_dispatch_policy_match_order",
        chunk_size: int = 18,
    ) -> None:
        self.trace_prefix = trace_prefix.rstrip("/")
        self.chunk_size = chunk_size
        self._turn_index = 0

    def reset(self) -> None:
        self._turn_index = 0

    @property
    def _script(self) -> tuple[str, ...]:
        crate = self.trace_prefix
        return (
            f'CALL read_file {{"id":"c1","file_path":"{crate}/src/lib.rs"}}',
            (
                'CALL apply_patch {"id":"c2",'
                f'"file_path":"{crate}/src/lib.rs",'
                '"find":"        Action::Delete => !dry_run,\\n",'
                '"replace":"        Action::Delete => !dry_run && role != Role::Guest,\\n"}'
            ),
            f'CALL cargo_test {{"id":"c3","project_path":"{crate}"}}',
            (
                "FINAL: Patched the Delete branch so Guest deletes are not logged, "
                "while Admin and User deletes still require a real non-dry-run execution. "
                "The crate tests pass."
            ),
        )

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        del prompt
        script = self._script
        text = script[min(self._turn_index, len(script) - 1)]
        self._turn_index += 1
        for start in range(0, len(text), self.chunk_size):
            await asyncio.sleep(0)
            yield text[start : start + self.chunk_size]

    async def close(self) -> None:
        return None
