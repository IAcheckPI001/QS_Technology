from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI


class OpenAIProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def stream_chat(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        stream: Any = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
        )
        async for part in stream:
            text = part.choices[0].delta.content if part.choices else None
            if text:
                yield text

    async def close(self) -> None:
        await self._client.close()
