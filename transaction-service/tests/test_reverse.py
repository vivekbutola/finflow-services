"""Dedicated coverage of TransactionService.reverse_transaction(): the
reversible/not-reversible state machine, the successful reversal saga, and
both of its failure phases (claw-back from destination, refund to source)."""

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
        "amount": "300.00",
        "currency": "INR",
    }
    payload.update(overrides)
    return payload


async def _create_successful_transfer(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient, *, amount: str = "300.00"
) -> dict:
    from_wallet = uuid.uuid4()
    to_wallet = uuid.uuid4()
    fake_wallet_client.seed(from_wallet, Decimal("1000.00"))

    response = await client.post(
        "/api/v1/transactions/transfer",
        headers=auth_headers(),
        json=_transfer_payload(
            from_wallet_id=str(from_wallet), to_wallet_id=str(to_wallet), amount=amount
        ),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "SUCCESS"
    return body


# --- State machine / reversibility ------------------------------------------------


async def test_reverse_nonexistent_transaction_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/transactions/{uuid.uuid4()}/reverse", headers=auth_headers()
    )
    assert response.status_code == 404
    assert response.json()["type"] == "https://errors.finflow.com/transaction_not_found"


async def test_cannot_reverse_a_failed_transaction(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient
) -> None:
    from_wallet = uuid.uuid4()
    to_wallet = uuid.uuid4()
    fake_wallet_client.seed(from_wallet, Decimal("0.00"))  # forces insufficient funds -> FAILED

    created = await client.post(
        "/api/v1/transactions/transfer",
        headers=auth_headers(),
        json=_transfer_payload(from_wallet_id=str(from_wallet), to_wallet_id=str(to_wallet)),
    )
    assert created.json()["status"] == "FAILED"
    transaction_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/transactions/{transaction_id}/reverse", headers=auth_headers()
    )
    assert response.status_code == 409
    assert response.json()["type"] == "https://errors.finflow.com/transaction_not_reversible"


async def test_cannot_reverse_an_already_reversed_transaction(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient
) -> None:
    body = await _create_successful_transfer(client, fake_wallet_client)
    transaction_id = body["id"]

    first = await client.post(
        f"/api/v1/transactions/{transaction_id}/reverse", headers=auth_headers()
    )
    assert first.status_code == 200
    assert first.json()["status"] == "REVERSED"

    second = await client.post(
        f"/api/v1/transactions/{transaction_id}/reverse", headers=auth_headers()
    )
    assert second.status_code == 409
    assert second.json()["type"] == "https://errors.finflow.com/transaction_not_reversible"


# --- Successful reversal ----------------------------------------------------------


async def test_successful_reversal_moves_funds_back(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient
) -> None:
    body = await _create_successful_transfer(client, fake_wallet_client, amount="300.00")
    transaction_id = body["id"]
    from_wallet = uuid.UUID(body["from_wallet_id"])
    to_wallet = uuid.UUID(body["to_wallet_id"])

    fake_wallet_client.calls.clear()

    response = await client.post(
        f"/api/v1/transactions/{transaction_id}/reverse",
        headers=auth_headers(),
        json={"reason": "customer requested refund"},
    )

    assert response.status_code == 200
    reversed_body = response.json()
    assert reversed_body["status"] == "REVERSED"

    # Destination clawed back, source refunded.
    assert fake_wallet_client.balances[to_wallet] == Decimal("0.00")
    assert fake_wallet_client.balances[from_wallet] == Decimal("1000.00")

    reference_id = body["reference_id"]
    assert fake_wallet_client.calls == [
        ("debit", to_wallet, Decimal("300.00"), f"{reference_id}-REVERSAL"),
        ("credit", from_wallet, Decimal("300.00"), f"{reference_id}-REVERSAL"),
    ]


async def test_successful_reversal_audit_trail_is_complete(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient, db_session
) -> None:
    body = await _create_successful_transfer(client, fake_wallet_client)
    transaction_id = uuid.UUID(body["id"])

    await client.post(
        f"/api/v1/transactions/{transaction_id}/reverse", headers=auth_headers()
    )

    from app.repositories.audit_repository import TransactionAuditRepository

    audit_repo = TransactionAuditRepository(db_session)
    entries = await audit_repo.list_for_transaction(transaction_id)
    actions = [entry.action for entry in entries]

    assert actions == [
        "TRANSFER_INITIATED",
        "DEBIT_SUCCEEDED",
        "CREDIT_SUCCEEDED",
        "TRANSFER_COMPLETED",
        "REVERSAL_INITIATED",
        "REVERSAL_DEBIT_SUCCEEDED",
        "REVERSAL_COMPLETED",
    ]


# --- Reversal failure: phase 1 (claw-back from destination) -----------------------


async def test_reversal_fails_when_destination_wallet_cannot_be_debited(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient
) -> None:
    body = await _create_successful_transfer(client, fake_wallet_client)
    transaction_id = body["id"]
    to_wallet = uuid.UUID(body["to_wallet_id"])
    from_wallet = uuid.UUID(body["from_wallet_id"])

    # Destination wallet has since been frozen — it can still be credited to
    # (per the fake's own semantics) but debiting it for the claw-back fails.
    fake_wallet_client.frozen_wallets.add(to_wallet)

    response = await client.post(
        f"/api/v1/transactions/{transaction_id}/reverse", headers=auth_headers()
    )

    assert response.status_code == 400
    assert response.json()["type"] == "https://errors.finflow.com/reversal_failed"

    # Transaction remains SUCCESS -- reversal never got past phase 1.
    get_response = await client.get(f"/api/v1/transactions/{transaction_id}", headers=auth_headers())
    assert get_response.json()["status"] == "SUCCESS"

    # No funds moved.
    assert fake_wallet_client.balances[from_wallet] == Decimal("700.00")
    assert fake_wallet_client.balances[to_wallet] == Decimal("300.00")


# --- Reversal failure: phase 2 (refund to source) ---------------------------------


async def test_reversal_fails_when_source_wallet_cannot_be_credited(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient
) -> None:
    body = await _create_successful_transfer(client, fake_wallet_client)
    transaction_id = body["id"]
    to_wallet = uuid.UUID(body["to_wallet_id"])
    from_wallet = uuid.UUID(body["from_wallet_id"])

    # The claw-back from the destination succeeds, but refunding the
    # original source wallet fails (e.g. it was closed in the interim).
    fake_wallet_client.missing_wallets.add(from_wallet)

    response = await client.post(
        f"/api/v1/transactions/{transaction_id}/reverse", headers=auth_headers()
    )

    assert response.status_code == 400
    assert response.json()["type"] == "https://errors.finflow.com/reversal_failed"

    # Transaction is left in SUCCESS (not falsely marked REVERSED), and the
    # failure is loudly recorded for manual reconciliation since the funds
    # are now in limbo (pulled from destination, not yet returned to source).
    get_response = await client.get(f"/api/v1/transactions/{transaction_id}", headers=auth_headers())
    assert get_response.json()["status"] == "SUCCESS"

    assert fake_wallet_client.balances[to_wallet] == Decimal("0.00")
