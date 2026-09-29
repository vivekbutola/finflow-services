import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def test_freeze_wallet_success(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/wallet/create", headers=headers)

    response = await client.post("/api/v1/wallet/freeze", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "FROZEN"


async def test_unfreeze_wallet_success(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/wallet/create", headers=headers)
    await client.post("/api/v1/wallet/freeze", headers=headers)

    response = await client.post("/api/v1/wallet/unfreeze", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"


async def test_unfreeze_already_active_wallet_is_rejected(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/wallet/create", headers=headers)

    response = await client.post("/api/v1/wallet/unfreeze", headers=headers)
    assert response.status_code == 400
    assert response.json()["type"] == "https://errors.finflow.com/wallet_not_frozen"


async def test_close_wallet_with_zero_balance_succeeds(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/wallet/create", headers=headers)

    response = await client.post("/api/v1/wallet/close", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "CLOSED"


async def test_close_wallet_with_nonzero_balance_is_rejected(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/wallet/create", headers=headers)
    await client.post(
        "/api/v1/wallet/credit", headers=headers, json={"amount": "50.00", "reference_id": "SEED"}
    )

    response = await client.post("/api/v1/wallet/close", headers=headers)
    assert response.status_code == 400
    assert response.json()["type"] == "https://errors.finflow.com/wallet_balance_not_zero"


async def test_frozen_wallet_cannot_be_closed(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/wallet/create", headers=headers)
    await client.post("/api/v1/wallet/freeze", headers=headers)

    response = await client.post("/api/v1/wallet/close", headers=headers)
    assert response.status_code == 400
    assert response.json()["type"] == "https://errors.finflow.com/wallet_frozen"


async def test_closed_wallet_rejects_freeze(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/wallet/create", headers=headers)
    await client.post("/api/v1/wallet/close", headers=headers)

    response = await client.post("/api/v1/wallet/freeze", headers=headers)
    assert response.status_code == 400
    assert response.json()["type"] == "https://errors.finflow.com/wallet_closed"
