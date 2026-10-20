import asyncio
import json
import re
from uuid import UUID

from app.modules.chatbot.extraction.validate_registry import plan_turn, resolve
from app.modules.chatbot.schemas.inbound import (
    ChannelType,
    InboundRequest,
    MessageUser,
    SessionInfo,
)
from app.modules.chatbot.schemas.system import (
    Analysis,
    Conversation,
    ConversationMessage,
    QueryInfo,
    RetrievalScope,
    RunContext,
    RunState,
)
from app.modules.chatbot.service import ChatbotService
from app.modules.chatbot.stages.answer_composer import AnswerComposer
from app.modules.chatbot.stages.execution_stage import ExecutionStage


class FakeProvider:
    model = "test-model"

    def __init__(self, chunks=None):
        self.chunks = chunks or []
        self.messages = None

    async def stream_chat(self, messages):
        self.messages = messages
        for chunk in self.chunks:
            yield chunk


def _sub_query(query, intent, models=(), handoff_reason=None, unresolved=()):
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


def _analysis(*sub_queries) -> Analysis:
    return Analysis.from_plan(plan_turn(resolve({"sub_queries": list(sub_queries)})))


def _state(query, analysis, history=()) -> RunState:
    state = RunState(input=InboundRequest(
        message=MessageUser(message_id="request-1", text=query),
        session=SessionInfo(session_id="00000000-0000-0000-0000-000000000001"),
        channel={"type": ChannelType.WEBSITE, "branch": "support-technical"},
    ))
    state.context = RunContext(
        conversation=Conversation(history=list(history)),
        query=QueryInfo(origin=query),
        retrieval_scope=RetrievalScope(collections=["crm-technical"]),
    )
    state.analysis = analysis
    asyncio.run(ExecutionStage().execute(state))
    return state


def _task_results(content: str) -> list[dict]:
    match = re.search(r"<task_results>(.*)</task_results>", content)
    assert match is not None
    return json.loads(match.group(1))


def test_build_messages_includes_history_query_and_task_results():
    history = [
        ConversationMessage(role="user", content="Chào bạn", message_id="u1"),
        ConversationMessage(role="assistant", content="Chào anh/chị", message_id="a1"),
    ]
    state = _state("Xin chào", _analysis(_sub_query("Xin chào", "other.chitchat")), history)

    messages = AnswerComposer(FakeProvider()).build_messages(state)

    assert messages[0]["role"] == "system"
    assert messages[1:3] == [
        {"role": "user", "content": "Chào bạn"},
        {"role": "assistant", "content": "Chào anh/chị"},
    ]
    user = messages[-1]["content"]
    assert "<query>Xin chào</query>" in user
    assert "<clarification>" not in user
    assert _task_results(user) == [{
        "task_id": "task-q1",
        "kind": "chitchat",
        "status": "completed",
        "queries": ["Xin chào"],
        "metadata": {"kind": "chitchat"},
    }]


def test_build_messages_includes_clarification_and_failed_retrieval():
    analysis = _analysis(
        _sub_query("Hướng dẫn đấu nguồn Astro 6A", "guide.installation", unresolved=["Astro 6A"]),
        _sub_query("Hướng dẫn đấu nguồn F54", "lookup.product_info", ["F54"]),
    )
    state = _state("Đấu nguồn Astro 6A và F54", analysis)

    user = AnswerComposer(FakeProvider()).build_messages(state)[-1]["content"]

    assert "<clarification>" in user
    assert "Astro 6A" in user
    results = {item["kind"]: item for item in _task_results(user)}
    assert results["clarify"]["status"] == "blocked"
    assert results["retrieve"]["error"] == "handler_not_configured"


def test_stream_yields_provider_chunks():
    provider = FakeProvider(["Xin chào", "!"])
    state = _state("Xin chào", _analysis(_sub_query("Xin chào", "other.chitchat")))

    async def collect():
        return [chunk async for chunk in AnswerComposer(provider).stream(state)]

    assert asyncio.run(collect()) == ["Xin chào", "!"]
    assert provider.messages[0]["role"] == "system"


class FakeHistoryRepository:
    def __init__(self):
        self.created = []

    async def session_exists(self, session_id):
        return False

    async def list_for_context(self, session_id):
        return []

    async def create(self, **data):
        self.created.append(data)
        return data


class FakeAnalysisStage:
    async def execute(self, state):
        state.analysis = _analysis(_sub_query("Xin chào", "other.chitchat"))
        return state


def test_service_streams_composed_answer_and_saves_history():
    provider = FakeProvider(["Xin chào, ", "tôi có thể giúp gì?"])
    repository = FakeHistoryRepository()
    service = ChatbotService(provider, repository, analysis_stage=FakeAnalysisStage())
    session_id = UUID("00000000-0000-0000-0000-000000000001")

    async def collect():
        return [chunk async for chunk in service.stream_reply("Xin chào", session_id)]

    assert asyncio.run(collect()) == ["Xin chào, ", "tôi có thể giúp gì?"]
    assert repository.created[0]["status"] == "completed"
    assert repository.created[0]["answer"] == "Xin chào, tôi có thể giúp gì?"
