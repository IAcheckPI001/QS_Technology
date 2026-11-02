"""Client ngắt giữa lượt agent: huỷ phải đi xuyên AgentRunner → tool → pipeline → dependency.

Không dùng timeout để giả lập: task được cancel thật như khi Starlette huỷ request.
"""

import asyncio

import pytest

from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.services import ChatbotService
from tests.chatbot.agent_fakes import (
    FakeChunks,
    ScriptedToolProvider,
    ToolProbe,
    agent_runner,
    analysis_output,
    answer,
    ask,
    calls,
    docs_registry,
    echo_tool,
    sub_query,
)
from app.modules.chatbot.tools import ToolRegistry
from tests.chatbot.builders import make_inbound, make_request_context, make_service_principal
from tests.chatbot.test_cancelled_turn import AuditingHistoryRepository


class BlockingAnalysis:
    """Output analysis chờ mãi, ghi lại việc bị huỷ (như LLM đang trả lời chậm)."""

    def __init__(self):
        self.started = asyncio.Event()
        self.cancelled = False

    async def __call__(self):
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


async def _cancel_while(service, ready: asyncio.Event):
    inbound = make_inbound("Hướng dẫn lắp đặt F86", channel=ChannelType.CRM)

    async def consume():
        async for _ in service.stream_reply(
            inbound, make_service_principal(), make_request_context(ChannelType.CRM),
        ):
            pass

    task = asyncio.create_task(consume())
    await ready.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)
    return [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]


def _assert_recorded_cancelled(repository):
    assert repository.created == []          # không có lượt completed/error
    [row] = repository.audited
    assert row["status"] == "cancelled"
    assert row["retrieval_snapshot"]["agent_steps"][0]["kind"] == "llm"


def test_cancel_while_analysis_llm_is_waiting_cancels_the_tool_chain():
    blocking = BlockingAnalysis()
    provider = ScriptedToolProvider(
        turns=[calls(ask("c1", "Hướng dẫn lắp đặt F86")), answer("không tới")],
        analysis_outputs=[blocking],
    )
    repository = AuditingHistoryRepository()
    runner = agent_runner(provider, docs_registry(provider, FakeChunks()))
    service = ChatbotService(provider, repository, agent_runner=runner)

    leftover = asyncio.run(_cancel_while(service, blocking.started))

    assert blocking.cancelled
    assert leftover == []
    _assert_recorded_cancelled(repository)


def test_cancel_while_repository_query_is_running_reaches_the_repository():
    chunks = FakeChunks(gate=asyncio.Event())
    provider = ScriptedToolProvider(
        turns=[calls(ask("c1", "Hướng dẫn lắp đặt F86")), answer("không tới")],
        analysis_outputs=[analysis_output(
            sub_query("Hướng dẫn lắp đặt F86", "guide.installation", ["F86"]),
        )],
    )
    repository = AuditingHistoryRepository()
    runner = agent_runner(provider, docs_registry(provider, chunks))
    service = ChatbotService(provider, repository, agent_runner=runner)

    leftover = asyncio.run(_cancel_while(service, chunks.started))

    assert chunks.cancelled
    assert leftover == []
    _assert_recorded_cancelled(repository)


def test_cancel_cancels_every_parallel_tool_and_leaves_no_task():
    probe = ToolProbe()
    block = asyncio.Event()
    provider = ScriptedToolProvider(turns=[
        calls(("c1", "echo", {"text": "a"}), ("c2", "echo", {"text": "b"})),
        answer("không tới"),
    ])
    repository = AuditingHistoryRepository()
    runner = agent_runner(provider, ToolRegistry([echo_tool(probe=probe, block=block)]))
    service = ChatbotService(provider, repository, agent_runner=runner)

    async def scenario():
        ready = asyncio.Event()

        async def both_running():
            while probe.running < 2:
                await asyncio.sleep(0.001)
            ready.set()

        watcher = asyncio.create_task(both_running())
        leftover = await _cancel_while(service, ready)
        await watcher
        return leftover

    leftover = asyncio.run(scenario())

    assert sorted(probe.cancelled) == ["a", "b"]
    assert probe.running == 0
    assert leftover == []
    _assert_recorded_cancelled(repository)
