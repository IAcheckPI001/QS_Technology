import asyncio
import json

import pytest
from pydantic import BaseModel

from app.modules.chatbot.schemas.default import SystemModel
from app.modules.chatbot.schemas.system import ToolCallRequest
from app.modules.chatbot.stages.execution_stage import SourceAllocator
from app.modules.chatbot.tools import (
    ToolConfigurationError,
    ToolContext,
    ToolOutcome,
    ToolOutput,
    ToolRegistry,
    ToolSpec,
)
from app.modules.chatbot.tools.product_docs import (
    DocsSource,
    DocsSourceGroup,
    ProductDocsAskOutput,
)
from tests.chatbot.agent_fakes import EchoIn, EchoOut, ToolProbe, crm_state, echo_tool


def _context(call_id="c1"):
    return ToolContext(parent_state=crm_state(), sources=SourceAllocator(), tool_call_id=call_id)


def _invoke(registry, name, arguments, *, allowed=None, timeout_s=5.0):
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    call = ToolCallRequest(id="c1", name=name, arguments_raw=raw)
    return asyncio.run(registry.invoke(
        call,
        _context(),
        allowed=registry.names if allowed is None else allowed,
        timeout_s=timeout_s,
    ))


def _words(text: str) -> int:
    return len(text.split())


# --- 8 tình huống tool-call ------------------------------------------------------

def test_valid_arguments_run_the_tool():
    outcome = _invoke(ToolRegistry([echo_tool()]), "echo", {"text": "hi"})

    assert outcome.ok and outcome.output == EchoOut(text="hi")
    assert json.loads(outcome.message_content(100, _words)) == {"text": "hi"}


@pytest.mark.parametrize("arguments, detail", [
    ("{not json", "arguments is not valid JSON"),
    ("[1, 2]", "arguments must be a JSON object"),
    ({"text": 1}, "text: Input should be a valid string"),
    ({"text": "hi", "extra": True}, "extra: Extra inputs are not permitted"),
    ({}, "text: Field required"),
])
def test_invalid_arguments_do_not_run_and_explain_without_echoing_values(arguments, detail):
    probe = ToolProbe()
    outcome = _invoke(ToolRegistry([echo_tool(probe=probe)]), "echo", arguments)

    assert outcome.error_code == "tool_invalid_args"
    assert outcome.error_detail == detail
    assert probe.max_running == 0
    assert json.loads(outcome.message_content(100, _words)) == {
        "error": "tool_invalid_args", "detail": detail,
    }


def test_unknown_tool_is_reported_to_the_llm():
    outcome = _invoke(ToolRegistry([echo_tool()]), "missing", {"text": "hi"})

    assert outcome.error_code == "tool_not_found"


def test_tool_outside_allowed_list_is_rejected_even_if_registered():
    probe = ToolProbe()
    outcome = _invoke(ToolRegistry([echo_tool(probe=probe)]), "echo", {"text": "hi"}, allowed=[])

    assert outcome.error_code == "tool_not_allowed"
    assert probe.max_running == 0


def test_tool_exception_becomes_error_code_only(caplog):
    outcome = _invoke(ToolRegistry([echo_tool(fail=True)]), "echo", {"text": "hi"})

    assert outcome.error_code == "tool_failed"
    assert outcome.error_detail is None
    assert json.loads(outcome.message_content(100, _words)) == {"error": "tool_failed"}
    assert "agent tool failed tool=echo" in caplog.text


def test_tool_timeout_uses_the_smaller_of_call_and_spec_limits():
    registry = ToolRegistry([echo_tool(delay=1.0, timeout_s=0.05)])

    outcome = _invoke(registry, "echo", {"text": "hi"}, timeout_s=5.0)

    assert outcome.error_code == "tool_timeout"
    assert outcome.latency_ms < 900


def test_no_time_left_means_timeout_without_running():
    probe = ToolProbe()
    outcome = _invoke(ToolRegistry([echo_tool(probe=probe)]), "echo", {"text": "hi"}, timeout_s=0)

    assert outcome.error_code == "tool_timeout"
    assert probe.max_running == 0


