"""product_docs_ask với dữ liệu sản phẩm có cấu trúc: catalog_match, awaiting_models, bằng chứng model."""

import asyncio
import json

import pytest

from app.modules.chatbot.schemas.system import AgentRun, ConversationState, ToolCallRequest
from app.modules.chatbot.stages.execution_stage import SourceAllocator
from app.modules.chatbot.tools import ToolContext
from app.modules.chatbot.tools.product_docs import ProductDocsTurnState
from tests.chatbot.agent_fakes import (
    FakeChunks,
    ScriptedToolProvider,
    analysis_output,
    chunk,
    crm_state,
    docs_registry,
    sub_query,
)

ETHERCAT = ["F86", "F10T", "ASTRO_10S", "ASTRO_6AH", "ASTRO_6AV", "ASTRO_10I"]


def _find(question, *, ci=(), excluded=(), match="all", unmapped=()):
    return sub_query(question, "lookup.product_catalog", ci=ci, excluded=excluded, match=match,
                     unmapped=unmapped, dependency="general")


def _call(registry, state, arguments, call_id="c1", allocator=None):
    state.agent = state.agent or AgentRun()
    context = ToolContext(
        parent_state=state,
        sources=allocator or SourceAllocator.for_state(state),
        tool_call_id=call_id,
    )
    if isinstance(arguments, str):
        arguments = {"question": arguments}
    call = ToolCallRequest(id=call_id, name="product_docs_ask", arguments_raw=json.dumps(arguments))
    return asyncio.run(registry.invoke(call, context, allowed=registry.names, timeout_s=10))


def _ask(analysis_outputs, question, *, chunks=None, state=None):
    provider = ScriptedToolProvider(analysis_outputs=analysis_outputs)
    chunks = chunks if chunks is not None else FakeChunks()
    state = state or crm_state(question)
    outcome = _call(docs_registry(provider, chunks), state, question)
    assert outcome.ok, outcome.error_code
    return outcome.output, chunks, state


def _discovered(state):
    turn = state.agent.tool_state(ProductDocsTurnState)
    return turn.discovered_models if turn is not None else []


def _codes(output):
    return [model.code for model in output.catalog_match.models]


def _task_statuses(output):
    return [task.status for task in output.task_results]


# --- catalog_match / next_action -----------------------------------------------------------

def test_many_matches_ask_selection_without_retrieval_or_evidence():
    output, chunks, state = _ask(
        [analysis_output(_find("Các model hỗ trợ EtherCAT", ci=["ethercat"]))],
        "Các model hỗ trợ EtherCAT",
    )

    assert output.status == "matched"
    assert _codes(output) == ETHERCAT
    assert output.catalog_match.next_action == "ask_selection"
    assert output.catalog_match.applied.control_interface == ["ethercat"]
    assert chunks.calls == []                     # dữ liệu có cấu trúc: không vector search
    assert _discovered(state) == []    # vượt ngưỡng: chưa được tra tiếp
    [task] = output.task_results
    assert (task.kind, task.status) == ("catalog", "completed")


@pytest.mark.parametrize(("conditions", "expected"), [
    ({"ci": ["ethercat", "mechatrolink"]}, ["ASTRO_6AH", "ASTRO_6AV", "ASTRO_10I"]),
    ({"ci": ["ethercat"], "excluded": ["mechatrolink"]}, ["F86", "F10T", "ASTRO_10S"]),
])
def test_few_matches_lookup_each_and_become_evidence(conditions, expected):
    output, chunks, state = _ask([analysis_output(_find("Tìm model", **conditions))], "Tìm model")

    assert output.status == "matched"
    assert _codes(output) == expected
    assert output.catalog_match.next_action == "lookup_each"
    assert _discovered(state) == expected
    assert chunks.calls == []


def test_or_conditions_use_any_match():
    output, _, _ = _ask(
        [analysis_output(_find("Model hỗ trợ EtherCAT hoặc Mechatrolink",
                               ci=["ethercat", "mechatrolink"], match="any"))],
        "Model hỗ trợ EtherCAT hoặc Mechatrolink",
    )

    assert _codes(output) == ETHERCAT
    assert output.catalog_match.applied.match == "any"
    assert output.catalog_match.next_action == "ask_selection"


