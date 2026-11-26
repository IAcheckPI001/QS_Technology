"""Event SSE `status`: dòng hoạt động AI của widget (WU-17 đợt 3A, sau cờ `CHAT_STATUS_EVENTS_ENABLED`).

Không phát ở từng chỗ trong code: `StatusEmitter` nghe mốc mở/đóng span của tracing (`core.tracing.listen`) và ánh
xạ span đã có (stage, tác vụ tra cứu, tool của agent) sang event. Thêm/đổi bước sau này chỉ cần sửa bảng ánh xạ ở
đây. Event chỉ có mã bước, trạng thái, số đếm và định danh (model, mã tài liệu, tên tool, mã lỗi); không có câu
chữ, câu hỏi, nội dung tài liệu hay dữ liệu CRM. Câu hiển thị do widget dịch (src/chatbot/activity/activityModel.js).

Contract: docs/ai/api_guidelines.md (event `status`).
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar, Token
from typing import Any

from app.core.tracing import STATUS_OK, Span

StatusEvent = dict[str, Any]

# Đang ở trong một lần gọi tool của agent: tool `product_docs_ask` chạy lại cả pipeline tra cứu bên trong; các
# bước lồng đó gộp vào một dòng của tool, không hiện riêng.
_inside_tool: ContextVar[bool] = ContextVar("status_inside_tool", default=False)
_OK_TOOL_STATUSES = {STATUS_OK, "deduplicated"}


def _as_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _str_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


class StatusEmitter:
    """Bộ nghe span → event `status`. `put` nhận dict event (đồng bộ, không chặn)."""

    def __init__(self, put: Callable[[StatusEvent], None]) -> None:
        self._put = put
        self._tool_tokens: dict[int, Token[bool]] = {}
        self._agent_open = False

    def __call__(self, phase: str, span: Span) -> None:
        name = span.name
        if name.startswith("tool."):
            self._tool(phase, span, name[len("tool."):])
            return
        if _inside_tool.get():
            return
        handler = getattr(self, "_" + name.replace(".", "_"), None)
        if handler is not None:
            handler(phase, span)

    def _emit(self, event_id: str, step: str, state: str, **fields: object) -> None:
        event: StatusEvent = {"id": event_id, "step": step, "state": state}
        event.update({key: value for key, value in fields.items() if value is not None and value != []})
        self._put(event)

    @staticmethod
    def _failed(span: Span) -> bool:
        return span.status != STATUS_OK

    # --- Các bước chung ---
    def _stage_security(self, phase: str, span: Span) -> None:
        if phase == "start":
            self._emit("security", "security", "running")
        elif span.attributes.get("action") == "block":
            self._emit("security", "security", "error", code="request_blocked")
        else:
            self._emit("security", "security", "error" if self._failed(span) else "done")

    def _stage_context_load(self, phase: str, span: Span) -> None:
        if phase == "start":
            self._emit("context", "context", "running")
        else:
            self._emit("context", "context", "error" if self._failed(span) else "done",
                       turns=_as_int(span.attributes.get("history_messages")))

    # --- Kênh website (pipeline) ---
    def _stage_analysis(self, phase: str, span: Span) -> None:
        if phase == "start":
            self._emit("analysis", "analysis", "running")
            return
        intents = _str_list(span.attributes.get("intents"))
        self._emit("analysis", "analysis", "error" if self._failed(span) else "done",
                   intent=intents[0] if intents else None,
                   models=_str_list(span.attributes.get("product_models")))

    def _task_retrieve(self, phase: str, span: Span) -> None:
        task_id = span.attributes.get("task_id") or "retrieval"
        event_id = f"retrieval:{task_id}"
        target = span.attributes.get("target")
        if phase == "start":
            self._emit(event_id, "retrieval", "running", target=target)
            return
        if self._failed(span):
            self._emit(event_id, "retrieval", "error", target=target, code="retrieval_error")
            return
        hits = _as_int(span.attributes.get("hits")) or 0
        if span.attributes.get("no_docs") or hits == 0:
            self._emit(event_id, "retrieval", "warn", target=target, count=0)
            return
        score = span.attributes.get("best_similarity")
        self._emit(event_id, "retrieval", "done", target=target, count=hits,
                   score=score if isinstance(score, int | float) else None,
                   docs=_str_list(span.attributes.get("doc_ids")))

    def _stage_direct(self, phase: str, span: Span) -> None:
        if phase != "end":
            return
        code = str(span.attributes.get("code") or "")
        step = "handoff" if code.startswith("handoff") else "direct"
        self._emit(step, step, "done")

    def _stage_compose(self, phase: str, span: Span) -> None:
        self._emit("compose", "compose", "running" if phase == "start" else ("error" if self._failed(span) else "done"))

    # --- Kênh CRM (agent) ---
    def _agent_run(self, phase: str, span: Span) -> None:
        if phase == "start":
            self._agent_open = True
            self._emit("analysis", "analysis", "running")
            return
        if self._agent_open:   # agent trả lời ngay, không gọi tool
            self._agent_open = False
            self._emit("analysis", "analysis", "done")
        self._emit("compose", "compose", "error" if self._failed(span) else "done")

    def _llm_chat_tools(self, phase: str, span: Span) -> None:
        # Lần gọi cuối (tool_choice="none") là bước soạn câu trả lời của agent.
        if phase == "start" and span.attributes.get("tool_choice") == "none":
            self._close_agent_analysis()
            self._emit("compose", "compose", "running")

    def _close_agent_analysis(self) -> None:
        if self._agent_open:
            self._agent_open = False
            self._emit("analysis", "analysis", "done")

    def _tool(self, phase: str, span: Span, tool: str) -> None:
        event_id = f"tool:{span.attributes.get('tool_call_id') or id(span)}"
        if phase == "start":
            if _inside_tool.get():   # tool lồng trong tool: gộp vào dòng của tool ngoài
                return
            self._close_agent_analysis()
            self._tool_tokens[id(span)] = _inside_tool.set(True)
            self._emit(event_id, "tool", "running", tool=tool)
            return
        token = self._tool_tokens.pop(id(span), None)
        if token is None:   # đầu "start" đã bị bỏ qua (tool lồng)
            return
        try:
            _inside_tool.reset(token)
        except ValueError:   # đóng ở context khác: chỉ cần đặt lại cờ
            _inside_tool.set(False)
        attributes = span.attributes
        if span.status not in _OK_TOOL_STATUSES:
            state = "retry" if attributes.get("repairable") else "error"
            self._emit(event_id, "tool", state, tool=tool, code=span.status)
            return
        self._emit(event_id, "tool", "done", tool=tool,
                   rows=_as_int(attributes.get("returned")),
                   count=_as_int(attributes.get("sources")))
