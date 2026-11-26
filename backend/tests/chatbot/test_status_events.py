"""WU-17 đợt 3A: event SSE `status` (dòng hoạt động AI) từ mốc span của tracing."""

import asyncio
import json
from uuid import UUID

from starlette.requests import Request

from app.core.tracing import Trace, activate, listen, span
from app.modules.chatbot.routers.sse import stream_chat
from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.services.status_events import StatusEmitter
from tests.chatbot.builders import make_inbound, make_request_context, make_service_principal
from tests.chatbot.test_sources import FakeSigner, _agent_service

SESSION_ID = UUID("00000000-0000-0000-0000-0000000000d2")


def _collect(run) -> list[dict]:
    events: list[dict] = []
    with listen(StatusEmitter(events.append)):
        run()
    return events


def test_pipeline_spans_become_status_events_without_content() -> None:
    def run() -> None:
        with activate(Trace("r1")):
            with span("stage.security", "stage") as security:
                security.set(action="allow")
            with span("stage.context_load", "stage") as load:
                load.set(history_messages=4)
            with span("stage.prune", "stage"):
                pass
            with span("stage.analysis", "stage") as analysis:
                analysis.set(intents=["guide.configuration"], product_models=["F54"], sub_queries=1)
            with span("task.retrieve", "internal", task_id="t1", target="F54") as retrieve:
                retrieve.set(hits=4, best_similarity=0.7529, doc_ids=["f54-installation-en"])
            with span("task.retrieve", "internal", task_id="t2", target="F10T", no_docs=True, hits=0):
                pass
            with span("stage.compose", "stage"):
                pass

    events = _collect(run)
    assert [(e["id"], e["state"]) for e in events] == [
        ("security", "running"), ("security", "done"),
        ("context", "running"), ("context", "done"),
        ("analysis", "running"), ("analysis", "done"),
        ("retrieval:t1", "running"), ("retrieval:t1", "done"),
        ("retrieval:t2", "running"), ("retrieval:t2", "warn"),
        ("compose", "running"), ("compose", "done"),
    ]
    assert events[3]["turns"] == 4
    assert events[5] == {"id": "analysis", "step": "analysis", "state": "done",
                         "intent": "guide.configuration", "models": ["F54"]}
    assert events[7] == {"id": "retrieval:t1", "step": "retrieval", "state": "done", "target": "F54",
                         "count": 4, "score": 0.7529, "docs": ["f54-installation-en"]}
    assert events[9]["count"] == 0


def test_blocked_direct_and_failed_steps() -> None:
    def run() -> None:
        with span("stage.security", "stage") as security:
            security.set(action="block")
        with span("stage.direct", "stage", code="handoff.pricing"):
            pass
        with span("stage.direct", "stage", code="chitchat"):
            pass
        try:
            with span("task.retrieve", "internal", task_id="t9"):
                raise RuntimeError("db down")
        except RuntimeError:
            pass

    events = _collect(run)
    assert events[1] == {"id": "security", "step": "security", "state": "error", "code": "request_blocked"}
    assert [(e["step"], e["state"]) for e in events[2:4]] == [("handoff", "done"), ("direct", "done")]
    assert events[-1]["state"] == "error" and events[-1]["code"] == "retrieval_error"


def test_agent_tools_retry_and_nested_pipeline_is_folded_into_the_tool_line() -> None:
    def run() -> None:
        with span("agent.run", "internal"):
            with span("llm.chat_tools", "llm", tool_choice="auto"):
                pass
            with span("tool.crm_query", "tool", tool_call_id="c1") as failed:
                failed.fail("tool_invalid_args")
                failed.set(repairable=True)
            with span("tool.crm_query", "tool", tool_call_id="c2") as ok:
                ok.set(returned=3)
            with span("tool.product_docs_ask", "tool", tool_call_id="c3") as docs:
                with span("stage.analysis", "stage"):     # pipeline lồng: không hiện riêng
                    pass
                with span("task.retrieve", "internal", task_id="t1"):
                    pass
                docs.set(sources=2)
            with span("tool.crm_query", "tool", tool_call_id="c4") as denied:
                denied.fail("crm_forbidden")
                denied.set(repairable=False)
            with span("llm.chat_tools", "llm", tool_choice="none"):
                pass

    events = _collect(run)
    pairs = [(e["id"], e["state"]) for e in events]
    assert pairs == [
        ("analysis", "running"), ("analysis", "done"),
        ("tool:c1", "running"), ("tool:c1", "retry"),
        ("tool:c2", "running"), ("tool:c2", "done"),
        ("tool:c3", "running"), ("tool:c3", "done"),
        ("tool:c4", "running"), ("tool:c4", "error"),
        ("compose", "running"), ("compose", "done"),
    ]
    assert events[3]["code"] == "tool_invalid_args"
    assert events[5]["rows"] == 3 and events[7]["count"] == 2
    assert events[9]["code"] == "crm_forbidden"


def _sse(service, *, status_enabled: bool) -> list[tuple[str, dict]]:
    request = Request({"type": "http", "method": "POST", "path": "/chat/crm", "headers": [], "state": {}})
    inbound = make_inbound("Hướng dẫn lắp đặt F86", session_id=SESSION_ID, channel=ChannelType.CRM)

    async def collect():
        response = stream_chat(request, service, inbound, make_service_principal(),
                               make_request_context(ChannelType.CRM), status_enabled=status_enabled)
        return [event async for event in response.body_iterator]

    out = []
    for raw in asyncio.run(collect()):
        name = raw.split("\n", 1)[0].removeprefix("event: ")
        out.append((name, json.loads(raw.split("data: ", 1)[1])))
    return out


def test_sse_interleaves_status_before_answer_and_keeps_old_behaviour_when_off() -> None:
    events = _sse(_agent_service(FakeSigner(), "Lắp theo các bước [S1]."), status_enabled=True)
    names = [name for name, _ in events]
    assert names[-3:] == ["delta", "sources", "done"]
    statuses = [payload for name, payload in events if name == "status"]
    assert names.index("delta") > names.index("status")
    assert ("security", "done") in [(s["id"], s["state"]) for s in statuses]
    assert any(s["step"] == "tool" and s.get("tool") == "product_docs_ask" and s["state"] == "done" for s in statuses)
    assert statuses[-1] == {"id": "compose", "step": "compose", "state": "done"}
    # Không có chữ của câu hỏi hay câu trả lời trong event status.
    assert "F86" not in json.dumps([s for s in statuses if s["step"] != "analysis"])
    assert "Lắp" not in json.dumps(statuses)

    off = [name for name, _ in _sse(_agent_service(FakeSigner(), "Lắp theo các bước [S1]."), status_enabled=False)]
    assert off == ["delta", "sources", "done"]
