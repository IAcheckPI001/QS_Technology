

"""RunStats – số liệu vận hành, ghi theo từng lần gọi LLM."""

from enum import StrEnum

from typing import Any

from pydantic import Field, computed_field, model_validator

from ..default import SystemModel, NonNegInt
from .run_context import ModelProvider

class ChatRequest(SystemModel):
    message: str = Field(min_length=1, max_length=1500)

class LLMStage(StrEnum):
    REWRITE = "rewrite"
    THINK = "think"
    COMPACTION = "compaction"
    VERIFY = "verify"


class LLMCall(SystemModel):
    stage: LLMStage
    iteration: NonNegInt | None = None
    provider: ModelProvider
    model: str
    input_tokens: NonNegInt
    output_tokens: NonNegInt
    latency_ms: NonNegInt


class TokenTotal(SystemModel):
    input_tokens: NonNegInt
    output_tokens: NonNegInt


class RunStats(SystemModel):
    llm_calls: list[LLMCall] = Field(default_factory=list)
    latency_ms: NonNegInt = 0          # tổng thời gian cả request, service gán khi kết thúc

    @model_validator(mode="before")
    @classmethod
    def drop_computed_total(cls, data: Any) -> Any:
        # Cho phép đọc lại bản đã model_dump() (có sẵn 'total') từ log/DB.
        if isinstance(data, dict):
            data = {k: v for k, v in data.items() if k != "total"}
        return data

    # total được TÍNH từ llm_calls, không gán tay → không bao giờ lệch.
    @computed_field
    @property
    def total(self) -> TokenTotal:
        return TokenTotal(
            input_tokens=sum(c.input_tokens for c in self.llm_calls),
            output_tokens=sum(c.output_tokens for c in self.llm_calls),
        )

    def record(self, call: LLMCall) -> None:
        self.llm_calls = [*self.llm_calls, call]