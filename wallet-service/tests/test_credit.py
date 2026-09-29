import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def test_credit_wallet_success(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/wallet/create", headers=headers)

    response = await client.post(
        "/api/v1/wallet/credit",
        headers=headers,
        json={"amount": "1000.00", "reference_id": "PAY_123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["available_balance"] == "1000.0000"
    assert body["ledger_entry"]["entry_type"] == "CREDIT"
    assert body["ledger_entry"]["balance_before"] == "0.0000"
    assert body["ledger_entry"]["balance_after"] == "1000.0000"


async def test_credit_accumulates_balance(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/wallet/create", headers=headers)

    await client.post(
        "/api/v1/wallet/credit", headers=headers, json={"amount": "500.00", "reference_id": "PAY_1"}
    )
    response = await client.post(
        "/api/v1/wallet/credit", headers=headers, json={"amount": "250.50", "reference_id": "PAY_2"}
    )
    assert response.json()["available_balance"] == "750.5000"


async def test_credit_rejects_zero_amount(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/wallet/create", headers=headers)

    response = await client.post(
        "/api/v1/wallet/credit", headers=headers, json={"amount": "0", "reference_id": "PAY_BAD"}
    )
    assert response.status_code == 422


async def test_credit_rejects_negative_amount(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/wallet/create", headers=headers)

    response = await client.post(
        "/api/v1/wallet/credit", headers=headers, json={"amount": "-100", "reference_id": "PAY_NEG"}
    )
    assert response.status_code == 422


async def test_credit_without_wallet_returns_404(client: AsyncClient) -> None:
    headers = auth_headers()
    response = await client.post(
        "/api/v1/wallet/credit", headers=headers, json={"amount": "100.00", "reference_id": "PAY_X"}
    )
    assert response.status_code == 404


async def test_credit_on_frozen_wallet_is_rejected(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/wallet/create", headers=headers)
    await client.post("/api/v1/wallet/freeze", headers=headers)

    response = await client.post(
        "/api/v1/wallet/credit", headers=headers, json={"amount": "100.00", "reference_id": "PAY_FROZEN"}
    )
    assert response.status_code == 400
    assert response.json()["type"] == "https://errors.finflow.com/wallet_frozen"


async def test_duplicate_reference_id_is_idempotent(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/wallet/create", headers=headers)

    first = await client.post(
        "/api/v1/wallet/credit", headers=headers, json={"amount": "100.00", "reference_id": "PAY_DUP"}
    )
    second = await client.post(
        "/api/v1/wallet/credit", headers=headers, json={"amount": "100.00", "reference_id": "PAY_DUP"}
    )
    assert first.status_code == 200
    assert second.status_code == 200
    # Balance must NOT be credited twice for the same reference_id
    assert second.json()["available_balance"] == first.json()["available_balance"] == "100.0000"
