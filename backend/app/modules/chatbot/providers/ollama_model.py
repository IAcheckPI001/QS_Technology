
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from app.util.parse_json import parse_json_object

# Ollama cắt prompt NGẦM khi vượt num_ctx; prompt chạm ngưỡng này coi như đã bị cắt.
CONTEXT_OVERFLOW_RATIO = 0.95


class OllamaContextOverflowError(RuntimeError):
    """Prompt có thể đã bị Ollama cắt bớt vì vượt num_ctx."""


class OllamaModelProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 180.0,
        num_ctx: int | None = None,
    ) -> None:
        self._client = AsyncOpenAI(
            base_url=f"{base_url.rstrip('/')}/",
            api_key="ollama",
            timeout=timeout,
        )
        self._model = model
        # Endpoint OpenAI-compatible không set được num_ctx theo request: giá trị này phải
        # khớp `PARAMETER num_ctx` trong Modelfile và chỉ dùng để phát hiện bị cắt.
        self._num_ctx = num_ctx

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

    async def chat_complete_json(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resp: Any = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0,
            stream=False,
            response_format=response_format or {"type": "json_object"},
        )

        if not resp.choices:
            raise RuntimeError("Ollama returned no completion choices.")

        usage = resp.usage
        if self._num_ctx and usage is not None and usage.prompt_tokens >= self._num_ctx * CONTEXT_OVERFLOW_RATIO:
            raise OllamaContextOverflowError(
                f"prompt used {usage.prompt_tokens} of num_ctx={self._num_ctx} tokens"
            )

        return parse_json_object(resp.choices[0].message.content)

    async def close(self) -> None:
        await self._client.close()