def test_no_match_is_reported_not_clarified():
    output, chunks, _ = _ask(
        [analysis_output(
            _find("Model hỗ trợ Mechatrolink nhưng không hỗ trợ EtherCAT",
                  ci=["mechatrolink"], excluded=["ethercat"]),
            sub_query("Hướng dẫn lắp đặt model đó", "guide.installation"),
        )],
        "Model hỗ trợ Mechatrolink nhưng không hỗ trợ EtherCAT? Hướng dẫn lắp đặt model đó.",
    )

    assert output.status == "no_match"
    assert output.catalog_match.models == []
    assert output.catalog_match.next_action == "report_no_match"
    assert output.clarification is None
    assert _task_statuses(output) == ["completed", "awaiting_models"]
    assert chunks.calls == []


def test_condition_outside_table_still_retrieves_without_model_filter():
    # "Model nào có 6 trục?": số trục chưa có trong bảng capabilities.
    output, chunks, _ = _ask(
        [analysis_output(_find("Các model có 6 trục", unmapped=["6 trục"]))],
        "Các model có 6 trục",
        chunks=FakeChunks({("product_catalog", ()): [chunk(5, doc_id="catalog")]}),
    )

    assert output.status == "answered"
    assert output.catalog_match.next_action == "verify_with_sources"
    assert output.catalog_match.unmapped_conditions == ["6 trục"]
    assert len(output.catalog_match.models) == 7      # ứng viên, chưa phải kết quả
    assert chunks.calls[0]["models"] is None           # giữ cả chunk catalog chung
    assert output.sources[0].product_models == []


def test_known_and_unknown_conditions_narrow_candidates_then_retrieve():
    output, chunks, _ = _ask(
        [analysis_output(_find("Model hỗ trợ EtherCAT và Profinet", ci=["ethercat"],
                               unmapped=["Profinet"]))],
        "Model hỗ trợ EtherCAT và Profinet",
    )

    assert output.catalog_match.next_action == "verify_with_sources"
    assert chunks.calls[0]["models"] == ETHERCAT
    assert output.status == "no_docs"     # không nguồn nào: không kết luận được về Profinet


def test_known_condition_excluding_everything_skips_unknown_condition():
    output, chunks, _ = _ask(
        [analysis_output(_find("Model hỗ trợ Mechatrolink, không EtherCAT, có 6 trục",
                               ci=["mechatrolink"], excluded=["ethercat"], unmapped=["6 trục"]))],
        "Model hỗ trợ Mechatrolink, không EtherCAT, có 6 trục",
    )

    assert output.status == "no_match"
    assert chunks.calls == []


# --- awaiting_models: câu hỏi phụ thuộc kết quả tìm trong cùng lần gọi --------------------

def test_dependent_question_in_same_call_awaits_models():
    question = "Model nào hỗ trợ EtherCAT và Mechatrolink? Hướng dẫn lắp đặt model đó."
    output, chunks, _ = _ask(
        [analysis_output(
            _find("Các model hỗ trợ EtherCAT và Mechatrolink", ci=["ethercat", "mechatrolink"]),
            sub_query("Hướng dẫn lắp đặt các model đó", "guide.installation"),
        )],
        question,
    )

    assert output.status == "matched"
    assert _task_statuses(output) == ["completed", "awaiting_models"]
    assert output.clarification is None     # không phải câu hỏi lại nhân viên
    assert chunks.calls == []


