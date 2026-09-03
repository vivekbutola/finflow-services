import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def test_me_rejects_missing_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")
    assert response.status_code in (401, 403)


async def test_me_rejects_malformed_token(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
    body = response.json()
    assert body["type"] == "https://errors.finflow.com/invalid_token"
    assert "trace_id" in body


async def test_me_rejects_expired_token(client: AsyncClient) -> None:
    headers = auth_headers(expired=True)
    response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["type"] == "https://errors.finflow.com/token_expired"


async def test_me_rejects_wrong_issuer(client: AsyncClient) -> None:
    headers = auth_headers(issuer="some-other-service")
    response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 401


async def test_me_rejects_wrong_audience(client: AsyncClient) -> None:
    headers = auth_headers(audience="some-other-platform")
    response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 401


async def test_me_rejects_non_access_token_type(client: AsyncClient) -> None:
    headers = auth_headers(token_type="refresh")
    response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 401


async def test_me_accepts_valid_token(client: AsyncClient) -> None:
    headers = auth_headers()
    response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200


async def test_error_response_shape_matches_problem_details(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer garbage"}
    )
    body = response.json()
    assert set(body.keys()) == {"type", "title", "status", "detail", "trace_id"}
