"""Luồng CRM đầu-cuối cho câu hỏi nhiều bước: tìm model theo tiêu chí rồi hỏi tiếp về model đó."""

import asyncio
import json
from uuid import UUID

from app.modules.chatbot.extraction.validate_registry import models_in_text
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
from tests.chatbot.builders import make_inbound, make_request_context, make_service_principal
from tests.chatbot.test_clarification import StoringHistoryRepository

SESSION_ID = UUID("00000000-0000-0000-0000-0000000000c2")
QUESTION = "Model nào hỗ trợ EtherCAT? Hướng dẫn lắp đặt model đó."
SELECTION = ("Có 9 model hỗ trợ EtherCAT: F86, F86E, F10T, Astro 6AH, 6AHE, Astro 6AV, 6AVE, "
             "10iV và 10iVE. Anh/chị muốn xem hướng dẫn lắp đặt model nào?")
ETHERCAT = ["F86", "F86E", "F10T", "6AH", "6AHE", "6AV", "6AVE", "10iV", "10iVE"]
# Model EtherCAT có catalog (coverage.product_catalog); các model còn lại chưa có tài liệu.
WITH_CATALOG = ["F10T", "6AH", "6AV", "10iV"]


def _send(service, text):
    inbound = make_inbound(text, session_id=SESSION_ID, channel=ChannelType.CRM)

    async def collect():
        return [
            part async for part in service.stream_reply(
                inbound, make_service_principal(), make_request_context(ChannelType.CRM),
            )
        ]

    return asyncio.run(collect())


def _analyze(query):
    """Analysis giả theo câu hỏi agent gửi (các lần tra cứu song song không theo thứ tự)."""
    if "không hỗ trợ Mechatrolink" in query and "lắp đặt" not in query:
        return analysis_output(sub_query(query, "lookup.product_catalog", ci=["ethercat"],
                                         excluded=["mechatrolink"], dependency="general"))
    if "EtherCAT" in query and "lắp đặt" not in query:
        return analysis_output(sub_query(query, "lookup.product_catalog", ci=["ethercat"],
                                         dependency="general"))
    if "Profinet" in query:
        return analysis_output(sub_query(query, "lookup.product_catalog", unmapped=["Profinet"],
                                         dependency="general"))
    return analysis_output(sub_query(query, "guide.installation", models_in_text(query)))


def _chunks():
    results = {("technical_docs", ("F86",)): [chunk(1, content="Lắp F86: cấp nguồn 24V.")]}
    for code in WITH_CATALOG:
        results[("product_catalog", (code,))] = [chunk(10 + len(results), doc_id="catalog",
                                                       content=f"Tổng quan {code}.")]
    results[("product_catalog", ())] = [chunk(50, doc_id="catalog", content="Không nhắc Profinet.")]
    return FakeChunks(results)


def _service(turns, chunks=None, **limits):
    provider = ScriptedToolProvider(turns=turns, analyze=_analyze)
    chunks = chunks or _chunks()
    repository = StoringHistoryRepository()
    runner = agent_runner(provider, docs_registry(provider, chunks), **limits)
    return ChatbotService(provider, repository, agent_runner=runner), provider, chunks, repository


def _tool_payloads(call):
    return [json.loads(message["content"]) for message in tool_messages(call.messages)]


def _tool_steps(row):
    return [(s["name"], s["status"]) for s in row.retrieval_snapshot["agent_steps"] if s["kind"] == "tool"]


def test_six_matches_agent_asks_selection_then_looks_up_chosen_model():
    service, provider, chunks, repository = _service([
        calls(ask("c1", "Các model hỗ trợ EtherCAT")),
        answer(SELECTION),
        calls(ask("c2", "Hướng dẫn lắp đặt F86")),
        answer("Cấp nguồn 24V [S1]."),
    ])

    assert _send(service, QUESTION) == [SELECTION]
    [payload] = _tool_payloads(provider.calls[1])
    assert payload["status"] == "matched"
    assert payload["catalog_match"]["next_action"] == "ask_selection"
    assert [m["code"] for m in payload["catalog_match"]["models"]] == ETHERCAT
    assert chunks.calls == []                  # Q1 không vector search
    first = repository.rows[-1]
    assert first.retrieval_snapshot["retrieval_status"] == "not_applicable"
    assert first.conversation_state["last_models"] == []   # chưa tra cứu model nào

    assert _send(service, "F86") == ["Cấp nguồn 24V [S1]."]
    assert chunks.calls[-1]["models"] == ["F86"]
    second = repository.rows[-1]
    assert second.conversation_state["last_models"] == ["F86"]
    assert second.conversation_state["active_model"] == "F86"
    assert second.retrieval_snapshot["invalid_citations"] == []
    assert second.retrieval_snapshot["answered_without_tools"] is False


