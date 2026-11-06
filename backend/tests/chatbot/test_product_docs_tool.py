import asyncio
import json

from app.modules.chatbot.schemas.system import (
    AgentRun,
    ConversationMessage,
    ConversationState,
    PendingClarification,
)
from app.modules.chatbot.stages.execution_stage import SourceAllocator
from app.modules.chatbot.tools import ToolContext
from app.modules.chatbot.tools.product_docs import product_docs_plans
from tests.chatbot.agent_fakes import (
    FakeChunks,
    ScriptedToolProvider,
    analysis_output,
    chunk,
    crm_state,
    docs_registry,
    sub_query,
)


def _ask(registry, state, question, call_id="c1", allocator=None):
    from app.modules.chatbot.schemas.system import ToolCallRequest

    state.agent = state.agent or AgentRun()
    context = ToolContext(
        parent_state=state,
        sources=allocator or SourceAllocator.for_state(state),
        tool_call_id=call_id,
    )
    call = ToolCallRequest(id=call_id, name="product_docs_ask",
                           arguments_raw=json.dumps({"question": question}))
    return asyncio.run(registry.invoke(call, context, allowed=registry.names, timeout_s=10))


def _catalog_chunks():
    return FakeChunks({
        ("technical_docs", ("F86",)): [chunk(1), chunk(2)],
        ("product_catalog", ("6AV",)): [chunk(7, doc_id="astro_catalog")],
    })


def test_answered_output_has_numbered_sources_and_records_plan_and_traces():
    provider = ScriptedToolProvider(analysis_outputs=[analysis_output(
        sub_query("Hướng dẫn lắp đặt F86", "guide.installation", ["F86"]),
    )])
    chunks = _catalog_chunks()
    state = crm_state("Hướng dẫn lắp đặt F86")

    outcome = _ask(docs_registry(provider, chunks), state, "Hướng dẫn lắp đặt F86")

    assert outcome.ok and outcome.output.status == "answered"
    [group] = outcome.output.sources
    assert [source.source_id for source in group.sources] == ["S1", "S2"]
    assert chunks.calls[0]["models"] == ["F86"]
    [tool_plan] = product_docs_plans(state.agent)
    assert tool_plan.tool_call_id == "c1" and tool_plan.question == "Hướng dẫn lắp đặt F86"
    assert state.retrieval_traces  # trace của lần tra cứu được chuyển về lượt cha


def test_source_ids_continue_and_dedupe_across_calls_in_one_turn():
    provider = ScriptedToolProvider(analysis_outputs=[
        analysis_output(sub_query("Hướng dẫn lắp đặt F86", "guide.installation", ["F86"])),
        analysis_output(sub_query("Đấu nguồn F86", "guide.installation", ["F86"])),
    ])
    chunks = FakeChunks({("technical_docs", ("F86",)): [chunk(1), chunk(2)]})
    registry = docs_registry(provider, chunks)
    state = crm_state("F86: lắp đặt và đấu nguồn")
    allocator = SourceAllocator.for_state(state)

    first = _ask(registry, state, "Hướng dẫn lắp đặt F86", "c1", allocator)
    chunks.results[("technical_docs", ("F86",))] = [chunk(2), chunk(3)]
    second = _ask(registry, state, "Đấu nguồn F86", "c2", allocator)

    assert [s.source_id for s in first.output.sources[0].sources] == ["S1", "S2"]
    assert [s.source_id for s in second.output.sources[0].sources] == ["S2", "S3"]


def test_ambiguous_model_needs_clarification_with_codes_and_names():
    provider = ScriptedToolProvider(analysis_outputs=[analysis_output(
        sub_query("Hướng dẫn lắp đặt Astro 6A", "guide.installation", unresolved=["Astro 6A"]),
    )])
    state = crm_state("Hướng dẫn lắp đặt Astro 6A")

    output = _ask(docs_registry(provider, _catalog_chunks()), state,
                  "Hướng dẫn lắp đặt Astro 6A").output

    assert output.status == "needs_clarification"
    assert output.sources == []
    assert output.clarification.reason == "ambiguous_product_model"
    assert [(c.code, c.name) for c in output.clarification.candidates] == [
        ("6AH", "Astro 6AH"), ("6AHE", "6AHE"), ("6AV", "Astro 6AV"), ("6AVE", "6AVE"),
    ]


