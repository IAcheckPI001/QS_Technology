import asyncio
from types import SimpleNamespace
from uuid import UUID

from app.modules.chatbot.analysis.analyzer import build_analysis
from app.modules.chatbot.clarification import (
    exhaust_clarification,
    match_confirmation,
    patch_pending,
)
from app.modules.chatbot.extraction.schema_builder import build_output_schema
from app.modules.chatbot.orchestration import build_execution_plan
from app.modules.chatbot.schemas.system import (
    ConversationState,
    Mode,
    PendingClarification,
    TaskKind,
    TaskStatus,
)
from app.modules.chatbot.service import ChatbotService

SESSION_ID = UUID("00000000-0000-0000-0000-000000000001")


def _sub_query(query, intent, models=(), unresolved=(), handoff_reason=None):
    return {
        "standalone_query": query,
        "intent": intent,
        "product_models": list(models),
        "unresolved_mentions": list(unresolved),
        "control_interface": [],
        "spec_attribute": [],
        "handoff_reason": handoff_reason,
        "history_conflict": False,
    }


F84_RAW = [
    _sub_query("F84 khác gì với F54", "compare.product_models", ["F54"], ["F84"]),
    _sub_query("F84 hoạt động như nào", "lookup.product_info", unresolved=["F84"]),
]


def _pending(candidates=("F86",), raws=F84_RAW, mentions=("F84",)):
    return PendingClarification(
        focus=mentions[0] if mentions else "missing_product_model",
        question_type="confirm" if len(candidates) == 1 else "choose",
        candidates=list(candidates),
        llm_raw={"sub_queries": list(raws), "mentions": list(mentions), "reason": "x"},
        ttl=2,
    )


# --- planner: held sub-queries -------------------------------------------------

def test_shared_unknown_mention_holds_every_related_sub_query():
    plan = build_execution_plan(build_analysis(F84_RAW))

    assert [(task.kind, task.status) for task in plan.tasks] == [
        (TaskKind.CLARIFY, TaskStatus.BLOCKED),
        (TaskKind.CLARIFY, TaskStatus.BLOCKED),
    ]


def test_clear_sub_query_is_retrieved_while_ambiguous_one_is_held():
    plan = build_execution_plan(build_analysis([
        _sub_query("F86 có cổng USB không", "lookup.product_info", ["F86"]),
        _sub_query("Hướng dẫn đấu nguồn Astro 6A", "guide.installation", unresolved=["Astro 6A"]),
    ]))

    kinds = {task.kind: task for task in plan.tasks}
    assert kinds[TaskKind.RETRIEVE].sub_query_ids == ["q1"]
    assert kinds[TaskKind.CLARIFY].status is TaskStatus.BLOCKED


# --- matcher -----------------------------------------------------------------

def test_matcher_accepts_alias_confirmation_and_ordinal():
    pending = _pending()
    assert match_confirmation("F86", pending) == "F86"
    assert match_confirmation("f-86 ạ", pending) == "F86"
    assert match_confirmation("Đúng rồi", pending) == "F86"
    assert match_confirmation("cái đầu", pending) == "F86"


def test_matcher_rejects_ambiguous_or_new_questions():
    two = _pending(candidates=("ASTRO_6AH", "ASTRO_6AV"))
    assert match_confirmation("đúng", two) is None
    assert match_confirmation("2", two) == "ASTRO_6AV"
    assert match_confirmation("F86 có cổng USB không?", _pending()) is None
    assert match_confirmation("cho mình hỏi giá bộ này bao nhiêu", _pending()) is None


def test_matcher_returns_unknown_model_like_mention():
    assert match_confirmation("A10", _pending()) == "A10"


# --- patch / resume -------------------------------------------------------------

def test_patch_replaces_mention_and_resolves_without_llm():
    analysis = build_analysis(patch_pending(_pending(), "F86"), resumed=True)

    q1, q2 = analysis.sub_queries
    assert q1.standalone_query == "F86 khác gì với F54"
    assert set(q1.entities.product_models) == {"F54", "F86"}
    assert q2.entities.product_models == ["F86"]
    assert q2.entities.unresolved_mentions == []
    assert not any(task.status is TaskStatus.BLOCKED for task in build_execution_plan(analysis).tasks)


def test_patch_with_unknown_answer_asks_again_then_exhausts():
    analysis = build_analysis(patch_pending(_pending(), "A10"), resumed=True)
    assert analysis.clarification is not None
    assert analysis.clarification.mentions == ["A10"]

    exhausted = exhaust_clarification(analysis)
    plan = build_execution_plan(exhausted)
    assert {task.kind for task in plan.tasks} == {TaskKind.NO_DOCS}
    assert "clarification_exhausted" in exhausted.sub_queries[0].warnings


def test_patch_without_mention_appends_model():
    raws = [_sub_query("Hướng dẫn đấu nguồn", "guide.installation")]
    patched = patch_pending(_pending(candidates=(), raws=raws, mentions=()), "F86")

    assert patched[0]["standalone_query"] == "Hướng dẫn đấu nguồn (F86)"
    assert patched[0]["product_models"] == ["F86"]


