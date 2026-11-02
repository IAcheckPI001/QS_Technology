"""Contract của một tool agent: spec, context, kết quả invoke."""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

from app.modules.chatbot.schemas.default import SystemModel
from app.modules.chatbot.schemas.system import AgentRun, RunState, ToolTurnState
from app.modules.chatbot.stages.execution_stage import SourceAllocator


class ToolRejected(Exception):
    """Tool từ chối call vì lý do nghiệp vụ, trước khi làm việc chính.

    Registry trả `code` và `detail` cho LLM để nó tự sửa call. `detail` do tool
    viết: chỉ nêu lý do, không chứa dữ liệu nhạy cảm.
    """

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ToolArgumentError(ToolRejected):
    """Argument hợp lệ về schema nhưng sai về nghiệp vụ (vd. trích nguồn không tồn tại)."""

    def __init__(self, detail: str) -> None:
        super().__init__("tool_invalid_args", detail)


class ToolOutput(SystemModel):
    """Output có kiểu của tool; `to_llm` quyết định cách cắt khi vượt budget token."""

    def to_llm(self, budget_tokens: int, count: Callable[[str], int]) -> dict[str, Any]:
        # Mặc định không cắt: registry trả tool_output_too_large nếu vượt budget.
        return self.model_dump(mode="json")


StateT = TypeVar("StateT", bound=ToolTurnState)


@dataclass(frozen=True)
class ToolContext:
    """Thứ tool được dùng từ lượt cha. Không cho tool ghi vào state cha ngoài các API này."""

    parent_state: RunState
    sources: SourceAllocator
    tool_call_id: str

    def turn_state(self, state_type: type[StateT]) -> StateT:
        """State riêng của tool trong lượt agent (tạo khi gọi lần đầu)."""
        if self.parent_state.agent is None:
            self.parent_state.agent = AgentRun()
        return self.parent_state.agent.ensure_tool_state(state_type)


ToolRun = Callable[[Any, ToolContext], Awaitable[ToolOutput]]


@dataclass(frozen=True)
class ToolSpec:
    """Mọi hành vi riêng của tool khai báo ở đây; orchestrator không biết tool làm gì.

    description: khi nào gọi và input (gửi qua tham số `tools` của provider).
    guide: cách đọc output và bước tiếp theo của riêng tool này; ghép vào system
    prompt chỉ khi principal được dùng tool, để luật của tool này không áp lên tool khác.
    """

    name: str
    description: str
    input_model: type[BaseModel]        # bắt buộc extra="forbid"
    output_model: type[ToolOutput]
    run: ToolRun
    guide: str = ""
    read_only: bool = True
    concurrency_safe: bool = True       # chỉ chạy song song khi mọi tool trong batch đều True
    # Call trùng (cùng argument) trong lượt dùng lại kết quả thành công trước đó.
    # None = theo read_only: tool ghi không bao giờ bị gộp/bỏ qua ngầm.
    deduplicate: bool | None = None
    max_calls_per_turn: int | None = None   # trần riêng, ngoài giới hạn chung của lượt
    timeout_s: float = 20.0
    required_scope: str | None = None   # chưa dùng: điểm gắn phân quyền theo role/scope

    @property
    def deduplicates(self) -> bool:
        return self.read_only if self.deduplicate is None else self.deduplicate


@dataclass(frozen=True)
class ToolOutcome:
    """Kết quả của đúng một tool call; lỗi là mã, không phải exception."""

    tool_call_id: str
    name: str
    output: ToolOutput | None = None
    error_code: str | None = None
    error_detail: str | None = None
    latency_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.error_code is None

    def message_content(self, budget_tokens: int, count: Callable[[str], int]) -> str:
        """Nội dung message role=tool gửi lại cho LLM."""
        if self.output is None:
            payload: dict[str, Any] = {"error": self.error_code}
            if self.error_detail:
                payload["detail"] = self.error_detail
            return _j(payload)
        text = _j(self.output.to_llm(budget_tokens, count))
        if count(text) > budget_tokens:
            return _j({"error": "tool_output_too_large"})
        return text


def _j(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
