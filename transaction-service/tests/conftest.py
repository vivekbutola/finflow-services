import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.exceptions import (
    InsufficientFundsError,
    WalletNotFoundError,
    WalletNotOperableError,
)
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.api.v1.dependencies import get_wallet_client

TEST_DATABASE_URL = (
    "postgresql+asyncpg://transaction_service:transaction_service_password"
    "@localhost:5432/transaction_service_test_db"
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


class FakeWalletServiceClient:
    """In-memory stand-in for wallet-service's internal debit/credit API,
    used so these tests exercise transaction-service's own orchestration,
    audit-trail, and status-machine logic without requiring a live
    wallet-service. Each test configures the wallet balances it needs and
    can force specific wallets to fail in specific ways."""

    def __init__(self) -> None:
        self.balances: dict[uuid.UUID, Decimal] = {}
        self.frozen_wallets: set[uuid.UUID] = set()
        self.missing_wallets: set[uuid.UUID] = set()
        self.calls: list[tuple[str, uuid.UUID, Decimal, str]] = []
        self.fail_credit_for: set[uuid.UUID] = set()
        # Unlike `fail_credit_for` (which exempts -COMPENSATION/-REVERSAL
        # references so the *happy* compensation/reversal path can succeed),
        # this fails a credit unconditionally -- used to simulate a
        # compensation or reversal-refund itself failing.
        self.always_fail_credit_for: set[uuid.UUID] = set()

    def seed(self, wallet_id: uuid.UUID, balance: Decimal) -> None:
        self.balances[wallet_id] = balance

    async def debit(self, wallet_id: uuid.UUID, amount: Decimal, reference_id: str) -> None:
        self.calls.append(("debit", wallet_id, amount, reference_id))
        if wallet_id in self.missing_wallets:
            raise WalletNotFoundError()
        if wallet_id in self.frozen_wallets:
            raise WalletNotOperableError()
        balance = self.balances.get(wallet_id, Decimal("0"))
        if balance < amount:
            raise InsufficientFundsError()
        self.balances[wallet_id] = balance - amount

    async def credit(self, wallet_id: uuid.UUID, amount: Decimal, reference_id: str) -> None:
        self.calls.append(("credit", wallet_id, amount, reference_id))
        if wallet_id in self.always_fail_credit_for:
            raise WalletNotOperableError("wallet cannot accept credit")
        if wallet_id in self.fail_credit_for and not reference_id.endswith(
            ("-COMPENSATION", "-REVERSAL")
        ):
            raise WalletNotOperableError("destination wallet cannot accept credit")
        if wallet_id in self.missing_wallets:
            raise WalletNotFoundError()
        self.balances[wallet_id] = self.balances.get(wallet_id, Decimal("0")) + amount


@pytest_asyncio.fixture()
async def fake_wallet_client() -> FakeWalletServiceClient:
    return FakeWalletServiceClient()


@pytest_asyncio.fixture()
async def client(
    db_session: AsyncSession, fake_wallet_client: FakeWalletServiceClient
) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db_session

    def _override_get_wallet_client():
        return fake_wallet_client

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_wallet_client] = _override_get_wallet_client

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
    transaction-service's validation logic can be tested against realistic
    tokens without depending on auth-service being deployed."""
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
