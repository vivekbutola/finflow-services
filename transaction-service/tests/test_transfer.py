"""Dedicated coverage of TransactionService.transfer_funds()'s two-phase
saga behavior: the happy path, a debit-phase failure (insufficient funds),
and a credit-phase failure that must trigger compensation (refunding the
already-debited source wallet)."""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from tests.conftest import FakeWalletServiceClient, auth_headers

pytestmark = pytest.mark.asyncio


def _transfer_payload(**overrides) -> dict:
    payload = {
        "reference_id": str(uuid.uuid4()),
        "from_wallet_id": str(uuid.uuid4()),
        "to_wallet_id": str(uuid.uuid4()),
        "amount": "250.00",
        "currency": "INR",
    }
    payload.update(overrides)
    return payload


# --- Happy path ----------------------------------------------------------------


async def test_successful_transfer_debits_and_credits_wallets(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient
) -> None:
    from_wallet = uuid.uuid4()
    to_wallet = uuid.uuid4()
    fake_wallet_client.seed(from_wallet, Decimal("1000.00"))

    reference_id = str(uuid.uuid4())
    response = await client.post(
        "/api/v1/transactions/transfer",
        headers=auth_headers(),
        json=_transfer_payload(
            reference_id=reference_id,
            from_wallet_id=str(from_wallet),
            to_wallet_id=str(to_wallet),
            amount="250.00",
        ),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "SUCCESS"
    assert body["failure_reason"] is None
    assert Decimal(body["amount"]) == Decimal("250.00")

    # Wallet balances actually moved.
    assert fake_wallet_client.balances[from_wallet] == Decimal("750.00")
    assert fake_wallet_client.balances[to_wallet] == Decimal("250.00")

    # Debit happened before credit, both using the caller-supplied reference_id.
    assert fake_wallet_client.calls == [
        ("debit", from_wallet, Decimal("250.00"), reference_id),
        ("credit", to_wallet, Decimal("250.00"), reference_id),
    ]


async def test_successful_transfer_audit_trail_is_complete(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient, db_session
) -> None:
    from_wallet = uuid.uuid4()
    to_wallet = uuid.uuid4()
    fake_wallet_client.seed(from_wallet, Decimal("500.00"))

    created = await client.post(
        "/api/v1/transactions/transfer",
        headers=auth_headers(),
        json=_transfer_payload(from_wallet_id=str(from_wallet), to_wallet_id=str(to_wallet)),
    )
    transaction_id = uuid.UUID(created.json()["id"])

    from app.repositories.audit_repository import TransactionAuditRepository

    audit_repo = TransactionAuditRepository(db_session)
    entries = await audit_repo.list_for_transaction(transaction_id)
    actions = [entry.action for entry in entries]

    assert actions == [
        "TRANSFER_INITIATED",
        "DEBIT_SUCCEEDED",
        "CREDIT_SUCCEEDED",
        "TRANSFER_COMPLETED",
    ]


# --- Debit-phase failure ---------------------------------------------------------


async def test_transfer_fails_when_source_has_insufficient_funds(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient
) -> None:
    from_wallet = uuid.uuid4()
    to_wallet = uuid.uuid4()
    fake_wallet_client.seed(from_wallet, Decimal("10.00"))

    response = await client.post(
        "/api/v1/transactions/transfer",
        headers=auth_headers(),
        json=_transfer_payload(
            from_wallet_id=str(from_wallet), to_wallet_id=str(to_wallet), amount="500.00"
        ),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["failure_reason"] is not None

    # No credit was ever attempted, and the source balance is untouched.
    assert ("credit", to_wallet, Decimal("500.00")) not in [
        (c[0], c[1], c[2]) for c in fake_wallet_client.calls
    ]
    assert fake_wallet_client.balances[from_wallet] == Decimal("10.00")


async def test_transfer_fails_when_source_wallet_is_frozen(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient
) -> None:
    from_wallet = uuid.uuid4()
    to_wallet = uuid.uuid4()
    fake_wallet_client.seed(from_wallet, Decimal("1000.00"))
    fake_wallet_client.frozen_wallets.add(from_wallet)

    response = await client.post(
        "/api/v1/transactions/transfer",
        headers=auth_headers(),
        json=_transfer_payload(from_wallet_id=str(from_wallet), to_wallet_id=str(to_wallet)),
    )

    assert response.status_code == 201
    assert response.json()["status"] == "FAILED"


async def test_transfer_fails_when_source_wallet_missing(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient
) -> None:
    from_wallet = uuid.uuid4()
    to_wallet = uuid.uuid4()
    fake_wallet_client.missing_wallets.add(from_wallet)

    response = await client.post(
        "/api/v1/transactions/transfer",
        headers=auth_headers(),
        json=_transfer_payload(from_wallet_id=str(from_wallet), to_wallet_id=str(to_wallet)),
    )

    assert response.status_code == 201
    assert response.json()["status"] == "FAILED"


# --- Credit-phase failure triggers compensation -----------------------------------


async def test_transfer_compensates_source_wallet_when_credit_fails(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient
) -> None:
    from_wallet = uuid.uuid4()
    to_wallet = uuid.uuid4()
    fake_wallet_client.seed(from_wallet, Decimal("1000.00"))
    fake_wallet_client.fail_credit_for.add(to_wallet)

    reference_id = str(uuid.uuid4())
    response = await client.post(
        "/api/v1/transactions/transfer",
        headers=auth_headers(),
        json=_transfer_payload(
            reference_id=reference_id,
            from_wallet_id=str(from_wallet),
            to_wallet_id=str(to_wallet),
            amount="250.00",
        ),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "FAILED"
    assert "compensated" in body["failure_reason"]

    # Source wallet was debited, then refunded back to its original balance.
    assert fake_wallet_client.balances[from_wallet] == Decimal("1000.00")
    # Destination wallet never actually received the funds.
    assert fake_wallet_client.balances.get(to_wallet, Decimal("0")) == Decimal("0")

    assert fake_wallet_client.calls == [
        ("debit", from_wallet, Decimal("250.00"), reference_id),
        ("credit", to_wallet, Decimal("250.00"), reference_id),
        ("credit", from_wallet, Decimal("250.00"), f"{reference_id}-COMPENSATION"),
    ]


async def test_transfer_compensation_failure_is_recorded(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient, db_session
) -> None:
    from_wallet = uuid.uuid4()
    to_wallet = uuid.uuid4()
    fake_wallet_client.seed(from_wallet, Decimal("1000.00"))
    fake_wallet_client.fail_credit_for.add(to_wallet)
    # The debit succeeds and the destination credit fails as usual, entering
    # the compensation branch -- but this time the compensating credit back
    # to the source wallet *also* fails unconditionally, which must be
    # recorded as a compensation failure rather than silently retried.
    fake_wallet_client.always_fail_credit_for.add(from_wallet)

    created = await client.post(
        "/api/v1/transactions/transfer",
        headers=auth_headers(),
        json=_transfer_payload(from_wallet_id=str(from_wallet), to_wallet_id=str(to_wallet)),
    )

    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "FAILED"
    assert "compensation_failed" in body["failure_reason"]

    from app.repositories.audit_repository import TransactionAuditRepository

    audit_repo = TransactionAuditRepository(db_session)
    entries = await audit_repo.list_for_transaction(uuid.UUID(body["id"]))
    actions = [entry.action for entry in entries]
    assert "COMPENSATION_FAILED" in actions
    assert "TRANSFER_FAILED" in actions


# --- Concurrency / idempotency ---------------------------------------------------


async def test_duplicate_reference_id_does_not_double_move_funds(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient
) -> None:
    from_wallet = uuid.uuid4()
    to_wallet = uuid.uuid4()
    fake_wallet_client.seed(from_wallet, Decimal("1000.00"))

    reference_id = str(uuid.uuid4())
    payload = _transfer_payload(
        reference_id=reference_id,
        from_wallet_id=str(from_wallet),
        to_wallet_id=str(to_wallet),
        amount="100.00",
    )

    first = await client.post("/api/v1/transactions/transfer", headers=auth_headers(), json=payload)
    assert first.status_code == 201
    assert fake_wallet_client.balances[from_wallet] == Decimal("900.00")

    second = await client.post("/api/v1/transactions/transfer", headers=auth_headers(), json=payload)
    assert second.status_code == 409

    # Balance unaffected by the rejected duplicate.
    assert fake_wallet_client.balances[from_wallet] == Decimal("900.00")
