import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_liveness(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness(client: AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_metrics_endpoint_exposes_prometheus_format(client: AsyncClient) -> None:
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text


async def test_request_id_is_generated_and_echoed(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert "x-request-id" in response.headers


async def test_request_id_is_propagated_when_supplied(client: AsyncClient) -> None:
    response = await client.get("/health/live", headers={"x-request-id": "fixed-id-123"})
    assert response.headers["x-request-id"] == "fixed-id-123"
