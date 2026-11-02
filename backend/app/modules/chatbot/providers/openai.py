from collections.abc import AsyncIterator
from typing import Any

from app.modules.chatbot.schemas.system import (
    AssistantTurn,
    LLMCapabilities,
    ModelProvider,
    TokenUsage,
    ToolCallRequest,
    ToolChoice,
)
from app.util.parse_json import parse_json_object

from openai import AsyncOpenAI

# OpenAI Chat Completions hỗ trợ đủ tool calling, nhiều tool call trong một
# response, tool_choice none/required và Structured Outputs (strict).
OPENAI_CAPABILITIES = LLMCapabilities(
    tool_calling=True,
    parallel_tool_calls=True,
    tool_choice_none=True,
    tool_choice_required=True,
    schema_dialect="openai_strict",
)


class OpenAIProvider:
    kind = ModelProvider.OPENAI

    def __init__(
        self,
        api_key: str,
        model: str,
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._embedding_model = embedding_model

    @property
    def model(self) -> str:
        return self._model

    @property
    def capabilities(self) -> LLMCapabilities:
        return OPENAI_CAPABILITIES

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

    async def chat_complete_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        tool_choice: ToolChoice = "auto",
        parallel_tool_calls: bool = True,
        max_tokens: int = 1200,
    ) -> AssistantTurn:
        """Một bước của vòng lặp agent; arguments giữ nguyên chuỗi để registry validate."""
        options: dict[str, Any] = {}
        if tools:
            options["tools"] = tools
            options["tool_choice"] = tool_choice
            if tool_choice == "auto":
                options["parallel_tool_calls"] = parallel_tool_calls
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0,
            max_tokens=max_tokens,
            stream=False,
            **options,
        )
        if not resp.choices:
            raise RuntimeError("OpenAI returned no completion choices.")
        choice = resp.choices[0]
        message = choice.message
        usage = resp.usage
        return AssistantTurn(
            content=message.content or None,
            tool_calls=[
                ToolCallRequest(
                    id=call.id,
                    name=call.function.name,
                    arguments_raw=call.function.arguments or "",
                )
                for call in message.tool_calls or []
                if call.type == "function"
            ],
            finish_reason=choice.finish_reason,
            usage=TokenUsage(
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
            ),
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model=self._embedding_model,
            input=texts,
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        return [list(item.embedding) for item in ordered]

    async def close(self) -> None:
        await self._client.close()
