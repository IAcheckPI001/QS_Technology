from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.schemas.inbound import InboundRequest
from app.modules.chatbot.stages.context_loader import (
    ContextBudgetError,
    ContextConfigurationError,
    ContextLoader
)
from app.modules.chatbot.stages.prune_stage import Prune
from tests.chatbot.builders import make_inbound, make_run_state


def request(session_id: str) -> InboundRequest:
    return make_inbound(session_id=session_id, message_id="current")


@pytest.mark.anyio
async def test_context_loader_emits_stable_turn_messages_and_filters_repository_path():
    history_id = uuid4()

    class Repository:
        async def list_for_context(self, *, session_id):
            assert session_id
            return [SimpleNamespace(
                id=history_id,
                query_origin="Câu hỏi cũ",
                answer="Câu trả lời cũ",
            )]

    state = make_run_state(session_id=str(uuid4()), message_id="current")
    context = await ContextLoader(Repository()).execute(state)

    assert [message.role for message in context.conversation.history] == [
        "user", "assistant"
    ]
    assert [message.message_id for message in context.conversation.history] == [
        f"{history_id}:user", f"{history_id}:assistant"
    ]
    assert context.conversation.summary is None
    assert context.retrieval_scope.collections == ["crm-technical", "crm-sale"]


def test_prune_removes_oldest_turn_and_preserves_current_query():
    from app.modules.chatbot.schemas.system import (
        Conversation,
        ConversationMessage,
        QueryInfo,
        RetrievalScope,
        RunContext,
    )
    context = RunContext(
        conversation=Conversation(history=[
            ConversationMessage(role="user", content="old", message_id="1:user"),
            ConversationMessage(role="assistant", content="old answer", message_id="1:assistant"),
            ConversationMessage(role="user", content="new", message_id="2:user"),
            ConversationMessage(role="assistant", content="new answer", message_id="2:assistant"),
        ]),
        query=QueryInfo(origin="current"),
        retrieval_scope=RetrievalScope(collections=["crm-technical"]),
    )
    pruned = Prune(
        1,
        token_counter=lambda value, model: 2 if len(value.conversation.history) > 2 else 1,
    ).execute(context, "gpt-4o-mini")
    assert [message.content for message in pruned.conversation.history] == [
        "new", "new answer"
    ]
    assert pruned.query.origin == "current"


def test_prune_reports_invalid_budget_and_mandatory_overflow():
    with pytest.raises(ContextConfigurationError):
        Prune(0)

    from app.modules.chatbot.schemas.system import Conversation, QueryInfo, RetrievalScope, RunContext
    context = RunContext(
        conversation=Conversation(),
        query=QueryInfo(origin="current"),
        retrieval_scope=RetrievalScope(collections=["crm-technical"]),
    )
    with pytest.raises(ContextBudgetError):
        Prune(1, token_counter=lambda _context, _model: 2).execute(context, "gpt-4o-mini")


def test_website_searches_every_collection():
    assert ContextLoader.resolve_retrieval_scope(request(str(uuid4()))).collections == [
        "crm-technical", "crm-sale"
    ]


def test_crm_without_branch_searches_every_collection():
    crm = make_inbound(channel=ChannelType.CRM)
    assert ContextLoader.resolve_retrieval_scope(crm).collections == [
        "crm-technical", "crm-sale"
    ]


def test_crm_branch_maps_to_single_collection():
    crm = make_inbound(channel=ChannelType.CRM, branch="support-sale")
    assert ContextLoader.resolve_retrieval_scope(crm).collections == ["crm-sale"]
