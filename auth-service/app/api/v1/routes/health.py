from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe (checks DB connectivity)")
async def readiness(session: AsyncSession = Depends(get_db)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready"}
