import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = (
    "postgresql+asyncpg://user_service:user_service_password@localhost:5432/user_service_test_db"
)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


def make_access_token(
    auth_user_id: uuid.UUID | None = None,
    *,
    expired: bool = False,
    issuer: str | None = None,
    audience: str | None = None,
    token_type: str = "access",
) -> str:
    """Builds a JWT shaped exactly like the ones auth-service issues, so
    user-service's validation logic can be tested against realistic tokens
    without depending on auth-service being deployed."""
    now = datetime.now(timezone.utc)
    exp = now - timedelta(minutes=5) if expired else now + timedelta(minutes=15)

    payload = {
        "sub": str(auth_user_id or uuid.uuid4()),
        "type": token_type,
        "iat": now,
        "exp": exp,
        "nbf": now,
        "jti": str(uuid.uuid4()),
        "iss": issuer or settings.JWT_ISSUER,
        "aud": audience or settings.JWT_AUDIENCE,
        "status": "active",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def auth_headers(auth_user_id: uuid.UUID | None = None, **kwargs) -> dict[str, str]:
    token = make_access_token(auth_user_id, **kwargs)
    return {"Authorization": f"Bearer {token}"}
