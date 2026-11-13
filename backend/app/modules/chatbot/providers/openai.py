from collections.abc import AsyncIterator
from typing import Any

from app.core.tracing import Span, span
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


def is_reasoning_model(model: str) -> bool:
    """Model suy luận (o1/o3/o4…, gpt-5…): không nhận temperature tuỳ ý và max_tokens;
    giới hạn đầu ra là max_completion_tokens (gồm cả token suy nghĩ)."""
    name = model.strip().lower()
    return name.startswith("gpt-5") or (len(name) > 1 and name[0] == "o" and name[1].isdigit())


def _record_usage(target: Span, usage: Any) -> None:
    """Usage thật của OpenAI vào span (không có usage thì bỏ qua)."""
    if usage is None:
        return
    details = getattr(usage, "prompt_tokens_details", None)
    target.set(
        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        cached_input_tokens=getattr(details, "cached_tokens", None) if details else None,
    )


class OpenAIProvider:
    kind = ModelProvider.OPENAI

    def __init__(
        self,
        api_key: str,
        model: str,
        embedding_model: str = "text-embedding-3-small",
        *,
        reasoning_effort: str | None = None,
    ) -> None:
        """reasoning_effort: chỉ gửi khi model là model suy luận (vd low, medium)."""
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._embedding_model = embedding_model
        self._reasoning = is_reasoning_model(model)
        self._reasoning_effort = reasoning_effort if self._reasoning else None
        self._capabilities = OPENAI_CAPABILITIES.model_copy(update={"reasoning": self._reasoning})

    @property
    def model(self) -> str:
        return self._model

    @property
    def capabilities(self) -> LLMCapabilities:
        return self._capabilities

    def _generation_options(self, max_tokens: int) -> dict[str, Any]:
        """Tham số sinh theo loại model: model suy luận không nhận temperature=0 và max_tokens."""
        if not self._reasoning:
            return {"temperature": 0, "max_tokens": max_tokens}
        options: dict[str, Any] = {"max_completion_tokens": max_tokens}
        if self._reasoning_effort:
            options["reasoning_effort"] = self._reasoning_effort
        return options

    async def stream_chat(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        with span("llm.stream_chat", "llm", model=self._model, messages=len(messages)) as llm_span:
            stream: Any = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True,
                # Chunk cuối (choices rỗng) mang usage thật của cả lượt stream.
                stream_options={"include_usage": True},
            )
            chunks = 0
            async for part in stream:
                _record_usage(llm_span, getattr(part, "usage", None))
                text = part.choices[0].delta.content if part.choices else None
                if text:
                    chunks += 1
                    if chunks == 1:
                        llm_span.set(first_token_ms=round(llm_span.elapsed_ms()))
                    llm_span.set(chunks=chunks)
                    yield text
    
    async def chat_complete_json(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        with span("llm.chat_json", "llm", model=self._model, messages=len(messages)) as llm_span:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=False,
                response_format=response_format or {"type": "json_object"},
                # Model suy luận cần chỗ cho token suy nghĩ.
                **self._generation_options(2000 if self._reasoning else 600),
            )
            _record_usage(llm_span, resp.usage)
            if resp.choices:
                llm_span.set(finish_reason=resp.choices[0].finish_reason)

        if not resp.choices:
            raise RuntimeError("Ollama returned no completion choices.")

        content = resp.choices[0].message.content

        return parse_json_object(content)
    
    async def chat_complete_text(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        with span("llm.chat_text", "llm", model=self._model, messages=len(messages)) as llm_span:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=False,
            )
            _record_usage(llm_span, response.usage)

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
            stream=False,
            **self._generation_options(max_tokens),
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
        with span("embedding", "embedding", model=self._embedding_model, inputs=len(texts)) as embed_span:
            response = await self._client.embeddings.create(
                model=self._embedding_model,
                input=texts,
            )
            usage = getattr(response, "usage", None)
            if usage is not None:
                embed_span.set(input_tokens=getattr(usage, "prompt_tokens", 0) or 0)
        ordered = sorted(response.data, key=lambda item: item.index)
        return [list(item.embedding) for item in ordered]

    async def close(self) -> None:
        await self._client.close()
