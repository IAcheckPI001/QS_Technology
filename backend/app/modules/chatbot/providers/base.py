"""Hợp đồng provider mà luồng agent cần (tool calling)."""

from typing import Any, Protocol, runtime_checkable

from app.modules.chatbot.schemas.system import (
    AssistantTurn,
    LLMCapabilities,
    ModelProvider,
    ToolChoice,
)


@runtime_checkable
class ToolCallingProvider(Protocol):
    """Provider điều khiển vòng lặp agent.

    Mỗi implementation tự khai báo `capabilities`; startup từ chối bật agent khi
    capability không đủ, thay vì để lỗi xuất hiện giữa lượt chat. Timeout do
    người gọi áp (deadline chung của lượt), provider không tự đặt.
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