def test_output_of_wrong_type_is_rejected():
    class Other(ToolOutput):
        value: int

    async def run(arguments, context):
        return Other(value=1)

    spec = ToolSpec(name="bad", description="bad", input_model=EchoIn, output_model=EchoOut, run=run)
    outcome = _invoke(ToolRegistry([spec]), "bad", {"text": "x"})

    assert outcome.error_code == "tool_invalid_output"


def test_output_over_budget_is_replaced_by_error():
    outcome = ToolOutcome(tool_call_id="c1", name="echo", output=EchoOut(text="a " * 200))

    assert json.loads(outcome.message_content(50, _words)) == {"error": "tool_output_too_large"}


def test_cancellation_is_propagated_not_turned_into_tool_failed():
    probe = ToolProbe()
    registry = ToolRegistry([echo_tool(probe=probe, block=asyncio.Event())])

    async def run():
        call = ToolCallRequest(id="c1", name="echo", arguments_raw='{"text": "hi"}')
        task = asyncio.create_task(
            registry.invoke(call, _context(), allowed=["echo"], timeout_s=5.0)
        )
        await probe.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())

    assert probe.cancelled == ["hi"]


# --- đăng ký tool ----------------------------------------------------------------

def test_register_rejects_names_providers_do_not_accept():
    with pytest.raises(ToolConfigurationError, match="invalid tool name"):
        ToolRegistry([echo_tool(name="product_docs.ask")])


def test_register_rejects_duplicate_names():
    with pytest.raises(ToolConfigurationError, match="already registered"):
        ToolRegistry([echo_tool(), echo_tool()])


def test_register_requires_input_model_that_forbids_extra_fields():
    class LooseIn(BaseModel):
        text: str

    spec = ToolSpec(name="loose", description="x", input_model=LooseIn, output_model=EchoOut,
                    run=echo_tool().run)

    with pytest.raises(ToolConfigurationError, match="extra='forbid'"):
        ToolRegistry([spec])


def test_allowed_filters_tools_that_require_a_scope():
    open_tool = echo_tool(name="open")
    scoped = ToolSpec(**{**echo_tool(name="crm_report").__dict__, "required_scope": "crm.reports"})
    registry = ToolRegistry([open_tool, scoped])

    principal = crm_state().principal
    assert [spec.name for spec in registry.allowed(principal)] == ["open"]
    granted = principal.model_copy(update={"scopes": frozenset({"crm.reports"})})
    assert [spec.name for spec in registry.allowed(granted)] == ["open", "crm_report"]


# --- cắt output theo cấu trúc ------------------------------------------------------

def _docs_output(*contents):
    return ProductDocsAskOutput(
        status="answered",
        sources=[DocsSourceGroup(
            query="Lắp đặt F86",
            answer_mode="full",
            sources=[
                DocsSource(source_id=f"S{i}", section=f"Mục {i}", content=content)
                for i, content in enumerate(contents, start=1)
            ],
        )],
    )


def test_docs_output_within_budget_is_not_truncated():
    payload = _docs_output("Câu một. Câu hai.").to_llm(1000, _words)

    assert "truncated" not in payload
    assert payload["sources"][0]["sources"][0]["content"] == "Câu một. Câu hai."


def test_docs_output_keeps_status_and_cuts_last_source_at_sentence_boundary():
    long_text = " ".join(f"Câu số {i} mô tả bước lắp đặt." for i in range(60))
    output = _docs_output("Đoạn đầu ngắn.", long_text, "Đoạn thứ ba bị lược.")

    payload = output.to_llm(200, _words)

    assert payload["status"] == "answered"
    kept = payload["sources"][0]["sources"]
    assert [source["source_id"] for source in kept] == ["S1", "S2"]
    assert kept[1]["content"].endswith("lắp đặt. …")
    assert payload["truncated"] is True
    assert payload["omitted_sources"] == 1
    assert _words(json.dumps(payload, ensure_ascii=False)) <= 200


def test_docs_output_uses_token_counter_not_characters():
    # Cùng số ký tự nhưng đếm token khác nhau: cắt theo hàm count truyền vào.
    output = _docs_output("x " * 300)

    by_chars = output.to_llm(200, len)
    by_words = output.to_llm(400, _words)

    assert by_chars["sources"][0]["sources"] == []
    assert by_words["sources"][0]["sources"][0]["content"] == "x " * 300
