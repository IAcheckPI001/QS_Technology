"""B2 (FRONTEND_REQUIREMENTS 19.4–19.7, 19.12): bộ lọc, cursor, danh sách/số liệu/đầu trang hội thoại."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.api.v1.router import build_api_router
from app.core.config import Settings
from app.db.models.history import ChatConversation
from app.modules.chatbot.dependencies import get_conversation_repository, get_history_repository
from app.modules.chatbot.repositories.conversation_repository import (
    ConversationListRow,
    ConversationRepository,
    ConversationTotals,
    TurnMatch,
)
from app.modules.chatbot.repositories.history_repository import HistoryPage
from app.modules.chatbot.routers import router
from app.modules.chatbot.routers.workspace import conversation_router
from app.modules.chatbot.services.conversation_filters import (
    ConversationQueryError,
    SearchTerms,
    build_filters,
    date_range,
    decode_cursor,
    encode_cursor,
    fold,
)

T0 = datetime(2026, 11, 18, 8, 0, tzinfo=timezone.utc)


def _client(*, conversations=None, history=None) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.include_router(conversation_router)
    app.dependency_overrides[get_conversation_repository] = lambda: conversations or SimpleNamespace()
    app.dependency_overrides[get_history_repository] = lambda: history or SimpleNamespace()
    return TestClient(app)


def _summary(**overrides) -> SimpleNamespace:
    values = dict(
        session_id=uuid4(), channel="crm", started_at=T0 - timedelta(hours=1), last_message_at=T0,
        last_history_id=uuid4(), last_query="Máy F86 báo lỗi", last_status="completed", question_count=3,
        cost_usd=0.002, has_handoff=False, has_tool_errors=True, product_models=["F86"], ticket_id=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


class _Conversations:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def search(self, filters, *, limit, after=None):
        self.calls.append((filters, limit, after))
        return self.rows[:limit] if limit else self.rows


# --- bộ lọc thuần --------------------------------------------------------------------------------

def test_fold_matches_postgres_unaccent_for_vietnamese():
    assert fold("Đổi cảm biến báo lỗi ĐƯỜNG") == "doi cam bien bao loi duong"


def test_search_terms_split_fold_and_drop_short_tokens():
    terms = SearchTerms.parse("  Cảm  biến a lỗi cảm ")
    assert terms.tokens == ("cam", "bien", "loi")
    assert terms.uuid is None
    assert SearchTerms.parse("   ") is None


def test_search_terms_recognise_uuid_and_ticket():
    session = uuid4()
    assert SearchTerms.parse(str(session)).uuid == session
    assert SearchTerms.parse("#TK-1048").exact == "TK-1048"


def test_date_range_uses_vietnam_day_boundaries():
    start, end = date_range(date(2026, 11, 10), date(2026, 11, 11), today=date(2026, 11, 18))
    assert start == datetime(2026, 11, 9, 17, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 11, 11, 17, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("from_date, to_date", [
    (date(2026, 11, 10), None),
    (date(2026, 11, 12), date(2026, 11, 10)),
    (date(2026, 11, 10), date(2026, 11, 19)),
    (date(2025, 1, 1), date(2026, 11, 18)),
])
def test_invalid_date_ranges(from_date, to_date):
    with pytest.raises(ConversationQueryError) as error:
        date_range(from_date, to_date, today=date(2026, 11, 18))
    assert error.value.code == "invalid_date_range"


def test_cursor_round_trip_and_filter_mismatch():
    filters = build_filters(q="F86", channel="crm")
    ident = uuid4()
    cursor = encode_cursor(T0, ident, filters)
    assert decode_cursor(cursor, filters) == (T0, ident)
    with pytest.raises(ConversationQueryError):
        decode_cursor(cursor, build_filters(q="F54", channel="crm"))
    with pytest.raises(ConversationQueryError):
        decode_cursor("không-phải-cursor", filters)


def test_conditions_render_unaccent_like_with_escape():
    filters = build_filters(q="lỗi 100%", status="handoff", product_models=["F86"])
    query = select(ChatConversation).where(*ConversationRepository(None)._conditions(filters))
    compiled = query.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "public.immutable_unaccent(lower(" in sql
    assert "ESCAPE" in sql
    assert "has_handoff IS true" in sql
    assert "%loi%" in compiled.params.values()
    assert "%100\\%%" in compiled.params.values()


# --- GET /chatbot/conversations (B2) -----------------------------------------------------------------

def test_list_b2_returns_summary_fields_match_and_next_cursor():
    rows = [
        ConversationListRow(
            summary=_summary(last_message_at=T0 - timedelta(minutes=index)),
            model="gpt-4o-mini",
            total_tokens=50,
            match=TurnMatch(uuid4(), 2, "Đổi cảm biến"),
        )
        for index in range(3)
    ]
    conversations = _Conversations(rows)

    response = _client(conversations=conversations).get(
        "/chatbot/conversations",
        params={"q": "cam bien", "channel": "crm", "product_model": ["F86", "F54"], "limit": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["conversations"]) == 2
    first = body["conversations"][0]
    assert first["question_count"] == 3
    assert first["has_tool_errors"] is True
    assert first["cost_vnd"] > 0
    assert first["match"]["turn_number"] == 2
    assert body["total"] is None and body["next_cursor"]
    filters, limit, _ = conversations.calls[0]
    assert limit == 3  # lấy thêm một dòng để biết còn trang sau
    assert filters.terms.tokens == ("cam", "bien")
    assert filters.product_models == ("F86", "F54")

    second = _client(conversations=conversations).get(
        "/chatbot/conversations",
        params={"q": "cam bien", "channel": "crm", "product_model": ["F86", "F54"], "limit": 2,
                "cursor": body["next_cursor"]},
    )
    assert second.status_code == 200
    assert conversations.calls[1][2] == (rows[1].summary.last_message_at, rows[1].summary.session_id)


def test_list_b2_last_page_has_no_cursor():
    conversations = _Conversations([ConversationListRow(summary=_summary())])
    body = _client(conversations=conversations).get("/chatbot/conversations", params={"limit": 25}).json()
    assert body["next_cursor"] is None


def test_list_rejects_cursor_of_other_filters():
    cursor = encode_cursor(T0, uuid4(), build_filters(q="F54"))
    response = _client(conversations=_Conversations([])).get(
        "/chatbot/conversations", params={"q": "F86", "limit": 25, "cursor": cursor},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_cursor"


def test_list_rejects_invalid_date_range():
    response = _client(conversations=_Conversations([])).get(
        "/chatbot/conversations", params={"from": "2026-11-10", "limit": 25},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_date_range"


def test_status_handoff_uses_b2_path():
    conversations = _Conversations([])
    response = _client(conversations=conversations).get("/chatbot/conversations", params={"status": "handoff"})
    assert response.status_code == 200
    assert conversations.calls[0][0].status == "handoff"


# --- metrics, đầu trang -----------------------------------------------------------------------------

def test_metrics_uses_same_filters():
    seen = []

    async def totals(filters):
        seen.append(filters)
        return ConversationTotals(conversation_count=4, handoff_count=1, question_count=9, cost_usd=0.01)

    response = _client(conversations=SimpleNamespace(totals=totals)).get(
        "/chatbot/conversations/metrics", params={"status": "error", "channel": "website"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "conversation_count": 4, "handoff_count": 1, "question_count": 9, "cost_usd": 0.01, "cost_vnd": 260.0,
    }
    assert seen[0].status == "error" and seen[0].channel == "website"


def test_conversation_detail_and_404():
    row = ConversationListRow(summary=_summary(), model="gpt-4o-mini", acting_user_id="crm-user-7")

    async def get(session_id):
        return row if session_id == row.summary.session_id else None

    client = _client(conversations=SimpleNamespace(get=get))
    body = client.get(f"/chatbot/conversations/{row.summary.session_id}").json()
    assert body["acting_user_id"] == "crm-user-7"
    assert body["question_count"] == 3
    missing = client.get(f"/chatbot/conversations/{uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "session_not_found"


def test_new_routes_are_behind_config_flag():
    def paths(enabled: bool) -> set[str]:
        config = Settings(DATABASE_URL="postgresql+asyncpg://u:p@h/db", WORKSPACE_CONVERSATION_API_ENABLED=enabled)
        app = FastAPI()
        app.include_router(build_api_router(config))
        return set(app.openapi()["paths"])

    assert "/chatbot/conversations/metrics" not in paths(False)
    assert "/chatbot/conversations/metrics" in paths(True)
    assert "/chatbot/conversations" in paths(False)


# --- GET /history có limit ----------------------------------------------------------------------------

def _turn(session_id, minutes, latency=None):
    return SimpleNamespace(
        id=uuid4(), session_id=session_id, query_origin=f"Câu {minutes}", answer="…", status="completed",
        created_at=T0 + timedelta(minutes=minutes), updated_date=T0 + timedelta(minutes=minutes),
        channel="website", latency_ms=latency,
    )


def test_history_page_numbers_turns_and_returns_cursor():
    session_id = uuid4()
    turns = [_turn(session_id, 5, latency=1500), _turn(session_id, 6)]
    calls = []

    async def history_page(*, session_id, limit, before):
        calls.append((limit, before))
        return HistoryPage(rows=turns, has_more=True, first_turn_number=4)

    async def traced(ids):
        return {turns[1].id}

    history = SimpleNamespace(history_page=history_page, traced_history_ids=traced)
    body = _client(history=history).get(f"/chatbot/sessions/{session_id}/history", params={"limit": 2}).json()

    assert [message["turn_number"] for message in body["messages"]] == [4, 5]
    assert [message["has_trace"] for message in body["messages"]] == [False, True]
    assert body["messages"][0]["asked_at"].startswith("2026-11-18T08:04:58.5")
    assert decode_cursor(body["next_cursor"]) == (turns[0].created_at, turns[0].id)

    _client(history=history).get(
        f"/chatbot/sessions/{session_id}/history", params={"limit": 2, "cursor": body["next_cursor"]},
    )
    assert calls[1] == (2, (turns[0].created_at, turns[0].id))


def test_history_rejects_bad_cursor():
    response = _client(history=SimpleNamespace()).get(
        f"/chatbot/sessions/{uuid4()}/history", params={"limit": 2, "cursor": "xx"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_cursor"
