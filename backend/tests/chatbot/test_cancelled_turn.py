import asyncio

import pytest
from starlette.requests import Request

from app.modules.chatbot.routers.sse import stream_chat
from app.modules.chatbot.services import ChatbotService
from tests.chatbot.builders import make_inbound, make_principal, make_request_context
from tests.chatbot.test_chat_history import FakeHistoryRepository, FakeProvider


class AuditingHistoryRepository(FakeHistoryRepository):
    def __init__(self):
        super().__init__()
        self.audited = []

    async def create_audit(self, **data):
        self.audited.append(data)
        return data


class WaitingProvider(FakeProvider):
    """Stream một chunk rồi chờ mãi, để test huỷ task giữa lúc chờ provider."""

    def __init__(self):
        super().__init__()
        self.waiting = asyncio.Event()

    async def stream_chat(self, messages):
        yield "Một phần"
        self.waiting.set()
        await asyncio.Event().wait()
        yield "không tới"


def _stream(service):
    inbound = make_inbound("Địa chỉ công ty?")
    return service.stream_reply(inbound, make_principal(), make_request_context())


def test_closing_stream_mid_answer_records_cancelled_turn():
    repository = AuditingHistoryRepository()
    service = ChatbotService(FakeProvider(["Xin ", "chào", " bạn"]), repository)

    async def run():
        replies = _stream(service)
        first = await anext(replies)
        await replies.aclose()  # Starlette đóng generator khi client ngắt (GeneratorExit)
        return first

    first = asyncio.run(run())

    assert repository.created == []
    [row] = repository.audited
    assert row["status"] == "cancelled"
    assert row["answer"] == first == "Xin "
    assert row["retrieval_snapshot"]["retrieval_status"] is not None
    assert "conversation_state" not in row


def test_cancelling_task_while_waiting_for_provider_records_and_reraises():
    repository = AuditingHistoryRepository()
    provider = WaitingProvider()
    service = ChatbotService(provider, repository)

    async def run():
        async def consume():
            async for _ in _stream(service):
                pass

        task = asyncio.create_task(consume())
        await provider.waiting.wait()
        task.cancel()  # task group của Starlette bị cancel (CancelledError)
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())

    [row] = repository.audited
    assert row["status"] == "cancelled"
    assert row["answer"] == "Một phần"


def test_completed_turn_is_not_recorded_as_cancelled():
    repository = AuditingHistoryRepository()
    service = ChatbotService(FakeProvider(["ok"]), repository)

    async def run():
        replies = _stream(service)
        chunks = [chunk async for chunk in replies]
        await replies.aclose()
        return chunks

    assert asyncio.run(run()) == ["ok"]
    assert repository.audited == []
    assert repository.created[0]["status"] == "completed"


def test_closing_sse_stream_closes_service_stream_immediately():
    repository = AuditingHistoryRepository()
    service = ChatbotService(FakeProvider(["Xin ", "chào"]), repository)
    request = Request({"type": "http", "method": "POST", "path": "/chat/website",
                       "headers": [], "state": {}})

    async def run():
        response = stream_chat(request, service, make_inbound("Địa chỉ công ty?"),
                               make_principal(), make_request_context())
        events = response.body_iterator
        first = await anext(events)
        await events.aclose()
        return first

    assert asyncio.run(run()).startswith("event: delta")
    assert [row["status"] for row in repository.audited] == ["cancelled"]
