import asyncio
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.exceptions import WalletAlreadyExistsError
from app.services.wallet_service import WalletService
from tests.conftest import TEST_DATABASE_URL, auth_headers

pytestmark = pytest.mark.asyncio


async def test_get_wallet_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/wallet")
    assert response.status_code in (401, 403)


async def test_get_wallet_rejects_expired_token(client: AsyncClient) -> None:
    headers = auth_headers(expired=True)
    response = await client.get("/api/v1/wallet", headers=headers)
    assert response.status_code == 401
    assert response.json()["type"] == "https://errors.finflow.com/token_expired"


async def test_get_wallet_rejects_wrong_issuer(client: AsyncClient) -> None:
    headers = auth_headers(issuer="not-auth-service")
    response = await client.get("/api/v1/wallet", headers=headers)
    assert response.status_code == 401


async def test_get_wallet_rejects_non_access_token(client: AsyncClient) -> None:
    headers = auth_headers(token_type="refresh")
    response = await client.get("/api/v1/wallet", headers=headers)
    assert response.status_code == 401


async def test_get_wallet_before_creation_returns_404(client: AsyncClient) -> None:
    headers = auth_headers()
    response = await client.get("/api/v1/wallet", headers=headers)
    assert response.status_code == 404
    assert response.json()["type"] == "https://errors.finflow.com/wallet_not_found"


async def test_create_wallet_success(client: AsyncClient) -> None:
    headers = auth_headers()
    response = await client.post("/api/v1/wallet/create", headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["available_balance"] == "0.0000"
    assert body["currency"] == "INR"
    assert body["status"] == "ACTIVE"
    assert body["wallet_id"].startswith("WAL-")


async def test_create_wallet_twice_is_rejected(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/wallet/create", headers=headers)

    response = await client.post("/api/v1/wallet/create", headers=headers)
    assert response.status_code == 409
    assert response.json()["type"] == "https://errors.finflow.com/wallet_already_exists"


async def test_get_wallet_after_creation(client: AsyncClient) -> None:
    headers = auth_headers()
    created = await client.post("/api/v1/wallet/create", headers=headers)

    response = await client.get("/api/v1/wallet", headers=headers)
    assert response.status_code == 200
    assert response.json()["wallet_id"] == created.json()["wallet_id"]


async def test_wallets_are_isolated_per_user(client: AsyncClient) -> None:
    headers_a = auth_headers()
    headers_b = auth_headers()

    created_a = await client.post("/api/v1/wallet/create", headers=headers_a)
    created_b = await client.post("/api/v1/wallet/create", headers=headers_b)

    assert created_a.json()["wallet_id"] != created_b.json()["wallet_id"]


async def test_concurrent_wallet_creation_is_race_safe() -> None:
    """Regression test: two concurrent create_wallet calls for the same
    user, on two independent DB connections, must result in exactly one
    successful wallet and one clean WalletAlreadyExistsError — never an
    unhandled IntegrityError. This exercises the real Postgres unique
    constraint, not just the application-level pre-check, since the
    shared single-session `client` fixture can't reproduce a true
    cross-connection race."""
    user_id = uuid.uuid4()

    from app.db.base import Base

    engine_a = create_async_engine(TEST_DATABASE_URL)
    engine_b = create_async_engine(TEST_DATABASE_URL)
    session_factory_a = async_sessionmaker(bind=engine_a, expire_on_commit=False)
    session_factory_b = async_sessionmaker(bind=engine_b, expire_on_commit=False)

    async with engine_a.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        async with session_factory_a() as session_a, session_factory_b() as session_b:
            service_a = WalletService(session_a)
            service_b = WalletService(session_b)

            results = await asyncio.gather(
                service_a.create_wallet(user_id),
                service_b.create_wallet(user_id),
                return_exceptions=True,
            )

        successes = [r for r in results if not isinstance(r, BaseException)]
        failures = [r for r in results if isinstance(r, BaseException)]

        assert len(successes) == 1, f"expected exactly one winner, got {results}"
        assert len(failures) == 1
        assert isinstance(failures[0], WalletAlreadyExistsError)
    finally:
        async with engine_a.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine_a.dispose()
        await engine_b.dispose()
