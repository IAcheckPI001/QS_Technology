

# app/infrastructure/database/engine.py

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_db_settings


settings = get_db_settings()


def create_engine() -> AsyncEngine:
    kwargs = {
        "echo": settings.database_echo,
        "pool_pre_ping": True,
    }

    if settings.database_pool_mode == "transaction":
        # Supabase Transaction Pooler :6543
        kwargs["poolclass"] = NullPool
    else:
        # Direct hoặc Session Pooler :5432
        kwargs.update(
            {
                "pool_size": settings.database_pool_size,
                "max_overflow": settings.database_max_overflow,
                "pool_recycle": settings.database_pool_recycle,
            }
        )

    return create_async_engine(
        settings.database_url,
        **kwargs,
    )


engine: AsyncEngine = create_engine()

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)