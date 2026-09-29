import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def _create_and_fund(client: AsyncClient, headers: dict, amount: str = "1000.00") -> None:
    await client.post("/api/v1/wallet/create", headers=headers)
    await client.post(
        "/api/v1/wallet/credit", headers=headers, json={"amount": amount, "reference_id": "SEED"}
    )


async def test_debit_wallet_success(client: AsyncClient) -> None:
    headers = auth_headers()
    await _create_and_fund(client, headers)

    response = await client.post(
        "/api/v1/wallet/debit",
        headers=headers,
        json={"amount": "400.00", "reference_id": "TRX_456"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["available_balance"] == "600.0000"
    assert body["ledger_entry"]["entry_type"] == "DEBIT"


async def test_debit_insufficient_balance_returns_400(client: AsyncClient) -> None:
    headers = auth_headers()
    await _create_and_fund(client, headers, amount="100.00")

    response = await client.post(
        "/api/v1/wallet/debit",
        headers=headers,
        json={"amount": "500.00", "reference_id": "TRX_TOO_BIG"},
    )
    assert response.status_code == 400
    assert response.json()["type"] == "https://errors.finflow.com/insufficient_balance"


async def test_debit_exact_balance_succeeds(client: AsyncClient) -> None:
    headers = auth_headers()
    await _create_and_fund(client, headers, amount="250.00")

    response = await client.post(
        "/api/v1/wallet/debit",
        headers=headers,
        json={"amount": "250.00", "reference_id": "TRX_EXACT"},
    )
    assert response.status_code == 200
    assert response.json()["available_balance"] == "0.0000"


async def test_debit_rejects_zero_amount(client: AsyncClient) -> None:
    headers = auth_headers()
    await _create_and_fund(client, headers)

    response = await client.post(
        "/api/v1/wallet/debit", headers=headers, json={"amount": "0", "reference_id": "TRX_BAD"}
    )
    assert response.status_code == 422


async def test_debit_on_closed_wallet_is_rejected(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/wallet/create", headers=headers)
    await client.post("/api/v1/wallet/close", headers=headers)

    response = await client.post(
        "/api/v1/wallet/debit", headers=headers, json={"amount": "10.00", "reference_id": "TRX_CLOSED"}
    )
    assert response.status_code == 400
    assert response.json()["type"] == "https://errors.finflow.com/wallet_closed"


async def test_debit_on_frozen_wallet_is_rejected(client: AsyncClient) -> None:
    headers = auth_headers()
    await _create_and_fund(client, headers)
    await client.post("/api/v1/wallet/freeze", headers=headers)

    response = await client.post(
        "/api/v1/wallet/debit", headers=headers, json={"amount": "10.00", "reference_id": "TRX_FROZEN"}
    )
    assert response.status_code == 400
    assert response.json()["type"] == "https://errors.finflow.com/wallet_frozen"


async def test_duplicate_debit_reference_id_is_idempotent(client: AsyncClient) -> None:
    headers = auth_headers()
    await _create_and_fund(client, headers, amount="500.00")

    first = await client.post(
        "/api/v1/wallet/debit", headers=headers, json={"amount": "200.00", "reference_id": "TRX_DUP"}
    )
    second = await client.post(
        "/api/v1/wallet/debit", headers=headers, json={"amount": "200.00", "reference_id": "TRX_DUP"}
    )
    assert first.json()["available_balance"] == second.json()["available_balance"] == "300.0000"
