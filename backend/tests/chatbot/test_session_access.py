import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.services import SessionAccessService, SessionNotFound
from tests.chatbot.builders import make_principal, make_service_principal


class FakeSessionStore:
    def __init__(self):
        self.rows = {}
        self.touched = []

    async def get_by_id(self, session_id):
        return self.rows.get(session_id)

    async def create(self, *, session_id, principal_type, subject_id, tenant_id,
                     acting_user_id, channel):
        self.rows[session_id] = SimpleNamespace(
            principal_type=principal_type,
            subject_id=subject_id,
            tenant_id=tenant_id,
            acting_user_id=acting_user_id,
            channel=channel,
            expires_at=None,
            revoked_at=None,
        )

    async def touch(self, session_id):
        self.touched.append(session_id)


def _resolve(store, session_id, principal=None, channel=ChannelType.WEBSITE):
    service = SessionAccessService(store)
    return asyncio.run(service.resolve_or_create(session_id, principal or make_principal(), channel))


def test_missing_session_id_creates_session_owned_by_principal():
    store = FakeSessionStore()

    session_id = _resolve(store, None)

    row = store.rows[session_id]
    assert (row.principal_type, row.subject_id, row.acting_user_id, row.channel) == (
        "service", "website_main", None, "website")


def test_owner_can_resume_session():
    store = FakeSessionStore()
    session_id = _resolve(store, None)

    assert _resolve(store, session_id) == session_id
    assert store.touched == [session_id]


@pytest.mark.parametrize("case", ["unknown", "other_integration", "with_acting_user", "other_channel",
                                  "revoked", "expired"])
def test_inaccessible_session_is_not_found(case):
    store = FakeSessionStore()
    session_id = _resolve(store, None)
    principal, channel = make_principal(), ChannelType.WEBSITE
    if case == "unknown":
        session_id = uuid4()
    elif case == "other_integration":
        principal = make_principal("website_other")
    elif case == "with_acting_user":
        principal = make_service_principal("employee-1", integration_id="website_main")
    elif case == "other_channel":
        channel = ChannelType.CRM
    elif case == "revoked":
        store.rows[session_id].revoked_at = datetime.now(UTC)
    elif case == "expired":
        store.rows[session_id].expires_at = datetime.now(UTC) - timedelta(seconds=1)

    with pytest.raises(SessionNotFound):
        _resolve(store, session_id, principal, channel)
    assert store.touched == []


def test_service_session_records_acting_user_and_resumes_for_same_user():
    store = FakeSessionStore()
    principal = make_service_principal("employee-1")

    session_id = _resolve(store, None, principal, ChannelType.CRM)

    row = store.rows[session_id]
    assert (row.principal_type, row.subject_id, row.acting_user_id) == (
        "service", "crm_sales", "employee-1")
    assert _resolve(store, session_id, make_service_principal("employee-1"),
                    ChannelType.CRM) == session_id


@pytest.mark.parametrize("other", [
    make_service_principal("employee-2"),                          # nhân viên khác cùng CRM
    make_service_principal("employee-1", integration_id="crm_hr"),  # CRM khác, trùng user_id
    make_service_principal(None),                                  # service không kèm user
])
def test_service_session_of_another_user_is_not_found(other):
    store = FakeSessionStore()
    session_id = _resolve(store, None, make_service_principal("employee-1"), ChannelType.CRM)

    with pytest.raises(SessionNotFound):
        _resolve(store, session_id, other, ChannelType.CRM)
