

# app/infrastructure/database/session.py

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from .engine import AsyncSessionFactory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise