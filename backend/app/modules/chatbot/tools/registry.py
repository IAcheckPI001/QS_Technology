"""Tool Registry: nguồn sự thật về tool agent được dùng, kiểm quyền và invoke an toàn."""

import asyncio
import json
import logging
import re
from collections.abc import Collection
from time import perf_counter
from typing import Any

from pydantic import ValidationError

from app.modules.chatbot.schemas.security.principal import PrincipalContext
from app.modules.chatbot.schemas.system import LLMCapabilities, SchemaDialect, ToolCallRequest

from .base import ToolContext, ToolOutcome, ToolOutput, ToolRejected, ToolSpec
from .schema import to_provider_schema

logger = logging.getLogger(__name__)

# Tên function của OpenAI (và đa số provider): không có dấu chấm.
TOOL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class ToolConfigurationError(ValueError):
    """Tool hoặc provider không đủ điều kiện chạy agent; phát hiện lúc startup."""


class ToolRegistry:
    def __init__(self, specs: Collection[ToolSpec] = ()) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._schemas: dict[tuple[str, SchemaDialect], dict[str, Any]] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: ToolSpec) -> None:
        if not TOOL_NAME_PATTERN.fullmatch(spec.name):
            raise ToolConfigurationError(f"invalid tool name: {spec.name!r}")
        if spec.name in self._specs:
            raise ToolConfigurationError(f"tool already registered: {spec.name}")
        if not spec.description.strip():
            raise ToolConfigurationError(f"{spec.name}: description is required")
        if spec.input_model.model_config.get("extra") != "forbid":
            # LLM không được truyền tham số ngoài contract.
            raise ToolConfigurationError(f"{spec.name}: input model must set extra='forbid'")
        if not issubclass(spec.output_model, ToolOutput):
            raise ToolConfigurationError(f"{spec.name}: output model must extend ToolOutput")
        if spec.timeout_s <= 0:
            raise ToolConfigurationError(f"{spec.name}: timeout must be positive")
        if spec.max_calls_per_turn is not None and spec.max_calls_per_turn < 1:
            raise ToolConfigurationError(f"{spec.name}: max_calls_per_turn must be at least 1")
        self._specs[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    @property
    def names(self) -> list[str]:
        return list(self._specs)

    def allowed(self, principal: PrincipalContext) -> list[ToolSpec]:
        """Tool principal được dùng.

        Chưa có role/scope cho nhân viên CRM: mọi tool không đòi scope đều được
        dùng. Đây là điểm gắn phân quyền theo role sau này.
        """
        return [
            spec
            for spec in self._specs.values()
            if spec.required_scope is None or spec.required_scope in principal.scopes
        ]

    def provider_tools(
        self,
        specs: Collection[ToolSpec],
        dialect: SchemaDialect,
    ) -> list[dict[str, Any]]:
        """Định nghĩa tool gửi qua tham số `tools` của provider (không render vào prompt)."""
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": self._schema(spec, dialect),
                    **({"strict": True} if dialect == "openai_strict" else {}),
                },
            }
            for spec in specs
        ]

    def validate_for(self, capabilities: LLMCapabilities) -> None:
        """Gọi lúc startup: thiếu capability hoặc schema sai thì không bật agent."""
        missing = [
            name
            for name, ok in (
                ("tool_calling", capabilities.tool_calling),
                ("tool_choice_none", capabilities.tool_choice_none),
            )
            if not ok
        ]
        if missing:
            raise ToolConfigurationError(
                f"provider does not support agent mode: missing {', '.join(missing)}"
            )
        if not self._specs:
            raise ToolConfigurationError("agent mode requires at least one registered tool")
        for spec in self._specs.values():
            try:
                self._schema(spec, capabilities.schema_dialect)
            except ValueError as error:
                raise ToolConfigurationError(f"{spec.name}: {error}") from error

    async def invoke(
        self,
        call: ToolCallRequest,
        context: ToolContext,
        *,
        allowed: Collection[str],
        timeout_s: float,
    ) -> ToolOutcome:
        """Chạy một tool call. Mọi lỗi thành mã trong ToolOutcome, trừ CancelledError.

        CancelledError (client ngắt, lượt bị huỷ) luôn được truyền lên: không bao
        giờ biến thành tool_failed.
        """
        started_at = perf_counter()

        def failed(code: str, detail: str | None = None) -> ToolOutcome:
            return ToolOutcome(
                tool_call_id=call.id,
                name=call.name,
                error_code=code,
                error_detail=detail,
                latency_ms=_elapsed_ms(started_at),
            )

        spec = self._specs.get(call.name)
        if spec is None:
            return failed("tool_not_found", f"unknown tool {call.name!r}")
        if call.name not in allowed:
            return failed("tool_not_allowed")
        def invalid(detail: str) -> ToolOutcome:
            if spec.on_invalid_args is not None:
                try:
                    spec.on_invalid_args(call.arguments_raw or "", detail, context)
                except Exception:
                    logger.exception("agent tool invalid-args hook failed tool=%s", spec.name)
            return failed("tool_invalid_args", detail)

        try:
            raw = json.loads(call.arguments_raw or "{}")
        except ValueError:
            return invalid("arguments is not valid JSON")
        if not isinstance(raw, dict):
            return invalid("arguments must be a JSON object")
        try:
            arguments = spec.input_model.model_validate(raw)
        except ValidationError as error:
            return invalid(_summarize(error))
        timeout_s = min(timeout_s, spec.timeout_s)
        if timeout_s <= 0:
            return failed("tool_timeout")

        try:
            async with asyncio.timeout(timeout_s):
                output = await spec.run(arguments, context)
        except TimeoutError:
            logger.warning("agent tool timed out tool=%s timeout_s=%.1f", spec.name, timeout_s)
            return failed("tool_timeout")
        except ToolRejected as rejected:
            return failed(rejected.code, rejected.detail)
        except Exception:
            # Chi tiết chỉ vào log; LLM chỉ nhận mã lỗi.
            logger.exception("agent tool failed tool=%s", spec.name)
            return failed("tool_failed")

        if not isinstance(output, spec.output_model):
            logger.error("agent tool returned invalid output tool=%s", spec.name)
            return failed("tool_invalid_output")
        return ToolOutcome(
            tool_call_id=call.id,
            name=call.name,
            output=output,
            latency_ms=_elapsed_ms(started_at),
        )

    def _schema(self, spec: ToolSpec, dialect: SchemaDialect) -> dict[str, Any]:
        key = (spec.name, dialect)
        if key not in self._schemas:
            self._schemas[key] = to_provider_schema(spec.input_model, dialect)
        return self._schemas[key]


def _summarize(error: ValidationError) -> str:
    """Vị trí và lý do lỗi, không lặp lại giá trị LLM đã gửi."""
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or '<root>'}: {item['msg']}"
        for item in error.errors()[:5]
    )


def _elapsed_ms(started_at: float) -> int:
    return round((perf_counter() - started_at) * 1000)
