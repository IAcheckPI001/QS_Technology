from collections.abc import AsyncIterator
from typing import Any

from app.util.parse_json import parse_json_object

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
    
    async def chat_complete_json(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0,
            max_tokens=600,
            stream=False,
            response_format=response_format or {"type": "json_object"},
        )

        if not resp.choices:
            raise RuntimeError("Ollama returned no completion choices.")

        content = resp.choices[0].message.content

        return parse_json_object(content)
    
    async def chat_complete_text(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=False,
        )

        if not response.choices:
            raise RuntimeError("Ollama returned no completion choices.")

        content = response.choices[0].message.content

        if not isinstance(content, str):
            raise RuntimeError("Ollama returned no text content.")

        return content

    async def close(self) -> None:
        await self._client.close()
