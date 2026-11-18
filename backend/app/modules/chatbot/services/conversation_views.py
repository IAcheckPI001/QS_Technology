"""Dựng response danh sách/đầu trang/số liệu hội thoại từ dòng của ConversationRepository (B2)."""

from __future__ import annotations

from app.modules.chatbot.repositories.conversation_repository import ConversationListRow, ConversationTotals
from app.modules.chatbot.schemas.history import (
    ConversationDetail,
    ConversationMatch,
    ConversationMetricsResponse,
    ConversationSummary,
)


def _vnd(cost_usd: float, rate: float) -> float:
    return round(cost_usd * rate, 2)


def conversation_summary(row: ConversationListRow, usd_to_vnd_rate: float) -> ConversationSummary:
    summary = row.summary
    cost = float(summary.cost_usd or 0)
    return ConversationSummary(
        session_id=summary.session_id,
        model=row.model,
        product_models=list(summary.product_models or []),
        ticket_id=summary.ticket_id,
        last_query=summary.last_query,
        channel=summary.channel,
        created_at=summary.started_at,
        updated_date=summary.last_message_at,
        status=summary.last_status,
        total_tokens=row.total_tokens,
        cost_usd=cost,
        question_count=summary.question_count,
        has_handoff=summary.has_handoff,
        has_tool_errors=summary.has_tool_errors,
        cost_vnd=_vnd(cost, usd_to_vnd_rate),
        match=ConversationMatch(
            history_id=row.match.history_id, turn_number=row.match.turn_number, query=row.match.query,
        ) if row.match else None,
    )


def conversation_detail(row: ConversationListRow, usd_to_vnd_rate: float) -> ConversationDetail:
    return ConversationDetail(
        **conversation_summary(row, usd_to_vnd_rate).model_dump(),
        acting_user_id=row.acting_user_id,
    )


def conversation_metrics(totals: ConversationTotals, usd_to_vnd_rate: float) -> ConversationMetricsResponse:
    return ConversationMetricsResponse(
        conversation_count=totals.conversation_count,
        handoff_count=totals.handoff_count,
        question_count=totals.question_count,
        cost_usd=totals.cost_usd,
        cost_vnd=_vnd(totals.cost_usd, usd_to_vnd_rate),
    )
