import json
import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.middleware.request_context import RequestContextMiddleware
from app.core.security.service_key import generate_service_key
from app.modules.chatbot.adapters.crm import crm_to_inbound
from app.modules.chatbot.adapters.website import website_to_inbound
from app.modules.chatbot.dependencies import (
    get_chatbot_service,
    get_service_auth_service,
    get_session_access_service,
    get_visitor_identity_service,
)
from app.modules.chatbot.repositories.service_key_repository import ServiceKeyRecord
from app.modules.chatbot.routers import router
from app.modules.chatbot.schemas.channels import CRMChatIn, WebsiteChatIn
from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.services import (
    ChatbotService,
    ServiceAuthService,
    SessionAccessService,
    VisitorIdentityService,
)
from tests.chatbot.builders import make_request_context
from tests.chatbot.test_chat_history import FakeHistoryRepository, FakeProvider
from tests.chatbot.test_session_access import FakeSessionStore

IDENTITY = VisitorIdentityService(secret="s" * 48, issuer="qs-chatbot", ttl=timedelta(hours=1))
BODY = {"message": {"text": "Địa chỉ công ty?"}}
CRM_BODY = {"user_id": "employee_456", "message": {"text": "Lỗi CNC F86 xử lý thế nào?"}}


class FakeServiceKeyStore:
    def __init__(self):
        self.records = {}
        self.fail = False

    def issue(self, **overrides) -> str:
        generated = generate_service_key()
        self.records[generated.key_id] = replace(
            ServiceKeyRecord(
                key_id=generated.key_id,
                secret_hash=generated.secret_hash,
                expires_at=None,
                revoked_at=None,
                integration_id="crm_sales",
                tenant_id="qs_technology",
                integration_disabled_at=None,
            ),
            **overrides,
        )
        return generated.token

    async def get_by_key_id(self, key_id):
        if self.fail:
            raise ConnectionError("database down")
        return self.records.get(key_id)


class Harness:
    def __init__(self, *, identity=IDENTITY):
        self.history = FakeHistoryRepository()
        self.sessions = FakeSessionStore()
        self.keys = FakeServiceKeyStore()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_visitor_identity_service] = lambda: identity
        app.dependency_overrides[get_service_auth_service] = (
            lambda: ServiceAuthService(self.keys)
        )
        app.dependency_overrides[get_session_access_service] = (
            lambda: SessionAccessService(self.sessions)
        )
        app.dependency_overrides[get_chatbot_service] = (
            lambda: ChatbotService(FakeProvider(["Xin ", "chào"]), self.history)
        )
        self.client = TestClient(RequestContextMiddleware(app))

    def token(self, current: str | None = None) -> str:
        headers = {"Authorization": f"Bearer {current}"} if current else {}
        response = self.client.post("/chat/website/visitor", headers=headers)
        assert response.status_code == 200
        return response.json()["token"]

    def chat(self, token: str | None, body=BODY, **headers):
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return self.client.post("/chat/website", json=body, headers=headers)

    def crm_chat(self, key: str | None, body=CRM_BODY, **headers):
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return self.client.post("/chat/crm", json=body, headers=headers)


