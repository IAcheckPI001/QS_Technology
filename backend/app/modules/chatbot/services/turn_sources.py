"""Tóm tắt nguồn câu trả lời của một lượt từ dòng chat_history (FRONTEND_REQUIREMENTS 19.14, 19.15).

Hàm thuần, đọc `retrieval_snapshot` đã lưu (không truy vấn thêm): `chunks`, `retrieval_status`,
`agent_steps`. Dùng chung cho GET /history (nhãn dưới mỗi lượt) và GET /retrieval?history_id.
"""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from app.modules.chatbot.schemas.history import (
    AgentStepItem,
    AnswerSource,
    ChatHistoryItem,
    ChunkResult,
    RetrievalSnapshotResponse,
    RetrievalTask,
    ToolUsage,
    TurnSources,
    TurnUsageInfo,
)
from app.modules.chatbot.tools.product_docs import PRODUCT_DOCS_TOOL_NAME

# Status của bước tool không tính là lỗi: thành công, hoặc dùng lại kết quả của lần gọi trùng.
_TOOL_OK = frozenset({"ok", "deduplicated"})
_CRM_TOOL_PREFIX = "crm_"


def tool_usage(agent_steps: Any) -> list[ToolUsage]:
    """Gom các bước `kind=tool` theo tên, giữ thứ tự gọi lần đầu; bỏ công cụ tra tài liệu."""
    usage: dict[str, ToolUsage] = {}
    for step in agent_steps if isinstance(agent_steps, list) else []:
        if not isinstance(step, Mapping) or step.get("kind") != "tool":
            continue
        name = step.get("name")
        if not isinstance(name, str) or not name or name == PRODUCT_DOCS_TOOL_NAME:
            continue
        item = usage.setdefault(name, ToolUsage(name=name))
        item.calls += 1
        status = step.get("status")
        if status not in _TOOL_OK:
            item.failed += 1
            code = status if isinstance(status, str) and status else "tool_failed"
            item.errors[code] = item.errors.get(code, 0) + 1
    return list(usage.values())


def _answer_source(searched: bool, crm: bool) -> AnswerSource:
    if searched and crm:
        return "documents_and_crm"
    if searched:
        return "documents"
    if crm:
        return "crm_data"
    return "direct"


def summarize_turn(snapshot: Mapping[str, Any] | None) -> TurnSources:
    """Nguồn của lượt từ `chat_history.retrieval_snapshot` (None → `none`)."""
    if not isinstance(snapshot, Mapping):
        return TurnSources(answer_source="none")
    chunks = snapshot.get("chunks")
    chunk_count = len(chunks) if isinstance(chunks, list) else 0
    status = snapshot.get("retrieval_status")
    retrieval_status = status if isinstance(status, str) else None
    tools = tool_usage(snapshot.get("agent_steps"))
    # Có tra cứu tài liệu: có task retrieve (status khác not_applicable), hoặc bản ghi cũ chưa có
    # retrieval_status nhưng có chunk.
    searched = (retrieval_status is not None and retrieval_status != "not_applicable") or chunk_count > 0
    crm = any(tool.name.startswith(_CRM_TOOL_PREFIX) for tool in tools)
    return TurnSources(
        answer_source=_answer_source(searched, crm),
        retrieval_status=retrieval_status,
        chunk_count=chunk_count,
        tools=tools,
        has_tool_errors=any(tool.failed for tool in tools),
    )


def usage_info(row: Any) -> TurnUsageInfo | None:
    """Nguồn số liệu token/chi phí của lượt (B3): `snapshot["usage"]` có thì là usage thật."""
    snapshot = getattr(row, "retrieval_snapshot", None)
    usage = snapshot.get("usage") if isinstance(snapshot, Mapping) else None
    if isinstance(usage, Mapping) and usage.get("source") == "trace":
        def count(key: str) -> int | None:
            value = usage.get(key)
            return int(value) if isinstance(value, int | float) and not isinstance(value, bool) else None

        models = usage.get("unpriced_models")
        return TurnUsageInfo(
            source="trace",
            llm_calls=count("llm_calls"),
            cached_input_tokens=count("cached_input_tokens"),
            embedding_tokens=count("embedding_tokens"),
            unpriced_models=[str(model) for model in models] if isinstance(models, list) else [],
        )
    if (getattr(row, "input_tokens", 0) or 0) or (getattr(row, "output_tokens", 0) or 0):
        return TurnUsageInfo(source="estimate")
    return None


def history_item(row: Any, usd_to_vnd_rate: float) -> ChatHistoryItem:
    """Một lượt của GET /history kèm tóm tắt nguồn (B5), nguồn số liệu và chi phí VND (B3)."""
    item = ChatHistoryItem.model_validate(row)
    cost = item.cost_usd
    return item.model_copy(update={
        "sources": summarize_turn(getattr(row, "retrieval_snapshot", None)),
        "usage": usage_info(row),
        "cost_vnd": None if cost is None else round(cost * usd_to_vnd_rate, 2),
    })


def _models(model_cls, items: Any) -> list:
    """Dựng danh sách schema từ JSON đã lưu, bỏ phần tử không đúng dạng (bản ghi cũ/lỗi)."""
    out = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, Mapping):
            try:
                out.append(model_cls.model_validate(item))
            except ValueError:
                continue
    return out


def retrieval_view(session_id: UUID, row: Any) -> RetrievalSnapshotResponse:
    """Response của GET /retrieval cho một lượt; lượt không có snapshot trả danh sách rỗng."""
    raw = getattr(row, "retrieval_snapshot", None)
    snapshot = raw if isinstance(raw, Mapping) else {}
    chunks = [ChunkResult.model_validate(chunk) for chunk in snapshot.get("chunks") or []]
    answered_without_tools = snapshot.get("answered_without_tools")
    return RetrievalSnapshotResponse(
        session_id=session_id,
        history_id=row.id,
        query=snapshot.get("query") or row.query_origin,
        model=snapshot.get("model") or getattr(row, "model", None),
        product_models=snapshot.get("product_models") or [],
        highest_score=max((chunk.score for chunk in chunks), default=None),
        latency_ms=snapshot.get("latency_ms"),
        total_tokens=getattr(row, "total_tokens", 0) or 0,
        retrieval_status=snapshot.get("retrieval_status"),
        chunks=chunks,
        turn_status=getattr(row, "status", None),
        sources=summarize_turn(raw),
        retrieval_tasks=_models(RetrievalTask, snapshot.get("retrieval_tasks")),
        agent_steps=_models(AgentStepItem, snapshot.get("agent_steps")),
        answered_without_tools=answered_without_tools if isinstance(answered_without_tools, bool) else None,
        invalid_citations=[str(item) for item in snapshot.get("invalid_citations") or []],
    )
