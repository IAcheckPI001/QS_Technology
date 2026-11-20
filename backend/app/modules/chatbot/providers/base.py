"""Hợp đồng provider mà luồng agent cần (tool calling)."""

from typing import Any, Protocol, runtime_checkable

from app.modules.chatbot.schemas.system import (
    AssistantTurn,
    LLMCapabilities,
    ModelProvider,
    ToolChoice,
)


class ProviderTransientError(RuntimeError):
    """Lỗi tạm thời của provider (429, 5xx, mất kết nối): gọi lại có thể thành công.

    Provider tự đổi lỗi SDK sang lỗi này để runner thử lại mà không biết SDK cụ thể. Hết giờ
    vẫn là `TimeoutError`. `status_code`/`code` được tracing ghi lên span (`http_status`).
    """

    def __init__(self, reason: str, *, status_code: int | None = None, code: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code
        self.code = code


@runtime_checkable
class ToolCallingProvider(Protocol):
    """Provider điều khiển vòng lặp agent.

    Mỗi implementation tự khai báo `capabilities`; startup từ chối bật agent khi
    capability không đủ, thay vì để lỗi xuất hiện giữa lượt chat. Deadline chung của lượt do
    người gọi áp; provider được đặt timeout mỗi request ngắn hơn một chút (không tự thử lại),
    để lỗi hết giờ mang theo giai đoạn (kết nối hay chờ phản hồi) thay vì chỉ bị huỷ.
    Lỗi tạm thời trả `TimeoutError` hoặc `ProviderTransientError`; runner quyết định thử lại.
    """

    kind: ModelProvider

    @property
    def model(self) -> str: ...

    @property
    def capabilities(self) -> LLMCapabilities: ...

    async def chat_complete_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        tool_choice: ToolChoice = "auto",
        parallel_tool_calls: bool = True,
        max_tokens: int = 1200,
    ) -> AssistantTurn: ...
