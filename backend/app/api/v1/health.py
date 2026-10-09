from fastapi import APIRouter, Depends

from app.db.session import get_db_session
from app.db.health import check_database
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
async def database_health(
    db: AsyncSession = Depends(get_db_session),
):
    ok = await check_database(db)

    return {
        "database": "ok" if ok else "error"
    }
