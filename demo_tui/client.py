from __future__ import annotations

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
