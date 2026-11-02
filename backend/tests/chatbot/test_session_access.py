import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import anyio
import pytest

from app.modules.chatbot.schemas.default import ChannelType
from app.modules.chatbot.services import (
    SessionAccessService,
    SessionBusy,
    SessionNotFound,
    SessionTurnLease,
)
from tests.chatbot.builders import make_principal, make_service_principal


class FakeSessionStore:
    """Store của transaction request: chỉ đọc và tạo phiên, không UPDATE phiên đã có."""

    def __init__(self):
        self.rows = {}
        self.calls = []

    async def get_by_id(self, session_id):
        self.calls.append(("get_by_id", session_id))
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



class FakeTurnLeaseStore:
    """Lease trong bộ nhớ: cùng ngữ nghĩa với ChatTurnLeaseRepository (không hết hạn)."""

    def __init__(self):
        self.held = set()
        self.acquired = []
        self.released = []

    async def acquire(self, session_id, ttl_s):
        if session_id in self.held:
            return False
        self.held.add(session_id)
        self.acquired.append(session_id)
        return True

    async def release(self, session_id):
        self.held.discard(session_id)
        self.released.append(session_id)


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

    store.calls.clear()

    assert _resolve(store, session_id) == session_id
    # Không UPDATE chat_sessions trong transaction của request: khóa dòng sẽ chặn
    # lease theo phiên (connection riêng) tới statement_timeout.
    assert store.calls == [("get_by_id", session_id)]


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


def test_turn_lease_rejects_second_holder_until_released():
    store = FakeTurnLeaseStore()
    lease = SessionTurnLease(store, ttl_s=120)
    session_id = uuid4()

    async def scenario():
        await lease.acquire(session_id)
        with pytest.raises(SessionBusy):
            await lease.acquire(session_id)
        await lease.release(session_id)
        await lease.acquire(session_id)

    asyncio.run(scenario())

    assert store.acquired == [session_id, session_id]


def test_turn_lease_release_finishes_even_when_task_is_cancelled():
    class SlowReleaseStore(FakeTurnLeaseStore):
        async def release(self, session_id):
            await asyncio.sleep(0.05)
            await super().release(session_id)

    store = SlowReleaseStore()
    lease = SessionTurnLease(store, ttl_s=120)
    session_id = uuid4()

    async def scenario():
        # Huỷ như Starlette khi client ngắt: cancel scope của anyio task group.
        await lease.acquire(session_id)
        async with anyio.create_task_group() as group:
            group.start_soon(lease.release, session_id)
            await anyio.sleep(0.01)
            group.cancel_scope.cancel()

    asyncio.run(scenario())

    assert store.held == set()


def test_turn_lease_release_error_is_logged_not_raised(caplog):
    class BrokenStore(FakeTurnLeaseStore):
        async def release(self, session_id):
            raise ConnectionError("db down")

    asyncio.run(SessionTurnLease(BrokenStore(), ttl_s=120).release(uuid4()))

    assert "failed to release chat turn lease" in caplog.text


# --- ChatTurnLeaseRepository: SQL thật gửi tới Postgres ------------------------------

class _RecordingDb:
    """AsyncSession giả: ghi lại câu SQL đã compile (PostgreSQL) và việc commit."""

    def __init__(self, returned_id):
        self.statements = []
        self.committed = False
        self._returned_id = returned_id

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, statement, params=None):
        from sqlalchemy.dialects import postgresql

        self.statements.append(" ".join(str(statement.compile(dialect=postgresql.dialect())).split()))
        return SimpleNamespace(scalar_one_or_none=lambda: self._returned_id)

    async def commit(self):
        self.committed = True


def _lease_repository(returned_id=None):
    from app.modules.chatbot.repositories.chat_session_repository import ChatTurnLeaseRepository

    db = _RecordingDb(returned_id)
    return ChatTurnLeaseRepository(session_factory=lambda: db), db


def test_lease_acquire_sets_lock_timeout_then_takes_lease_and_touches_activity():
    session_id = uuid4()
    repository, db = _lease_repository(returned_id=session_id)

    assert asyncio.run(repository.acquire(session_id, ttl_s=120)) is True

    lock_timeout, update = db.statements
    assert lock_timeout == "SET LOCAL lock_timeout = '3s'"
    assert update.startswith("UPDATE public.chat_sessions SET ")
    assert "turn_lease_until=(now() + " in update
    assert "last_activity_at=now()" in update
    assert ("chat_sessions.turn_lease_until IS NULL OR "
            "public.chat_sessions.turn_lease_until < now()") in update
    assert update.endswith("RETURNING public.chat_sessions.id")
    assert db.committed


def test_lease_acquire_reports_busy_when_no_row_was_updated():
    repository, db = _lease_repository(returned_id=None)

    assert asyncio.run(repository.acquire(uuid4(), ttl_s=120)) is False
    assert db.committed


def test_lease_release_sets_lock_timeout_and_clears_lease_only():
    repository, db = _lease_repository()

    asyncio.run(repository.release(uuid4()))

    lock_timeout, update = db.statements
    assert lock_timeout == "SET LOCAL lock_timeout = '3s'"
    assert update.startswith("UPDATE public.chat_sessions SET turn_lease_until=")
    assert "last_activity_at" not in update
    assert db.committed
