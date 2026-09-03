import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

VALID_PASSWORD = "StrongP@ssw0rd"


async def _register(client: AsyncClient, email: str = "user@example.com") -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": VALID_PASSWORD},
    )
    assert response.status_code == 201


async def test_register_success(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "new.user@example.com", "password": VALID_PASSWORD},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.user@example.com"
    assert body["status"] == "active"


async def test_register_duplicate_email_rejected(client: AsyncClient) -> None:
    await _register(client, "dup@example.com")
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": VALID_PASSWORD},
    )
    assert response.status_code == 409


async def test_login_success_returns_token_pair(client: AsyncClient) -> None:
    await _register(client, "login@example.com")
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": VALID_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


async def test_login_wrong_password_rejected(client: AsyncClient) -> None:
    await _register(client, "wrongpass@example.com")
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@example.com", "password": "IncorrectPass1!"},
    )
    assert response.status_code == 401


async def test_refresh_rotates_token(client: AsyncClient) -> None:
    await _register(client, "refresh@example.com")
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@example.com", "password": VALID_PASSWORD},
    )
    old_refresh_token = login_resp.json()["refresh_token"]

    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert refresh_resp.status_code == 200
    new_refresh_token = refresh_resp.json()["refresh_token"]
    assert new_refresh_token != old_refresh_token

    # Reusing the rotated-out token must now fail
    reuse_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh_token},
    )
    assert reuse_resp.status_code == 401


async def test_me_requires_valid_access_token(client: AsyncClient) -> None:
    await _register(client, "me@example.com")
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "me@example.com", "password": VALID_PASSWORD},
    )
    access_token = login_resp.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


async def test_me_rejects_missing_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code in (401, 403)