def test_output_schema_requires_pending_answer():
    schema = build_output_schema()
    assert "pending_answer" in schema["required"]


# --- service, multi-turn ---------------------------------------------------------

class AnalysisProvider:
    model = "test-model"

    def __init__(self, outputs, chunks=("ok",)):
        self.outputs = list(outputs)
        self.analysis_calls = 0
        self.stream_calls = 0
        self.chunks = list(chunks)
        self.last_analysis_messages = None

    async def chat_complete_json(self, messages, response_format=None):
        self.analysis_calls += 1
        self.last_analysis_messages = messages
        return self.outputs.pop(0)

    async def stream_chat(self, messages):
        self.stream_calls += 1
        for chunk in self.chunks:
            yield chunk


class StoringHistoryRepository:
    def __init__(self, rows=()):
        self.rows = list(rows)

    async def session_exists(self, session_id):
        return bool(self.rows)

    async def list_for_context(self, session_id):
        return [row for row in self.rows if row.status == "completed"]

    async def create(self, **data):
        row = SimpleNamespace(id=f"row-{len(self.rows)}", **data)
        self.rows.append(row)
        return row


def _send(service, message):
    async def collect():
        return [chunk async for chunk in service.stream_reply(message, SESSION_ID)]

    return asyncio.run(collect())


def test_chitchat_only_turn_uses_fixed_reply_without_answer_llm():
    provider = AnalysisProvider([{
        "sub_queries": [_sub_query("Xin chào", "other.chitchat")],
        "pending_answer": None,
    }])
    repository = StoringHistoryRepository()

    chunks = _send(ChatbotService(provider, repository), "Xin chào")

    assert len(chunks) == 1 and "QS Technology" in chunks[0]
    assert provider.stream_calls == 0


def test_handoff_only_turn_uses_reason_reply_and_stays_in_bot_mode():
    provider = AnalysisProvider([{
        "sub_queries": [_sub_query("Giá F86", "handoff.human", ["F86"], handoff_reason="pricing")],
        "pending_answer": None,
    }])
    repository = StoringHistoryRepository()

    chunks = _send(ChatbotService(provider, repository), "Giá F86 bao nhiêu?")

    assert "giá" in chunks[0].lower()
    assert provider.stream_calls == 0
    assert repository.rows[-1].conversation_state["mode"] == "bot"


def test_clarification_round_trip_resumes_without_second_analysis_call():
    provider = AnalysisProvider([{"sub_queries": F84_RAW, "pending_answer": None}])
    repository = StoringHistoryRepository()
    service = ChatbotService(provider, repository)

    _send(service, "F84 khác gì với F54, và nó hoạt động như nào?")
    pending = repository.rows[-1].conversation_state["pending"]
    assert pending["focus"] == "F84"
    assert pending["candidates"] == ["F86"]
    assert repository.rows[-1].conversation_state["clarify_attempts"] == 1

    _send(service, "Đúng rồi")

    assert provider.analysis_calls == 1
    state = repository.rows[-1].conversation_state
    assert state["pending"] is None
    assert state["clarify_attempts"] == 0
    assert "F86" in state["last_models"]


def test_llm_pending_answer_merges_held_and_new_sub_queries():
    provider = AnalysisProvider([
        {"sub_queries": F84_RAW, "pending_answer": None},
        {
            "sub_queries": [_sub_query("F86 có cổng USB không", "lookup.product_info", ["F86"])],
            "pending_answer": "F86",
        },
    ])
    repository = StoringHistoryRepository()
    service = ChatbotService(provider, repository)

    _send(service, "F84 khác gì với F54, và nó hoạt động như nào?")
    _send(service, "F86 nhé, mà nó có cổng USB không?")

    assert provider.analysis_calls == 2
    assert "<pending>" in provider.last_analysis_messages[-1]["content"]
    assert repository.rows[-1].conversation_state["pending"] is None


def test_unknown_reply_twice_stops_asking():
    provider = AnalysisProvider([{"sub_queries": F84_RAW, "pending_answer": None}])
    repository = StoringHistoryRepository()
    service = ChatbotService(provider, repository)

    _send(service, "F84 khác gì với F54, và nó hoạt động như nào?")
    _send(service, "A10")
    assert repository.rows[-1].conversation_state["clarify_attempts"] == 2
    assert repository.rows[-1].conversation_state["pending"]["focus"] == "A10"

    _send(service, "A11")
    state = repository.rows[-1].conversation_state
    assert state["pending"] is None
    assert state["clarify_attempts"] == 0
    assert provider.analysis_calls == 1


def test_agent_mode_skips_bot_pipeline():
    agent_state = ConversationState(mode=Mode.AWAITING_AGENT, ticket_id="T-1")
    repository = StoringHistoryRepository([SimpleNamespace(
        id="row-0", status="completed", query_origin="Giá F86", answer="Đã chuyển",
        conversation_state=agent_state.model_dump(mode="json"),
    )])
    provider = AnalysisProvider([])

    chunks = _send(ChatbotService(provider, repository), "Có ai không?")

    assert "nhân viên" in chunks[0]
    assert provider.analysis_calls == 0 and provider.stream_calls == 0
    assert repository.rows[-1].conversation_state["ticket_id"] == "T-1"