def test_model_inherited_from_session_is_not_used_for_dependent_question():
    # Phiên đang bàn F54; "model đó" là kết quả tìm, không phải F54.
    question = "Model nào hỗ trợ EtherCAT và Mechatrolink? Hướng dẫn lắp đặt model đó."
    state = crm_state(question)
    state.context.conversation.state = ConversationState(last_models=["F54"], active_model="F54")
    output, chunks, _ = _ask(
        [analysis_output(
            _find("Các model hỗ trợ EtherCAT và Mechatrolink", ci=["ethercat", "mechatrolink"]),
            sub_query("Hướng dẫn lắp đặt model đó", "guide.installation"),
        )],
        question,
        state=state,
    )

    assert _task_statuses(output) == ["completed", "awaiting_models"]
    assert chunks.calls == []        # không tra lắp đặt cho F54


def test_comparison_with_discovered_models_awaits_models():
    question = "So sánh F86 với các model hỗ trợ Mechatrolink"
    output, chunks, _ = _ask(
        [analysis_output(
            _find("Các model hỗ trợ Mechatrolink", ci=["mechatrolink"]),
            sub_query(question, "compare.product_models", ["F86"]),
        )],
        question,
    )

    assert output.catalog_match.next_action == "lookup_each"
    assert _task_statuses(output) == ["completed", "awaiting_models"]
    assert chunks.calls == []


def test_independent_questions_are_not_treated_as_discovery():
    question = "F86 có bao nhiêu trục? F54 thì sao?"
    output, chunks, _ = _ask(
        [analysis_output(
            sub_query("F86 có bao nhiêu trục?", "lookup.product_info", ["F86"]),
            sub_query("F54 có bao nhiêu trục?", "lookup.product_info", ["F54"]),
        )],
        question,
        chunks=FakeChunks({
            ("product_catalog", ("F86",)): [chunk(1, doc_id="catalog")],
            ("product_catalog", ("F54",)): [chunk(2, doc_id="catalog")],
        }),
    )

    assert output.status == "answered" and output.catalog_match is None
    assert _task_statuses(output) == ["completed", "completed"]
    assert sorted(call["models"][0] for call in chunks.calls) == ["F54", "F86"]
    assert [group.product_models for group in output.sources] == [["F86"], ["F54"]]


def test_missing_model_without_discovery_still_needs_clarification():
    output, _, _ = _ask(
        [analysis_output(sub_query("Hướng dẫn lắp đặt", "guide.installation"))],
        "Hướng dẫn lắp đặt",
    )

    assert output.status == "needs_clarification"
    assert output.clarification.reason == "missing_product_model"
    assert output.catalog_match is None


def test_conflicting_interface_conditions_are_unclear():
    output, _, _ = _ask(
        [analysis_output(_find("Model hỗ trợ và không hỗ trợ EtherCAT", ci=["ethercat"],
                               excluded=["ethercat"]))],
        "Model hỗ trợ và không hỗ trợ EtherCAT",
    )

    assert output.status == "needs_clarification"
    assert output.clarification.reason == "unclear_query"


# --- Bằng chứng model giữa các lần gọi trong một lượt -------------------------------------

def _six_axes_chunks(content="F10T điều khiển tối đa 6 trục."):
    return FakeChunks({
        ("product_catalog", ()): [chunk(5, doc_id="catalog", content=content)],
        ("product_catalog", ("F10T",)): [chunk(6, doc_id="catalog")],
        ("product_catalog", ("ASTRO_6AH",)): [chunk(7, doc_id="catalog")],
    })


def _two_calls(second_arguments, *, follow_up=None, content="F10T điều khiển tối đa 6 trục."):
    outputs = [analysis_output(_find("Các model có 6 trục", unmapped=["6 trục"]))]
    if follow_up is not None:
        outputs.append(analysis_output(follow_up))
    chunks = _six_axes_chunks(content)
    registry = docs_registry(ScriptedToolProvider(analysis_outputs=outputs), chunks)
    state = crm_state("Model nào có 6 trục? Hướng dẫn lắp đặt model đó.")
    state.agent = AgentRun()
    allocator = SourceAllocator.for_state(state)
    first = _call(registry, state, "Các model có 6 trục", "c1", allocator)
    second = _call(registry, state, second_arguments, "c2", allocator)
    return first, second, chunks, state


