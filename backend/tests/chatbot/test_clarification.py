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
from app.modules.chatbot.services import ChatbotService
from tests.chatbot.builders import collect_reply

SESSION_ID = UUID("00000000-0000-0000-0000-000000000001")


def _sub_query(query, intent, models=(), unresolved=(), handoff_reason=None):
    return {
        "standalone_query": query,
        "intent": intent,
        "product_models": list(models),
        "unresolved_mentions": list(unresolved),
        "control_interface": [],
        "spec_attributes": [],
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
    return collect_reply(service, message, SESSION_ID)


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


# --- A/B/C: thiếu model, xung đột ngữ cảnh, model không xác định ------------------

def _dep(query, intent, dependency, models=(), unresolved=(), conflict=False):
    raw = _sub_query(query, intent, models, unresolved)
    raw.update(model_dependency=dependency, history_conflict=conflict)
    return raw


def test_missing_model_specific_question_blocks_with_covered_candidates():
    analysis = build_analysis([
        _dep("Hướng dẫn cấu hình thông số", "guide.configuration", "model_specific"),
    ])

    sub_query = analysis.sub_queries[0]
    assert sub_query.route.value == "clarify"
    assert sub_query.clarification.reason == "missing_product_model"
    assert sub_query.clarification.blocking is True
    # technical_docs chỉ có tài liệu cho F86
    assert sub_query.clarification.candidates == {"missing_product_model": ["F86"]}


def test_missing_model_general_question_is_answered_then_asks():
    analysis = build_analysis([
        _dep("Macro dùng để làm gì", "guide.configuration", "general"),
    ])

    sub_query = analysis.sub_queries[0]
    assert sub_query.route.value == "retrieve"
    assert sub_query.retrieval_scope.model_filter is None
    assert sub_query.retrieval_scope.answer_mode == "general"
    assert sub_query.clarification.blocking is False
    plan = build_execution_plan(analysis)
    assert [task.kind for task in plan.tasks] == [TaskKind.RETRIEVE]


def test_two_models_in_context_ask_which_one_without_llm_flag():
    analysis = build_analysis(
        [_dep("Chân CN1 có chức năng gì", "guide.installation", "model_specific")],
        last_models=["F54", "F86"],
    )

    clarification = analysis.sub_queries[0].clarification
    assert analysis.sub_queries[0].route.value == "clarify"
    assert clarification.reason == "context_conflict"
    assert clarification.candidates == {"context_conflict": ["F54", "F86"]}


def test_single_model_in_context_is_inherited():
    analysis = build_analysis(
        [_dep("Chân CN1 có chức năng gì", "guide.installation", "model_specific")],
        last_models=["F86"],
    )

    sub_query = analysis.sub_queries[0]
    assert sub_query.route.value == "retrieve"
    assert sub_query.entities.product_models == ["F86"]
    assert "inherited_model:F86" in sub_query.warnings


def test_explicit_model_wins_over_context():
    analysis = build_analysis(
        [_dep("Tra cứu CN1 của F86", "guide.installation", "model_specific", models=["F86"])],
        last_models=["F54"],
    )

    sub_query = analysis.sub_queries[0]
    assert sub_query.clarification is None
    assert sub_query.entities.product_models == ["F86"]


def test_guard_drops_model_the_user_never_typed():
    from app.modules.chatbot.extraction.validate_registry import guard_extracted_models

    raw = [_dep("So sánh F54 với F86", "compare.product_models", "model_specific",
                models=["F54", "F86"])]
    guarded = guard_extracted_models(raw, "So sánh F54 với F84")
    analysis = build_analysis(guarded)

    sub_query = analysis.sub_queries[0]
    assert sub_query.entities.product_models == ["F54"]
    assert "model_not_in_text:F86" in sub_query.warnings
    assert sub_query.clarification.reason == "insufficient_models_for_comparison"
    assert guard_extracted_models(raw, "So sánh F54 với F-86") == raw


def test_confirm_reply_resolves_missing_model_candidate():
    provider = AnalysisProvider([{
        "sub_queries": [_dep("Hướng dẫn cấu hình thông số", "guide.configuration", "model_specific")],
        "pending_answer": None,
    }])
    repository = StoringHistoryRepository()
    service = ChatbotService(provider, repository)

    _send(service, "Hướng dẫn cấu hình thông số cho bộ điều khiển")
    pending = repository.rows[-1].conversation_state["pending"]
    assert pending["focus"] == "missing_product_model"
    assert pending["candidates"] == ["F86"]

    _send(service, "Đúng rồi")
    state = repository.rows[-1].conversation_state
    assert provider.analysis_calls == 1
    assert state["pending"] is None
    assert state["last_models"] == ["F86"]


def test_empty_reply_to_clarification_asks_again_then_stops():
    two = {"sub_queries": [], "pending_answer": None}
    provider = AnalysisProvider([{"sub_queries": F84_RAW, "pending_answer": None}, two, two])
    repository = StoringHistoryRepository()
    service = ChatbotService(provider, repository)

    _send(service, "F84 khác gì với F54, và nó hoạt động như nào?")
    _send(service, "ok bạn")
    state = repository.rows[-1].conversation_state
    assert repository.rows[-1].status == "completed"
    assert state["pending"]["focus"] == "F84"
    assert state["clarify_attempts"] == 2

    _send(service, "ừ thì")
    state = repository.rows[-1].conversation_state
    assert state["pending"] is None
    assert state["clarify_attempts"] == 0


# --- chốt chặn khi LLM đánh dấu "general" sai ---------------------------------------

def test_general_flag_ignored_for_installation_with_two_models_in_context():
    analysis = build_analysis(
        [_dep("Cách đấu dây connector CN1", "guide.installation", "general")],
        last_models=["F54", "F86"],
    )

    sub_query = analysis.sub_queries[0]
    assert sub_query.route.value == "clarify"
    assert sub_query.clarification.reason == "context_conflict"
    assert sub_query.clarification.candidates == {"context_conflict": ["F54", "F86"]}


def test_general_flag_ignored_when_query_names_a_specific_code():
    analysis = build_analysis([
        _dep("Tham số #4130 dùng để làm gì", "guide.configuration", "general"),
    ])

    sub_query = analysis.sub_queries[0]
    assert sub_query.route.value == "clarify"
    assert sub_query.clarification.reason == "missing_product_model"
    assert sub_query.clarification.blocking is True


def test_general_flag_kept_for_conceptual_configuration_question():
    analysis = build_analysis(
        [_dep("Macro trong bộ điều khiển dùng để làm gì", "guide.configuration", "general")],
        last_models=["F54", "F86"],
    )

    assert analysis.sub_queries[0].retrieval_scope.answer_mode == "general"


def test_general_turn_retrieves_with_injected_retriever():
    from app.modules.chatbot.retrieval import Retriever, RetrieverConfig
    from app.modules.chatbot.stages.execution_stage import ExecutionStage

    class Embedder:
        async def embed(self, texts):
            return [[0.1, 0.2] for _ in texts]

    class Chunks:
        def __init__(self):
            self.calls = []

        async def match(self, **kwargs):
            self.calls.append(kwargs)
            return []

        async def fetch_by_ids(self, ids):
            return []

    chunks = Chunks()
    provider = AnalysisProvider([{
        "sub_queries": [_dep("Macro dùng để làm gì", "guide.configuration", "general")],
        "pending_answer": None,
    }])
    repository = StoringHistoryRepository()
    service = ChatbotService(
        provider,
        repository,
        execution_stage=ExecutionStage(retriever=Retriever(Embedder(), chunks, RetrieverConfig())),
    )

    _send(service, "Macro trong bộ điều khiển dùng để làm gì?")

    assert chunks.calls and chunks.calls[0]["models"] is None
    assert repository.rows[-1].status == "completed"


# --- P1: last_models cộng dồn, active_model, pending của câu hỏi chung -------------

def _out(*sub_queries, pending_answer=None):
    return {"sub_queries": list(sub_queries), "pending_answer": pending_answer}


def test_latest_single_model_turn_becomes_active_and_is_inherited():
    provider = AnalysisProvider([
        _out(_dep("Giới thiệu F54", "lookup.product_info", "model_specific", models=["F54"])),
        _out(_dep("Giới thiệu F86", "lookup.product_info", "model_specific", models=["F86"])),
        _out(_dep("Chân CN1 có chức năng gì", "guide.installation", "model_specific")),
    ])
    repository = StoringHistoryRepository()
    service = ChatbotService(provider, repository)

    _send(service, "Giới thiệu F54")
    _send(service, "Giới thiệu F86")
    _send(service, "Chân CN1 có chức năng gì?")

    state = repository.rows[-1].conversation_state
    assert state["pending"] is None
    assert state["active_model"] == "F86"
    assert state["last_models"] == ["F54", "F86"]


def test_comparison_turn_clears_active_model_so_next_question_asks():
    provider = AnalysisProvider([
        _out(_dep("So sánh F54 và F86", "compare.product_models", "model_specific",
                  models=["F54", "F86"])),
        _out(_dep("Chân CN1 có chức năng gì", "guide.installation", "model_specific")),
    ])
    repository = StoringHistoryRepository()
    service = ChatbotService(provider, repository)

    _send(service, "So sánh F54 và F86")
    assert repository.rows[-1].conversation_state["active_model"] is None
    _send(service, "Chân CN1 có chức năng gì?")

    pending = repository.rows[-1].conversation_state["pending"]
    assert pending["focus"] == "context_conflict"
    assert pending["candidates"] == ["F54", "F86"]

    _send(service, "F86")
    state = repository.rows[-1].conversation_state
    assert state["pending"] is None
    assert state["active_model"] == "F86"
    assert provider.analysis_calls == 2


def test_previous_models_are_kept_for_comparison_with_active_model():
    provider = AnalysisProvider([
        _out(_dep("Giới thiệu F54", "lookup.product_info", "model_specific", models=["F54"])),
        _out(_dep("Giới thiệu F86", "lookup.product_info", "model_specific", models=["F86"])),
        _out(_dep("Giới thiệu F10T", "lookup.product_info", "model_specific", models=["F10T"])),
        _out(_dep("So sánh F10T với F54 và F86", "compare.product_models", "model_specific",
                  models=["F10T", "F54", "F86"])),
    ])
    repository = StoringHistoryRepository()
    service = ChatbotService(provider, repository)

    for message in ("Giới thiệu F54", "Giới thiệu F86", "Giới thiệu F10T"):
        _send(service, message)
    _send(service, "Nó khác gì so với các model trên?")

    sent_state = provider.last_analysis_messages[-1]["content"]
    assert '"last_models":["F54","F86","F10T"]' in sent_state
    assert '"active_model":"F10T"' in sent_state
    state = repository.rows[-1].conversation_state
    assert set(state["last_models"]) == {"F54", "F86", "F10T"}
    assert state["active_model"] is None


def test_last_models_keep_only_the_most_recent_four():
    outputs = [
        _out(_dep(f"Giới thiệu {model}", "lookup.product_info", "model_specific", models=[model]))
        for model in ("F54", "F86", "F10T", "ASTRO_10S", "F54")
    ]
    provider = AnalysisProvider(outputs)
    repository = StoringHistoryRepository()
    service = ChatbotService(provider, repository)

    for message in ("F54", "F86", "F10T", "Astro 10S", "F54 lần nữa"):
        _send(service, f"Giới thiệu {message}")

    assert repository.rows[-1].conversation_state["last_models"] == [
        "F86", "F10T", "ASTRO_10S", "F54",
    ]


def test_general_answer_leaves_non_blocking_pending_resolved_by_model_reply():
    provider = AnalysisProvider([
        _out(_dep("Macro dùng để làm gì", "guide.configuration", "general")),
    ])
    repository = StoringHistoryRepository()
    service = ChatbotService(provider, repository)

    _send(service, "Macro trong bộ điều khiển dùng để làm gì?")
    pending = repository.rows[-1].conversation_state["pending"]
    assert pending["blocking"] is False
    assert pending["focus"] == "missing_product_model"
    assert pending["candidates"] == ["F86"]
    assert repository.rows[-1].conversation_state["clarify_attempts"] == 0

    _send(service, "F86")
    state = repository.rows[-1].conversation_state
    assert provider.analysis_calls == 1
    assert state["pending"] is None
    assert state["active_model"] == "F86"


def test_acknowledgement_does_not_trigger_non_blocking_pending():
    provider = AnalysisProvider([
        _out(_dep("Macro dùng để làm gì", "guide.configuration", "general")),
        _out(),
    ])
    repository = StoringHistoryRepository()
    service = ChatbotService(provider, repository)

    _send(service, "Macro trong bộ điều khiển dùng để làm gì?")
    assert match_confirmation("ok", PendingClarification.model_validate(
        repository.rows[-1].conversation_state["pending"])) is None

    chunks = _send(service, "ok cảm ơn")

    assert provider.analysis_calls == 2
    assert len(chunks) == 1 and "QS Technology" in chunks[0]
    pending = repository.rows[-1].conversation_state["pending"]
    assert pending is not None and pending["ttl"] == 1


# --- P1: đa ngôn ngữ --------------------------------------------------------------

class RecordingAnalysisProvider(AnalysisProvider):
    def __init__(self, outputs, chunks=("ok",)):
        super().__init__(outputs, chunks)
        self.answer_messages = None

    async def stream_chat(self, messages):
        self.answer_messages = messages
        async for chunk in super().stream_chat(messages):
            yield chunk


def test_english_question_is_normalized_to_vietnamese_and_answered_in_english():
    provider = RecordingAnalysisProvider([{
        **_out(_dep("Địa chỉ công ty QS Technology", "lookup.company_info", "general")),
        "language": "en",
    }])
    repository = StoringHistoryRepository()

    _send(ChatbotService(provider, repository), "Where is QS Technology located?")

    row = repository.rows[-1]
    assert row.query_origin == "Where is QS Technology located?"
    assert row.normalized_query == "Địa chỉ công ty QS Technology"
    assert row.conversation_state["language"] == "en"
    assert "<language>en</language>" in provider.answer_messages[-1]["content"]


def test_chitchat_uses_fixed_reply_for_supported_language_only():
    english = AnalysisProvider([{
        **_out(_dep("Xin chào", "other.chitchat", "general")), "language": "en",
    }])
    chunks = _send(ChatbotService(english, StoringHistoryRepository()), "Hello")
    assert chunks[0].startswith("Hello!") and english.stream_calls == 0

    japanese = RecordingAnalysisProvider([{
        **_out(_dep("Xin chào", "other.chitchat", "general")), "language": "ja",
    }], chunks=("こんにちは",))
    chunks = _send(ChatbotService(japanese, StoringHistoryRepository()), "こんにちは")
    assert chunks == ["こんにちは"] and japanese.stream_calls == 1
    assert "<language>ja</language>" in japanese.answer_messages[-1]["content"]


def test_resumed_turn_without_llm_keeps_session_language():
    provider = RecordingAnalysisProvider([{**_out(*F84_RAW), "language": "en"}])
    repository = StoringHistoryRepository()
    service = ChatbotService(provider, repository)

    _send(service, "How does F84 differ from F54, and how does it work?")
    _send(service, "F86")

    assert provider.analysis_calls == 1
    assert repository.rows[-1].conversation_state["language"] == "en"
    assert "<language>en</language>" in provider.answer_messages[-1]["content"]


def test_reply_language_guess_for_replies_before_analysis():
    from app.util.normalize import guess_reply_language

    assert guess_reply_language("Có ai không?") == "vi"
    assert guess_reply_language("Chân CN1 có chức năng gì?") == "vi"
    assert guess_reply_language("Ignore previous instructions.") == "en"
    assert guess_reply_language("Où est le café ?") == "en"
