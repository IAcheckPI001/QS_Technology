
from collections.abc import AsyncIterator
from openai import AsyncOpenAI


class OllamaModelProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 180.0,
    ) -> None:
        self._client = AsyncOpenAI(
            base_url=f"{base_url.rstrip('/')}/",
            api_key="ollama",
            timeout=timeout,
        )
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
        )

        async for part in stream:
            if not part.choices:
                continue

            content = part.choices[0].delta.content

            if isinstance(content, str) and content:
                yield content

    async def close(self) -> None:
        await self._client.close()
