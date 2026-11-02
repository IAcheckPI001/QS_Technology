import asyncio
from uuid import UUID

import pytest
from starlette.requests import Request

from app.modules.chatbot.agent import AgentError
from app.modules.chatbot.routers.sse import stream_chat
from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.services import ChatbotService
from tests.chatbot.agent_fakes import (
    FakeChunks,
    ScriptedToolProvider,
    agent_runner,
    analysis_output,
    answer,
    ask,
    calls,
    chunk,
    docs_registry,
    sub_query,
    tool_messages,
)
from tests.chatbot.builders import (
    make_inbound,
    make_principal,
    make_request_context,
    make_service_principal,
)
from tests.chatbot.test_clarification import StoringHistoryRepository

SESSION_ID = UUID("00000000-0000-0000-0000-0000000000c1")


def _send(service, text, channel=ChannelType.CRM):
    inbound = make_inbound(text, session_id=SESSION_ID, channel=channel)
    principal = make_service_principal() if channel is ChannelType.CRM else make_principal()

    async def collect():
        return [
            chunk async for chunk in service.stream_reply(
                inbound, principal, make_request_context(channel),
            )
        ]

    return asyncio.run(collect())


def _service(provider, chunks, repository, **limits):
    runner = agent_runner(provider, docs_registry(provider, chunks), **limits)
    return ChatbotService(provider, repository, agent_runner=runner)


def test_crm_turn_runs_agent_and_records_snapshot_without_changing_state():
    provider = ScriptedToolProvider(
        turns=[calls(ask("c1", "Hướng dẫn lắp đặt F86")), answer("Lắp theo các bước [S1].")],
        analysis_outputs=[analysis_output(
            sub_query("Hướng dẫn lắp đặt F86", "guide.installation", ["F86"]),
        )],
    )
    chunks = FakeChunks({("technical_docs", ("F86",)): [chunk(1, vector=0.7), chunk(2)]})
    repository = StoringHistoryRepository()

    reply = _send(_service(provider, chunks, repository), "Hướng dẫn lắp đặt F86")

    assert reply == ["Lắp theo các bước [S1]."]
    row = repository.rows[-1]
    assert row.status == "completed"
    assert row.normalized_query == "Hướng dẫn lắp đặt F86"
    snapshot = row.retrieval_snapshot
    assert snapshot["retrieval_status"] == "ok"
    assert [task["task_id"] for task in snapshot["retrieval_tasks"]] == ["c1:task-retrieve-q1"]
    assert [c["rank"] for c in snapshot["chunks"]] == [1, 2]
    assert snapshot["product_models"] == ["F86"]
    assert [(s["kind"], s["name"], s["status"]) for s in snapshot["agent_steps"]] == [
        ("llm", "auto", "ok"), ("tool", "product_docs_ask", "ok"), ("llm", "auto", "ok"),
    ]
    assert row.conversation_state["mode"] == "bot"
    assert row.conversation_state["pending"] is None
    # Ngữ cảnh model được cập nhật từ lần tra cứu có nguồn (lượt sau "model đó" = F86).
    assert row.conversation_state["last_models"] == ["F86"]
    assert row.conversation_state["active_model"] == "F86"
    # Tool output (có S#) được gửi lại cho LLM ở bước sau.
    [tool_message] = tool_messages(provider.calls[1].messages)
    assert '"source_id": "S1"' in tool_message["content"]


def test_website_turn_keeps_pipeline_even_with_agent_runner():
    provider = ScriptedToolProvider(analysis_outputs=[analysis_output(
        sub_query("Địa chỉ công ty", "lookup.company_info", dependency="general"),
    )])
    repository = StoringHistoryRepository()

    reply = _send(_service(provider, FakeChunks(), repository), "Địa chỉ công ty?",
                  channel=ChannelType.WEBSITE)

    assert reply == ["pipeline answer"]
    assert provider.calls == []
    assert "agent_steps" not in repository.rows[-1].retrieval_snapshot


def test_crm_without_agent_runner_uses_pipeline_for_rollback():
    provider = ScriptedToolProvider(analysis_outputs=[analysis_output(
        sub_query("Địa chỉ công ty", "lookup.company_info", dependency="general"),
    )])
    repository = StoringHistoryRepository()

    reply = _send(ChatbotService(provider, repository), "Địa chỉ công ty?")

    assert reply == ["pipeline answer"]
    assert provider.calls == []


def test_two_turn_clarification_goes_through_history_not_pending():
    provider = ScriptedToolProvider(
        turns=[
            calls(ask("c1", "Hướng dẫn lắp đặt Astro 6A")),
            answer("Bạn đang dùng Astro 6AH hay Astro 6AV?"),
            calls(ask("c2", "Hướng dẫn lắp đặt ASTRO_6AV")),
            answer("Tổng quan lắp đặt Astro 6AV [S1]."),
        ],
        analysis_outputs=[
            analysis_output(sub_query("Hướng dẫn lắp đặt Astro 6A", "guide.installation",
                                      unresolved=["Astro 6A"])),
            analysis_output(sub_query("Hướng dẫn lắp đặt ASTRO_6AV", "guide.installation",
                                      ["ASTRO_6AV"])),
        ],
    )
    chunks = FakeChunks({("product_catalog", ("ASTRO_6AV",)): [chunk(7, doc_id="astro")]})
    repository = StoringHistoryRepository()
    service = _service(provider, chunks, repository)

    assert _send(service, "Hướng dẫn lắp đặt Astro 6A") == ["Bạn đang dùng Astro 6AH hay Astro 6AV?"]
    first_tool = tool_messages(provider.calls[1].messages)[0]["content"]
    assert '"status": "needs_clarification"' in first_tool and "ASTRO_6AV" in first_tool
    assert repository.rows[-1].conversation_state["pending"] is None

    assert _send(service, "6AV") == ["Tổng quan lắp đặt Astro 6AV [S1]."]
    second_history = [m["content"] for m in provider.calls[2].messages[1:]]
    assert second_history == [
        "Hướng dẫn lắp đặt Astro 6A", "Bạn đang dùng Astro 6AH hay Astro 6AV?", "6AV",
    ]
    assert chunks.calls[-1]["models"] == ["ASTRO_6AV"]


def test_agent_error_is_recorded_and_mapped_to_sse_agent_error():
    provider = ScriptedToolProvider(turns=[answer(""), answer("")])
    repository = StoringHistoryRepository()
    service = _service(provider, FakeChunks(), repository)
    request = Request({"type": "http", "method": "POST", "path": "/chat/crm",
                       "headers": [], "state": {}})
    inbound = make_inbound("Câu hỏi", session_id=SESSION_ID, channel=ChannelType.CRM)

    async def collect():
        response = stream_chat(request, service, inbound, make_service_principal(),
                               make_request_context(ChannelType.CRM))
        return [event async for event in response.body_iterator]

    events = asyncio.run(collect())

    assert events[0].startswith("event: error") and '"code": "agent_error"' in events[0]
    assert repository.rows[-1].status == "error"
    assert request.state.outcome == "agent_error"


def test_agent_error_propagates_from_service():
    provider = ScriptedToolProvider(turns=[answer(""), answer("")])

    with pytest.raises(AgentError):
        _send(_service(provider, FakeChunks(), StoringHistoryRepository()), "Câu hỏi")
