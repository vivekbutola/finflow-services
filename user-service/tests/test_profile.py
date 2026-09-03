import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


async def test_get_my_profile_auto_provisions_on_first_access(client: AsyncClient) -> None:
    headers = auth_headers()
    response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert body["first_name"] is None


async def test_get_my_profile_is_idempotent_across_requests(client: AsyncClient) -> None:
    headers = auth_headers()
    first = await client.get("/api/v1/users/me", headers=headers)
    second = await client.get("/api/v1/users/me", headers=headers)
    assert first.json()["id"] == second.json()["id"]


async def test_update_my_profile(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.get("/api/v1/users/me", headers=headers)

    response = await client.put(
        "/api/v1/users/me",
        headers=headers,
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "phone_number": "+15551234567",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Ada"
    assert body["last_name"] == "Lovelace"
    assert body["phone_number"] == "+15551234567"


async def test_different_users_get_isolated_profiles(client: AsyncClient) -> None:
    headers_a = auth_headers()
    headers_b = auth_headers()

    response_a = await client.get("/api/v1/users/me", headers=headers_a)
    response_b = await client.get("/api/v1/users/me", headers=headers_b)

    assert response_a.json()["id"] != response_b.json()["id"]
