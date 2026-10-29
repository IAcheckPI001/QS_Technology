from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.modules.chatbot.schemas import InboundRequest, OutboundResponse
from app.modules.chatbot.schemas.channels import CRMChatIn, WebsiteChatIn
from app.modules.chatbot.schemas.security.principal import PrincipalContext, RequestContext
from app.modules.chatbot.schemas.system import (
    Candidate, LLMCall, RetrievalTrace, RunContext, RunState,
)
from tests.chatbot.builders import make_principal, make_request_context, make_service_principal

INBOUND = {
    "schema_version": "1.0",
    "message": {"message_id": "m3", "text": "  còn điều khoản 5 thì sao?  "},
    "session": {"session_id": "sess_abc"},
    "channel": {"type": "crm", "branch": None},
    "resources": {"ticket_id": "TK-1029"},
}

META = {"doc_id": "d_42", "version": 3, "title": "Hợp đồng lao động mẫu 2026",
        "page": 8, "section": "Điều 5", "url": None}

WEBSITE_BODY = {
    "schema_version": "1.0",
    "session_id": None,
    "message": {"text": "  Địa chỉ công ty?  "},
    "client_context": {"locale": "vi", "timezone": "Asia/Ho_Chi_Minh",
                       "page_url": "https://example.com/san-pham"},
}


# --- Hợp đồng public theo kênh -------------------------------------------------

def test_channel_body_ignores_unknown_fields_and_client_ids():
    body = WebsiteChatIn.model_validate({
        **WEBSITE_BODY,
        "channel": "crm",                           # channel do endpoint quyết định
        "message": {"message_id": "client-id", "text": "hi"},
        "crm_extra_field": "bị bỏ qua",
    })

    dumped = body.model_dump()
    assert "channel" not in dumped and "crm_extra_field" not in dumped
    assert "message_id" not in dumped["message"]


def test_channel_body_strips_text():
    assert WebsiteChatIn.model_validate(WEBSITE_BODY).message.text == "Địa chỉ công ty?"


@pytest.mark.parametrize("patch", [
    {"message": {"text": "   "}},                                         # text rỗng
    {"message": {"text": "x" * 4001}},                                    # quá dài
    {"session_id": "sess_abc"},                                           # không phải UUID
    {"schema_version": "2.0"},
    {"client_context": {"timezone": "Asia/Ho Chi Minh"}},                 # không phải tên IANA
    {"client_context": {"locale": "vietnamese"}},
    {"client_context": {"page_url": "https://example.com/" + "a" * 2048}},
])
def test_website_body_rejects(patch):
    with pytest.raises(ValidationError):
        WebsiteChatIn.model_validate({**WEBSITE_BODY, **patch})


def test_crm_body_requires_user_id_and_ignores_website_fields():
    body = CRMChatIn.model_validate({
        "user_id": " employee_456 ",
        "message": {"text": "Lỗi CNC F86"},
        "client_context": {"locale": "vi"},
        "context_refs": {"ticket_id": "TK-1"},
    })
    assert body.user_id == "employee_456" and body.session_id is None
    assert set(body.model_dump()) == {"schema_version", "user_id", "session_id", "message"}
    for missing in ({"message": {"text": "hi"}}, {"user_id": "   ", "message": {"text": "hi"}}):
        with pytest.raises(ValidationError):
            CRMChatIn.model_validate(missing)


# --- InboundRequest nội bộ (strict) --------------------------------------------

def test_inbound_ok_and_strips_text():
    req = InboundRequest.model_validate(INBOUND)
    assert req.message.text == "còn điều khoản 5 thì sao?"
    assert req.message.idempotency_key is None


def test_inbound_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        InboundRequest.model_validate({**INBOUND, "request": {"request_id": "r"}})


@pytest.mark.parametrize("patch", [
    {"message": {"message_id": "m3", "text": "   "}},                       # text rỗng
    {"channel": {"type": "zalo"}},                                         # kênh lạ
    {"schema_version": "2.0"},
    {"channel": {"type": "website"}},                                      # website có resources
])
def test_inbound_rejects(patch):
    with pytest.raises(ValidationError):
        InboundRequest.model_validate({**INBOUND, **patch})


def test_website_without_resources_ok():
    data = {**INBOUND, "channel": {"type": "website"}, "resources": {}}
    assert InboundRequest.model_validate(data).resources.ticket_id is None


# --- Principal / RequestContext ------------------------------------------------

def test_only_service_principal_is_supported():
    for principal_type, authn_method in (("guest", "guest_token"), ("employee", "crm_jwt")):
        with pytest.raises(ValidationError):
            PrincipalContext(subject_id="x", principal_type=principal_type,
                             authn_method=authn_method, tenant_id="t1", credential_id="k1")


def test_service_principal_requires_tenant_and_credential():
    base = {"subject_id": "crm_sales", "principal_type": "service",
            "authn_method": "service_key"}
    for patch in ({}, {"tenant_id": "t1"}, {"credential_id": "k1"},
                  {"tenant_id": "t1", "credential_id": "k1", "roles": frozenset({"admin"})}):
        with pytest.raises(ValidationError):
            PrincipalContext(**base, **patch)
    assert PrincipalContext(**base, tenant_id="t1", credential_id="k1").tenant_id == "t1"


def test_acting_for_revalidates():
    service = make_service_principal(None)

    assert service.acting_for("employee_456").acting_user_id == "employee_456"
    assert service.acting_user_id is None
    with pytest.raises(ValidationError):
        service.acting_for("   ")


def test_request_context_requires_aware_datetime():
    with pytest.raises(ValidationError):
        RequestContext(request_id="req-00001", channel="website", received_at=datetime.now())
    assert RequestContext(request_id="req-00001", channel="website",
                          received_at=datetime.now(timezone.utc)).branch is None


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
    state = RunState(
        input=InboundRequest.model_validate(INBOUND),
        principal=make_principal(),
        request_context=make_request_context(),
        context=ctx,
    )
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

def test_outbound_rejects_unknown_field():
    with pytest.raises(ValidationError):
        OutboundResponse.model_validate({**OUT, "internal_trace": "secret"})