def _events(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


def test_visitor_token_endpoint_issues_and_refreshes_same_guest():
    harness = Harness()
    first = harness.token()

    response = harness.client.post("/chat/website/visitor", headers={"Authorization": f"Bearer {first}"})

    body = response.json()
    assert body["token_type"] == "Bearer" and body["schema_version"] == "1.0"
    assert IDENTITY.authenticate(body["token"]).subject_id == IDENTITY.authenticate(first).subject_id


def test_website_chat_streams_and_request_id_matches_header():
    harness = Harness()
    key = uuid4()

    response = harness.chat(harness.token(), **{"Idempotency-Key": str(key)})

    assert response.status_code == 200
    events = _events(response.text)
    assert [name for name, _ in events] == ["delta", "delta", "done"]
    done = events[-1][1]
    assert done["request_id"] == response.headers["X-Request-ID"]
    session_id = UUID(done["session_id"])
    assert harness.sessions.rows[session_id].principal_type == "guest"
    saved = harness.history.created[0]
    assert saved["idempotency_key"] == key
    assert saved["channel"] == "website"
    assert isinstance(saved["history_id"], UUID)


def test_website_chat_requires_visitor_token():
    harness = Harness()

    for token in (None, "garbage"):
        response = harness.chat(token)
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json()["detail"]["code"] == "unauthorized"
        assert response.json()["detail"]["request_id"] == response.headers["X-Request-ID"]


def test_session_of_another_guest_is_not_found():
    harness = Harness()
    owner_session = _events(harness.chat(harness.token()).text)[-1][1]["session_id"]

    response = harness.chat(harness.token(), body={**BODY, "session_id": owner_session})

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "session_not_found"


def test_invalid_idempotency_key_is_rejected():
    harness = Harness()

    response = harness.chat(harness.token(), **{"Idempotency-Key": "not-a-uuid"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_idempotency_key"


def test_website_chat_without_secret_is_not_configured():
    harness = Harness(identity=None)

    assert harness.client.post("/chat/website/visitor").status_code == 503
    response = harness.chat("anything")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "visitor_auth_not_configured"


def test_crm_chat_streams_for_service_key_and_records_acting_user():
    harness = Harness()

    response = harness.crm_chat(harness.keys.issue())

    assert response.status_code == 200
    done = _events(response.text)[-1]
    assert done[0] == "done"
    row = harness.sessions.rows[UUID(done[1]["session_id"])]
    assert (row.principal_type, row.subject_id, row.tenant_id, row.acting_user_id, row.channel) == (
        "service", "crm_sales", "qs_technology", "employee_456", "crm")
    assert harness.history.created[0]["channel"] == "crm"


def test_crm_session_is_resumable_only_by_same_employee():
    harness = Harness()
    key = harness.keys.issue()
    session_id = _events(harness.crm_chat(key).text)[-1][1]["session_id"]

    same = harness.crm_chat(key, body={**CRM_BODY, "session_id": session_id})
    other = harness.crm_chat(key, body={**CRM_BODY, "user_id": "employee_789",
                                        "session_id": session_id})

    assert _events(same.text)[-1][1]["session_id"] == session_id
    assert other.status_code == 404
    assert other.json()["detail"]["code"] == "session_not_found"


@pytest.mark.parametrize("case", ["missing", "malformed", "unknown_key", "secret_mismatch",
                                  "revoked", "expired", "integration_disabled"])
def test_crm_chat_rejects_unusable_service_key_uniformly(case, caplog):
    harness = Harness()
    now = datetime.now(UTC)
    overrides = {
        "revoked": {"revoked_at": now},
        "expired": {"expires_at": now - timedelta(seconds=1)},
        "integration_disabled": {"integration_disabled_at": now},
    }.get(case, {})
    key = harness.keys.issue(**overrides)
    if case == "missing":
        key = None
    elif case == "malformed":
        key = "sk-not-ours"
    elif case == "unknown_key":
        key = generate_service_key().token
    elif case == "secret_mismatch":
        key = key[:-1] + ("A" if key[-1] != "A" else "B")

    with caplog.at_level(logging.WARNING, logger="app.modules.chatbot.dependencies"):
        response = harness.crm_chat(key)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_service_key"
    assert detail["message"] == "Service key is missing or invalid."
    assert f"reason={case}" in caplog.text
    if key:
        assert key not in caplog.text and key.split("_", 2)[-1] not in caplog.text
    assert harness.sessions.rows == {}


def test_crm_chat_key_lookup_failure_is_unavailable_not_unauthorized():
    harness = Harness()
    key = harness.keys.issue()
    harness.keys.fail = True

    response = harness.crm_chat(key)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "database_unavailable"


def test_crm_chat_requires_user_id():
    harness = Harness()

    response = harness.crm_chat(harness.keys.issue(), body={"message": {"text": "hi"}})

    assert response.status_code == 422


def test_legacy_chatbot_post_route_is_removed():
    assert Harness().client.post("/chatbot", json=BODY).status_code == 404


def test_adapters_set_channel_from_endpoint_and_server_message_id():
    session_id, key = uuid4(), uuid4()
    website = website_to_inbound(
        WebsiteChatIn.model_validate(BODY),
        session_id=session_id,
        message_id="m-1",
        idempotency_key=key,
        request_context=make_request_context(ChannelType.WEBSITE),
    )
    crm = crm_to_inbound(
        CRMChatIn.model_validate(CRM_BODY),
        session_id=session_id,
        message_id="m-2",
        idempotency_key=None,
        request_context=make_request_context(ChannelType.CRM),
    )

    assert website.channel.type is ChannelType.WEBSITE and website.resources.is_empty()
    assert website.message.message_id == "m-1" and website.message.idempotency_key == key
    assert website.session.session_id == str(session_id)
    assert crm.channel.type is ChannelType.CRM and crm.channel.branch is None
    assert crm.resources.is_empty() and crm.client_context is None


def test_chat_request_log_has_metadata_but_no_message_text(caplog):
    harness = Harness()
    secret = "Số điện thoại em là 0912345678"

    with caplog.at_level(logging.DEBUG, logger="app.modules.chatbot.routers.chat"):
        harness.chat(harness.token(), body={"message": {"text": secret},
                                            "client_context": {"locale": "vi"}})

    record = next(r for r in caplog.records if r.getMessage().startswith("chat request"))
    message = record.getMessage()
    assert f"text_chars={len(secret)}" in message
    assert "channel=website" in message and "locale=vi" in message and "new_session=True" in message
    assert secret not in caplog.text and "0912345678" not in caplog.text
