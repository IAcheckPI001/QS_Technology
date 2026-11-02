"""Hợp đồng của luồng agent: capability provider, tool-call protocol và trace từng bước."""

from typing import Literal, TypeVar

from pydantic import Field

from ..default import NonEmptyStr, NonNegInt, SystemModel
from .orchestration import ExecutionPlan

SchemaDialect = Literal["openai_strict", "json_schema_basic"]
ToolChoice = Literal["auto", "none"]


class LLMCapabilities(SystemModel):
    """Khả năng tool-calling do implementation provider tự khai báo (không dò lúc chạy).

    Không giả định mọi endpoint OpenAI-compatible đều hỗ trợ đủ: agent chỉ được
    bật khi provider khai báo `tool_calling` và `tool_choice_none`.
    """

    tool_calling: bool = False
    parallel_tool_calls: bool = False
    tool_choice_none: bool = False
    tool_choice_required: bool = False
    schema_dialect: SchemaDialect = "json_schema_basic"


class ToolCallRequest(SystemModel):
    id: NonEmptyStr
    name: str
    # Chuỗi JSON nguyên bản của provider; registry mới parse và validate.
    arguments_raw: str


class TokenUsage(SystemModel):
    input_tokens: NonNegInt = 0
    output_tokens: NonNegInt = 0


class AssistantTurn(SystemModel):
    """Một response của provider: câu trả lời, các tool call, hoặc cả hai."""

    content: str | None = None
    tool_calls: list[ToolCallRequest] = Field(default_factory=list)
    finish_reason: str | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)


class AgentStep(SystemModel):
    """Một lần gọi LLM hoặc một tool call của lượt agent (không chứa nội dung)."""

    step: NonNegInt
    kind: Literal["llm", "tool"]
    name: str | None = None              # tên tool, hoặc tool_choice của lần gọi LLM
    tool_call_id: str | None = None
    # "ok", "deduplicated" (dùng lại kết quả call trùng trước đó) hoặc mã lỗi (tool_timeout, ...)
    status: NonEmptyStr
    latency_ms: NonNegInt = 0
    finish_reason: str | None = None


class AgentToolPlan(SystemModel):
    """Plan retrieval đã chạy bên trong một tool call (dùng cho retrieval snapshot)."""

    tool_call_id: NonEmptyStr
    question: NonEmptyStr
    plan: ExecutionPlan
    # Model của các sub-query đã trả lời được bằng nguồn (cập nhật ngữ cảnh model của phiên).
    product_models: list[NonEmptyStr] = Field(default_factory=list)


class ToolTurnState(SystemModel):
    """Base cho state riêng của một tool trong một lượt agent.

    Mỗi tool tự định nghĩa subclass (vd. model đã xác nhận của tool tài liệu);
    orchestrator không đọc nội dung, nên thêm tool không phải sửa AgentRun.
    """


StateT = TypeVar("StateT", bound=ToolTurnState)


class AgentRun(SystemModel):
    """State chung của một lượt agent, không thuộc riêng tool nào."""

    steps: list[AgentStep] = Field(default_factory=list)
    # S# -> nội dung nguồn mọi tool đã trả cho agent trong lượt (kiểm tra citation).
    source_texts: dict[str, str] = Field(default_factory=dict)
    # [S#] trong câu trả lời cuối không phải nguồn của lượt: đã bị bỏ khỏi câu trả lời.
    invalid_citations: list[NonEmptyStr] = Field(default_factory=list)
    # State riêng theo tool, khóa là tên class state (mỗi class thuộc một tool).
    tool_states: dict[str, ToolTurnState] = Field(default_factory=dict)

    def add_step(self, step: AgentStep) -> None:
        self.steps = [*self.steps, step]

    def add_source_texts(self, texts: dict[str, str]) -> None:
        self.source_texts = {**self.source_texts, **texts}

    def tool_state(self, state_type: type[StateT]) -> StateT | None:
        state = self.tool_states.get(state_type.__name__)
        return state if isinstance(state, state_type) else None

    def ensure_tool_state(self, state_type: type[StateT]) -> StateT:
        state = self.tool_state(state_type)
        if state is None:
            state = state_type()
            self.tool_states[state_type.__name__] = state
        return state

    @property
    def answered_without_tools(self) -> bool:
        return not any(step.kind == "tool" for step in self.steps)