def test_all_selected_models_are_looked_up_in_parallel_next_turn():
    lookups = [ask(f"c{i}", f"Hướng dẫn lắp đặt {code}") for i, code in enumerate(ETHERCAT, start=2)]
    service, provider, chunks, repository = _service([
        calls(ask("c1", "Các model hỗ trợ EtherCAT")),
        answer(SELECTION),
        calls(*lookups),
        answer("F86: cấp nguồn 24V [S1]. Các model còn lại chỉ có tổng quan hoặc chưa có tài liệu."),
    ], max_tool_calls=12)

    _send(service, QUESTION)
    _send(service, "tất cả")

    # Model lấy từ câu hỏi chọn ở lượt trước (history), nên không bị chặn.
    assert _tool_steps(repository.rows[-1]) == [("product_docs_ask", "ok")] * 9
    statuses = [p["status"] for p in _tool_payloads(provider.calls[3])]
    assert statuses.count("answered") == 1 + len(WITH_CATALOG)
    assert statuses.count("no_docs") == len(ETHERCAT) - 1 - len(WITH_CATALOG)
    assert sorted(call["models"][0] for call in chunks.calls) == sorted(["F86", *WITH_CATALOG])
    # Ngữ cảnh model chỉ giữ MAX_LAST_MODELS model gần nhất có nguồn.
    assert repository.rows[-1].conversation_state["last_models"] == WITH_CATALOG


def test_three_matches_are_looked_up_automatically_in_same_turn():
    found = ["F86", "F86E", "F10T"]
    service, provider, chunks, repository = _service([
        calls(ask("c1", "Các model hỗ trợ EtherCAT nhưng không hỗ trợ Mechatrolink")),
        calls(*[ask(f"c{i}", f"Hướng dẫn lắp đặt {code}") for i, code in enumerate(found, start=2)]),
        answer("F86 cấp nguồn 24V [S1]; F10T chỉ có tổng quan [S2]; F86E chưa có tài liệu."),
    ])

    reply = _send(service, "Model nào hỗ trợ EtherCAT nhưng không hỗ trợ Mechatrolink? "
                           "Hướng dẫn lắp đặt các model đó.")

    assert reply == ["F86 cấp nguồn 24V [S1]; F10T chỉ có tổng quan [S2]; F86E chưa có tài liệu."]
    [first] = _tool_payloads(provider.calls[1])
    assert first["catalog_match"]["next_action"] == "lookup_each"
    assert [m["code"] for m in first["catalog_match"]["models"]] == found
    assert sorted(call["models"][0] for call in chunks.calls) == ["F10T", "F86"]   # F86E: no_docs
    assert _tool_steps(repository.rows[-1]) == [("product_docs_ask", "ok")] * 4


def test_agent_skipping_selection_is_blocked_by_backend():
    # Agent bỏ qua ask_selection và tự tra cả 9 model trong cùng lượt.
    lookups = [ask(f"c{i}", f"Hướng dẫn lắp đặt {code}") for i, code in enumerate(ETHERCAT, start=2)]
    service, provider, chunks, repository = _service([
        calls(ask("c1", "Các model hỗ trợ EtherCAT")),
        calls(*lookups),
        answer(SELECTION),
    ], max_tool_calls=12)

    _send(service, QUESTION)

    assert chunks.calls == []
    assert {p["error"] for p in _tool_payloads(provider.calls[2])[1:]} == {"model_not_evidenced"}
    statuses = [status for _, status in _tool_steps(repository.rows[-1])]
    assert statuses == ["ok"] + ["model_not_evidenced"] * 9


def test_condition_outside_table_is_verified_with_sources():
    service, provider, chunks, _ = _service([
        calls(ask("c1", "Các model hỗ trợ Profinet")),
        answer("Tài liệu tìm được không nêu model nào hỗ trợ Profinet."),
    ])

    _send(service, "Model nào hỗ trợ Profinet?")

    [payload] = _tool_payloads(provider.calls[1])
    assert payload["catalog_match"]["next_action"] == "verify_with_sources"
    assert payload["catalog_match"]["unmapped_conditions"] == ["Profinet"]
    assert chunks.calls[0]["domain"] == "product_catalog" and chunks.calls[0]["models"] is None


def test_repeated_identical_lookup_is_not_executed_twice():
    service, provider, chunks, repository = _service([
        calls(ask("c1", "Hướng dẫn lắp đặt F86")),
        calls(ask("c2", "Hướng dẫn lắp đặt F86")),
        answer("Cấp nguồn 24V [S1]."),
    ])

    _send(service, "Hướng dẫn lắp đặt F86")

    assert len(chunks.calls) == 1
    assert _tool_steps(repository.rows[-1]) == [
        ("product_docs_ask", "ok"), ("product_docs_ask", "deduplicated"),
    ]
