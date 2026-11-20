from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import contextmanager
from typing import Any

from app.core.tracing import Span, UsageEntry, UsageKind, current_span, record_usage, span
from app.modules.chatbot.schemas.system import (
    AssistantTurn,
    LLMCapabilities,
    ModelProvider,
    TokenUsage,
    ToolCallRequest,
    ToolChoice,
)
from app.modules.chatbot.providers.base import ProviderTransientError
from app.util.parse_json import parse_json_object
from app.util.token_counter import count_tokens

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

# OpenAI Chat Completions hỗ trợ đủ tool calling, nhiều tool call trong một
# response, tool_choice none và Structured Outputs (strict).
OPENAI_CAPABILITIES = LLMCapabilities(
    tool_calling=True,
    parallel_tool_calls=True,
    tool_choice_none=True,
    schema_dialect="openai_strict",
)


def is_reasoning_model(model: str) -> bool:
    """Model suy luận (o1/o3/o4…, gpt-5…): không nhận temperature tuỳ ý và max_tokens;
    giới hạn đầu ra là max_completion_tokens (gồm cả token suy nghĩ)."""
    name = model.strip().lower()
    return name.startswith("gpt-5") or (len(name) > 1 and name[0] == "o" and name[1].isdigit())


def _token_usage(usage: Any) -> TokenUsage | None:
    """Usage của response OpenAI (chat hoặc embedding); None khi response không kèm usage."""
    if usage is None:
        return None
    details = getattr(usage, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", None) if details else None
    return TokenUsage(
        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        cached_input_tokens=cached if isinstance(cached, int) else None,
    )


class _Meter:
    """Ghi usage của một lời gọi vào span và vào sổ usage của trace (`record_usage`)."""

    def __init__(self, kind: UsageKind, model: str, target: Span) -> None:
        self.kind = kind
        self.model = model
        self.target = target
        self.recorded = False
        self.streamed: list[str] = []

    def record(self, usage: Any) -> TokenUsage | None:
        tokens = _token_usage(usage)
        if tokens is None:
            return None
        self.target.set(
            input_tokens=tokens.input_tokens,
            output_tokens=tokens.output_tokens,
            cached_input_tokens=tokens.cached_input_tokens,
        )
        record_usage(UsageEntry(
            kind=self.kind, model=self.model, input_tokens=tokens.input_tokens,
            output_tokens=tokens.output_tokens, cached_input_tokens=tokens.cached_input_tokens or 0,
        ))
        self.recorded = True
        return tokens


@contextmanager
def _metered(kind: UsageKind, model: str, target: Span, prompt_tokens: Callable[[], int]) -> Iterator[_Meter]:
    """Lời gọi kết thúc mà chưa có usage thật (hết giờ, bị huỷ, stream ngắt trước chunk usage cuối)
    vẫn có thể bị tính tiền: ghi một mục ước tính. Request bị từ chối (HTTP lỗi) hoặc không tới được
    OpenAI (lỗi kết nối) thì không ghi."""
    meter = _Meter(kind, model, target)
    billable = True
    try:
        yield meter
    except APITimeoutError:
        raise                           # OpenAI có thể đã xử lý request: vẫn ước tính
    except (APIStatusError, APIConnectionError):
        billable = False
        raise
    finally:
        if billable and not meter.recorded:
            output = count_tokens("".join(meter.streamed), model) if meter.streamed else 0
            record_usage(UsageEntry(
                kind=kind, model=model, input_tokens=prompt_tokens(), output_tokens=output, estimated=True,
            ))
            target.set(usage_estimated=True)


def _prompt_tokens(messages: list[dict[str, Any]], model: str) -> Callable[[], int]:
    """Ước tính token prompt; chỉ dùng khi không có usage thật."""
    def estimate() -> int:
        return count_tokens("\n".join(str(message.get("content") or "") for message in messages), model)
    return estimate


_TIMEOUT_PHASES = {"ConnectTimeout": "connect", "ReadTimeout": "read", "WriteTimeout": "write", "PoolTimeout": "pool"}


def _timeout_phase(error: BaseException) -> str:
    """Giai đoạn hết giờ theo exception httpx gốc: connect (chưa tới OpenAI), read (chờ phản hồi)."""
    cause = error.__cause__ or error.__context__
    while cause is not None:
        phase = _TIMEOUT_PHASES.get(type(cause).__name__)
        if phase:
            return phase
        cause = cause.__cause__ or cause.__context__
    return "unknown"


def _error_code(error: APIStatusError) -> str | None:
    code = getattr(error, "code", None)
    return code if isinstance(code, str) else None


def _set_provider_headers(target: Span, headers: Any) -> None:
    """Request id và thời gian OpenAI tự xử lý (openai-processing-ms): so với latency để thấy phần
    chậm nằm ở OpenAI hay ở mạng/hàng đợi. Không phải dữ liệu nhạy cảm."""
    request_id = headers.get("x-request-id")
    processing = headers.get("openai-processing-ms")
    attributes: dict[str, Any] = {}
    if request_id:
        attributes["provider_request_id"] = str(request_id)[:64]
    if processing and str(processing).isdigit():
        attributes["provider_processing_ms"] = int(processing)
    if attributes:
        target.set(**attributes)


class OpenAIProvider:
    kind = ModelProvider.OPENAI

    def __init__(
        self,
        api_key: str,
        model: str,
        embedding_model: str = "text-embedding-3-small",
        *,
        reasoning_effort: str | None = None,
        tool_call_timeout_s: float | None = None,
    ) -> None:
        """reasoning_effort: chỉ gửi khi model là model suy luận (vd low, medium).

        tool_call_timeout_s: timeout mỗi request của `chat_complete_tools`, không để SDK tự thử lại
        (runner thử lại). None = mặc định SDK (600 s, tự thử lại 2 lần, không thấy được trong trace).
        """
        self._client = AsyncOpenAI(api_key=api_key)
        self._tool_call_timeout_s = tool_call_timeout_s
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
        with (
            span("llm.stream_chat", "llm", model=self._model, messages=len(messages)) as llm_span,
            _metered("llm", self._model, llm_span, _prompt_tokens(messages, self._model)) as meter,
        ):
            stream: Any = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True,
                # Chunk cuối (choices rỗng) mang usage thật của cả lượt stream.
                stream_options={"include_usage": True},
            )
            chunks = 0
            async for part in stream:
                meter.record(getattr(part, "usage", None))
                text = part.choices[0].delta.content if part.choices else None
                if text:
                    chunks += 1
                    meter.streamed.append(text)
                    if chunks == 1:
                        llm_span.set(first_token_ms=round(llm_span.elapsed_ms()))
                    llm_span.set(chunks=chunks)
                    yield text
    
    async def chat_complete_json(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        with (
            span("llm.chat_json", "llm", model=self._model, messages=len(messages)) as llm_span,
            _metered("llm", self._model, llm_span, _prompt_tokens(messages, self._model)) as meter,
        ):
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=False,
                response_format=response_format or {"type": "json_object"},
                # Model suy luận cần chỗ cho token suy nghĩ.
                **self._generation_options(2000 if self._reasoning else 600),
            )
            meter.record(resp.usage)
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
        with (
            span("llm.chat_text", "llm", model=self._model, messages=len(messages)) as llm_span,
            _metered("llm", self._model, llm_span, _prompt_tokens(messages, self._model)) as meter,
        ):
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=False,
            )
            meter.record(response.usage)

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
        # Span `llm.chat_tools` do runner mở và đang là span hiện tại.
        target = current_span()
        client = (
            self._client.with_options(timeout=self._tool_call_timeout_s, max_retries=0)
            if self._tool_call_timeout_s else self._client
        )
        completions = client.chat.completions
        raw_api = getattr(completions, "with_raw_response", None)
        request = {
            "model": self._model, "messages": messages, "stream": False,
            **self._generation_options(max_tokens), **options,
        }
        try:
            with _metered("llm", self._model, target, _prompt_tokens(messages, self._model)) as meter:
                if raw_api is not None:
                    raw = await raw_api.create(**request)
                    _set_provider_headers(target, raw.headers)
                    resp = raw.parse()
                else:
                    resp = await completions.create(**request)
                usage = meter.record(resp.usage) or TokenUsage()
        except APITimeoutError as error:
            # Kết nối (mạng, DNS, TLS) hay chờ phản hồi (OpenAI chưa trả): phân biệt nguồn của LC-2.
            target.set(timeout_phase=_timeout_phase(error))
            raise TimeoutError("OpenAI request timed out") from error
        except APIStatusError as error:
            target.set(provider_request_id=error.request_id)
            if error.status_code == 429 or error.status_code >= 500:
                raise ProviderTransientError(
                    f"http_{error.status_code}", status_code=error.status_code, code=_error_code(error),
                ) from error
            raise
        except APIConnectionError as error:
            raise ProviderTransientError("connection") from error
        if not resp.choices:
            raise RuntimeError("OpenAI returned no completion choices.")
        choice = resp.choices[0]
        message = choice.message
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
            usage=usage,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._embedding_model
        with (
            span("embedding", "embedding", model=model, inputs=len(texts)) as embed_span,
            _metered("embedding", model, embed_span, lambda: count_tokens("\n".join(texts), model)) as meter,
        ):
            response = await self._client.embeddings.create(model=model, input=texts)
            meter.record(getattr(response, "usage", None))
        ordered = sorted(response.data, key=lambda item: item.index)
        return [list(item.embedding) for item in ordered]

    async def close(self) -> None:
        await self._client.close()