def test_clarification_answer_is_resolved_from_history_without_pending():
    # Lượt 2: nhân viên trả "cái V"; câu hỏi lại ở lượt 1 nằm trong history.
    history = [
        ConversationMessage(role="user", content="Hướng dẫn lắp đặt Astro 6A",
                            message_id="h1:user"),
        ConversationMessage(role="assistant", content="Bạn dùng Astro 6AH hay Astro 6AV?",
                            message_id="h1:assistant"),
    ]
    provider = ScriptedToolProvider(analysis_outputs=[analysis_output(
        sub_query("Hướng dẫn lắp đặt 6AV", "guide.installation", ["6AV"]),
    )])
    chunks = _catalog_chunks()
    state = crm_state("cái V", history=history)
    # Pending cũ của luồng chat không được dùng trong luồng agent.
    state.context.conversation.state = ConversationState(
        pending=PendingClarification(
            focus="Astro 6A", question_type="choose", candidates=["6AH", "6AV"],
            llm_raw={"sub_queries": []}, ttl=2,
        ),
        last_models=["F54"],
        active_model="F54",
    )

    output = _ask(docs_registry(provider, chunks), state, "Hướng dẫn lắp đặt 6AV").output

    assert output.status == "answered"
    assert chunks.calls[0]["models"] == ["6AV"]
    assert output.sources[0].answer_mode == "overview"   # chưa có tài liệu lắp đặt: degrade
    assert output.sources[0].product_models == ["6AV"]
    analysis_prompt = provider.analysis_messages[0][1]["content"]
    assert "<pending>" not in analysis_prompt
    assert "cái V" in analysis_prompt and "Astro 6AH hay Astro 6AV" in analysis_prompt
    # Ngữ cảnh model của phiên vẫn được gửi (kế thừa/xung đột bằng code), pending thì không.
    assert '"last_models":["F54"]' in analysis_prompt


def test_model_invented_by_agent_is_rejected_before_analysis():
    # Nhân viên không nêu model; agent tự viết F86 vào câu hỏi.
    provider = ScriptedToolProvider()
    chunks = _catalog_chunks()
    state = crm_state("Hướng dẫn lắp đặt")

    outcome = _ask(docs_registry(provider, chunks), state, "Hướng dẫn lắp đặt F86")

    assert outcome.error_code == "model_not_evidenced"
    assert "F86" in outcome.error_detail
    assert provider.analysis_messages == [] and chunks.calls == []


def test_model_added_by_analysis_llm_is_still_dropped_by_guard():
    # Câu hỏi của agent không có model, nhưng LLM analysis tự điền F86.
    provider = ScriptedToolProvider(analysis_outputs=[analysis_output(
        sub_query("Hướng dẫn lắp đặt F86", "guide.installation", ["F86"]),
    )])
    chunks = _catalog_chunks()

    output = _ask(docs_registry(provider, chunks), crm_state("Hướng dẫn lắp đặt"),
                  "Hướng dẫn lắp đặt").output

    assert output.status == "needs_clarification"
    assert output.clarification.reason == "missing_product_model"
    assert chunks.calls == []


def test_handoff_is_a_business_result_only():
    provider = ScriptedToolProvider(analysis_outputs=[analysis_output(
        sub_query("Giá F86", "handoff.human", ["F86"], handoff_reason="pricing"),
    )])
    state = crm_state("Giá F86 bao nhiêu?")

    output = _ask(docs_registry(provider, _catalog_chunks()), state, "Giá F86").output

    assert output.status == "handoff"
    assert output.handoff_reason == "pricing"
    assert state.context.conversation.state.mode.value == "bot"


def test_model_without_docs_is_no_docs():
    provider = ScriptedToolProvider(analysis_outputs=[analysis_output(
        sub_query("Cấu hình tham số F54", "guide.configuration", ["F54"]),
    )])

    output = _ask(docs_registry(provider, _catalog_chunks()), crm_state("Cấu hình F54"),
                  "Cấu hình tham số F54").output

    assert output.status == "no_docs"


def test_retrieval_failure_is_failed_status_not_exception():
    class BrokenChunks(FakeChunks):
        async def match(self, **kwargs):
            raise ConnectionError("db down")

    provider = ScriptedToolProvider(analysis_outputs=[analysis_output(
        sub_query("Hướng dẫn lắp đặt F86", "guide.installation", ["F86"]),
    )])

    outcome = _ask(docs_registry(provider, BrokenChunks()), crm_state("Lắp đặt F86"),
                   "Hướng dẫn lắp đặt F86")

    assert outcome.ok and outcome.output.status == "failed"
