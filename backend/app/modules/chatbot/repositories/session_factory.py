"""Mixin dùng chung: cấp `AsyncSession` từ factory được tiêm hoặc `AsyncSessionFactory` mặc định."""

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession


class SessionFactoryMixin:
    """Repository kế thừa để có `_session()`; factory tiêm vào `__init__` (test) hoặc nạp lười khi cần."""

    _session_factory: Callable[[], AsyncSession] | None = None

    def _session(self) -> AsyncSession:
        if self._session_factory is None:
            from app.db.session import AsyncSessionFactory

            self._session_factory = AsyncSessionFactory
        return self._session_factory()
