import pytest
from pydantic import ValidationError
 
from app.modules.chatbot.schemas.system import (
    Candidate, LLMCall, RetrievalTrace, RunContext, RunState,
)
from app.modules.chatbot.schemas import InboundRequest, OutboundResponse
 
INBOUND = {
    "schema_version": "1.0",
    "request": {"request_id": "req_1", "ticket_id": "TK-1029", "user_id": "u_123"},
    "message": {"message_id": "m3", "text": "  còn điều khoản 5 thì sao?  "},
    "session": {"session_id": "sess_abc"},
    "channel": {"type": "crm", "branch": "support-technical"},
    "crm_extra_field": "bị bỏ qua",
}
 
META = {"doc_id": "d_42", "version": 3, "title": "Hợp đồng lao động mẫu 2026",
        "page": 8, "section": "Điều 5", "url": None}
 
def test_inbound_ignores_unknown_fields():
    req = InboundRequest.model_validate(INBOUND)

    assert not hasattr(req, "crm_extra_field")
    assert "crm_extra_field" not in req.model_dump()

def test_outbound_rejects_unknown_field():
    data = {
        **OUT,
        "internal_trace": "secret"
    }

    with pytest.raises(ValidationError):
        OutboundResponse.model_validate(data)
def test_request_id_is_stripped():
    req = InboundRequest.model_validate({
        **INBOUND,
        "request": {
            **INBOUND["request"],
            "request_id": "  req_1  ",
        },
    })

    assert req.request.request_id == "req_1"

def test_inbound_ok_and_strips_text():
    req = InboundRequest.model_validate(INBOUND)
    assert req.message.text == "còn điều khoản 5 thì sao?"

@pytest.mark.parametrize("patch", [
    {"message": {"message_id": "m3", "text": "   "}},                       # text rỗng
    {"channel": {"type": "zalo", "branch": "support-technical"}},          # kênh lạ
    {"request": {"request_id": "req_1"}},                                  # crm thiếu ticket
    {"schema_version": "2.0"},
])

def test_inbound_rejects(patch):
    with pytest.raises(ValidationError):
        InboundRequest.model_validate({**INBOUND, **patch})
 

from datetime import datetime, timezone

def test_received_at_accepts_aware_datetime():
    data = {
        **INBOUND,
        "request": {
            **INBOUND["request"],
            "received_at": datetime.now(timezone.utc),
        },
    }

    req = InboundRequest.model_validate(data)

    assert req.request.received_at is not None

def test_received_at_rejects_naive_datetime():
    data = {
        **INBOUND,
        "request": {
            **INBOUND["request"],
            "received_at": datetime.now(),
        },
    }

    with pytest.raises(ValidationError):
        InboundRequest.model_validate(data)

 
def test_website_without_ticket_ok():
    data = {**INBOUND, "request": {"request_id": "r"},
            "channel": {"type": "website", "branch": "support-sale"}}
    assert InboundRequest.model_validate(data).request.ticket_id is None
 
 
def test_run_context_and_state():
    ctx = RunContext.model_validate({
        "conversation": {"summary": None, "history": [
            {"role": "user", "content": "Điều khoản 4 quy định gì?", "message_id": "m1"},
            {"role": "assistant", "content": "… [S1]", "message_id": "m2",
             "citations": [{"source_id": "S1", "chunk_id": "c_100",
                            "metadata": {**META, "page": 7, "section": "Điều 4"}}]},
        ]},
        "query": {"origin": "còn điều khoản 5 thì sao?",
                  "standalone": "Điều khoản 5 của hợp đồng lao động mẫu 2026 quy định gì?",
                  "language": "vi",
                  "rewrite": {"method": "llm", "provider": "self_host", "model": "qwen2.5-7b"}},
        "retrieval_scope": {"collections": ["technical-knowledge"]},
    })
    state = RunState(input=InboundRequest.model_validate(INBOUND), context=ctx)
    sid = state.next_source_id()
    assert sid == "S2"  # tiếp nối S1 trong history
 
    state.add_trace(RetrievalTrace.model_validate({
        "retrieval_id": "r_1", "iteration": 0, "query": ctx.query.standalone,
        "params": {"top_k": 20, "rerank_top_n": 5,
                   "filters": {"collections": ["technical-knowledge"]}},
        "candidates": [
            {"chunk_id": "c_901", "source_id": sid, "selected": True,
             "scores": {"keyword": 12.4, "vector": 0.83, "fused": 0.031, "rerank": 0.94},
             "metadata": META},
            {"chunk_id": "c_455", "selected": False, "reject_reason": "below_rerank_threshold",
             "scores": {"vector": 0.71, "rerank": 0.22}, "metadata": {"doc_id": "d_17", "version": 1}},
        ],
        "latency_ms": 180,
    }))
    assert list(state.sources()) == ["S2"]
 
    state.stats.record(LLMCall(stage="rewrite", provider="self_host", model="qwen2.5-7b",
                               input_tokens=420, output_tokens=35, latency_ms=310))
    state.stats.record(LLMCall(stage="think", iteration=0, provider="openai", model="gpt-4o-mini",
                               input_tokens=4700, output_tokens=175, latency_ms=1650))
    assert state.stats.total.input_tokens == 5120
 
 
def test_candidate_selected_requires_source_id():
    with pytest.raises(ValidationError):
        Candidate.model_validate({"chunk_id": "c", "selected": True, "scores": {}, "metadata": META})
 
 
def test_rewrite_llm_requires_model():
    from app.modules.chatbot.schemas.system import RewriteInfo
    with pytest.raises(ValidationError):
        RewriteInfo(method="llm")
    assert RewriteInfo(method="passthrough").model is None
 
 
OUT = {
    "request_id": "req_1", "session_id": "sess_abc", "ticket_id": "TK-1029",
    "status": "answered",
    "answer": {"text": "Điều 5 quy định thời gian thử việc tối đa 60 ngày [1]."},
    "citations": [{"index": 1, "source_id": "S2", "chunk_id": "c_901",
                   "snippet": "…không quá 60 ngày…", "metadata": META}],
}
 
 
def test_outbound_answered_ok():
    res = OutboundResponse.model_validate(OUT)
    assert res.model_dump(mode="json")["schema_version"] == "1.0"
 
 
@pytest.mark.parametrize("patch", [
    {"answer": {"text": "… [1] và [2]."}},                                   # marker [2] thiếu citation
    {"citations": [{**OUT["citations"][0], "metadata": {**META, "title": None}}]},  # title null
    {"status": "handoff"},                                                   # thiếu handoff
    {"status": "error", "answer": None, "citations": []},                    # thiếu error
])
def test_outbound_rejects(patch):
    with pytest.raises(ValidationError):
        OutboundResponse.model_validate({**OUT, **patch})
 
 
def test_outbound_not_found_handoff():
    res = OutboundResponse.model_validate({
        **OUT, "status": "not_found", "citations": [],
        "answer": {"text": "Em đã chuyển cho chuyên viên hỗ trợ ạ."},
        "handoff": {"reason": "not_found", "target_branch": "support-technical",
                    "summary_for_agent": "Khách hỏi điều 5 HĐLĐ 2026, KB chưa có."},
    })
    assert res.handoff.reason == "not_found"