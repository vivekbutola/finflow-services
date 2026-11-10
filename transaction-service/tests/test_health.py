import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_metrics_endpoint_exposes_transaction_metrics(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "transaction_transfer_total" in response.text
    assert "transaction_reversal_total" in response.text
    assert "wallet_service_call_total" in response.text


async def test_request_id_is_generated_and_echoed(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert "x-request-id" in response.headers


async def test_request_id_is_propagated_when_supplied(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"x-request-id": "fixed-id-123"})
    assert response.headers["x-request-id"] == "fixed-id-123"