def test_model_from_cited_source_is_accepted():
    first, second, chunks, state = _two_calls(
        {"question": "Hướng dẫn lắp đặt F10T", "based_on_sources": ["S1"]},
        follow_up=sub_query("Hướng dẫn lắp đặt F10T", "guide.installation", ["F10T"]),
    )

    assert first.output.sources[0].sources[0].source_id == "S1"
    assert state.agent.source_texts["S1"] == "F10T điều khiển tối đa 6 trục."
    assert second.ok and second.output.status == "answered"
    assert chunks.calls[-1]["models"] == ["F10T"]


def test_model_from_source_without_citation_is_rejected():
    _, second, chunks, _ = _two_calls({"question": "Hướng dẫn lắp đặt F10T"})

    assert second.error_code == "model_not_evidenced"
    assert len(chunks.calls) == 1     # chỉ lần tìm đầu tiên


@pytest.mark.parametrize("cited", [["S9"], ["F10T"]])
def test_unknown_cited_source_is_invalid_args(cited):
    _, second, _, _ = _two_calls({"question": "Hướng dẫn lắp đặt F10T", "based_on_sources": cited})

    assert second.error_code == "tool_invalid_args"
    assert "unknown source ids" in second.error_detail


def test_ambiguous_alias_in_cited_source_is_not_evidence():
    _, second, _, _ = _two_calls(
        {"question": "Hướng dẫn lắp đặt ASTRO_6AH", "based_on_sources": ["S1"]},
        content="Astro 6A điều khiển tối đa 6 trục.",
    )

    assert second.error_code == "model_not_evidenced"


@pytest.mark.parametrize(("conditions", "allowed"), [
    ({"ci": ["ethercat", "mechatrolink"]}, True),    # 3 model: lookup_each
    ({"ci": ["ethercat"]}, False),                   # 6 model: ask_selection, hỏi nhân viên trước
])
def test_discovered_models_are_evidence_only_when_lookup_is_allowed(conditions, allowed):
    provider = ScriptedToolProvider(analysis_outputs=[
        analysis_output(_find("Tìm model", **conditions)),
        analysis_output(sub_query("Hướng dẫn lắp đặt ASTRO_6AH", "guide.installation",
                                  ["ASTRO_6AH"])),
    ])
    registry = docs_registry(provider, _six_axes_chunks())
    state = crm_state("Tìm model rồi hướng dẫn lắp đặt")
    allocator = SourceAllocator.for_state(state)

    _call(registry, state, "Tìm model", "c1", allocator)
    second = _call(registry, state, "Hướng dẫn lắp đặt ASTRO_6AH", "c2", allocator)

    assert second.ok is allowed
    if not allowed:
        assert second.error_code == "model_not_evidenced"


# --- Ngữ cảnh model của phiên (kế thừa / xung đột bằng code) ------------------------------

def _follow_up_state(last_models, active_model=None):
    state = crm_state("Hướng dẫn lắp đặt model đó")
    state.context.conversation.state = ConversationState(
        last_models=last_models, active_model=active_model,
    )
    return state


def test_single_model_in_session_is_inherited():
    output, chunks, _ = _ask(
        [analysis_output(sub_query("Hướng dẫn lắp đặt model đó", "guide.installation"))],
        "Hướng dẫn lắp đặt model đó",
        chunks=FakeChunks({("technical_docs", ("F86",)): [chunk(1)]}),
        state=_follow_up_state(["F86"], "F86"),
    )

    assert output.status == "answered"
    assert chunks.calls[0]["models"] == ["F86"]
    assert output.task_results[0].context_model == "F86"


def test_two_models_in_session_is_context_conflict():
    output, chunks, _ = _ask(
        [analysis_output(sub_query("Hướng dẫn lắp đặt model đó", "guide.installation"))],
        "Hướng dẫn lắp đặt model đó",
        state=_follow_up_state(["F54", "F86"]),
    )

    assert output.status == "needs_clarification"
    assert output.clarification.reason == "context_conflict"
    assert [c.code for c in output.clarification.candidates] == ["F54", "F86"]
    assert chunks.calls == []
