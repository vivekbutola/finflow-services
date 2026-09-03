import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio


def _address_payload(**overrides) -> dict:
    payload = {
        "address_type": "residential",
        "line1": "1 Infinite Loop",
        "line2": None,
        "city": "Cupertino",
        "state": "CA",
        "country": "us",
        "postal_code": "95014",
        "is_default": False,
    }
    payload.update(overrides)
    return payload


async def test_create_first_address_is_forced_default(client: AsyncClient) -> None:
    headers = auth_headers()
    response = await client.post(
        "/api/v1/users/me/addresses", headers=headers, json=_address_payload()
    )
    assert response.status_code == 201
    body = response.json()
    assert body["is_default"] is True
    assert body["country"] == "US"  # normalized to uppercase


async def test_list_addresses(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/users/me/addresses", headers=headers, json=_address_payload())
    await client.post(
        "/api/v1/users/me/addresses",
        headers=headers,
        json=_address_payload(line1="2 Main St", address_type="billing"),
    )

    response = await client.get("/api/v1/users/me/addresses", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_setting_new_default_unsets_previous_default(client: AsyncClient) -> None:
    headers = auth_headers()
    first = await client.post(
        "/api/v1/users/me/addresses", headers=headers, json=_address_payload()
    )
    second = await client.post(
        "/api/v1/users/me/addresses",
        headers=headers,
        json=_address_payload(line1="2 Main St", is_default=True),
    )
    assert second.json()["is_default"] is True

    refreshed_first = await client.put(
        f"/api/v1/users/me/addresses/{first.json()['id']}",
        headers=headers,
        json={},
    )
    assert refreshed_first.json()["is_default"] is False


async def test_delete_address_promotes_another_to_default(client: AsyncClient) -> None:
    headers = auth_headers()
    first = await client.post(
        "/api/v1/users/me/addresses", headers=headers, json=_address_payload()
    )
    second = await client.post(
        "/api/v1/users/me/addresses",
        headers=headers,
        json=_address_payload(line1="2 Main St"),
    )

    delete_response = await client.delete(
        f"/api/v1/users/me/addresses/{first.json()['id']}", headers=headers
    )
    assert delete_response.status_code == 204

    remaining = await client.get("/api/v1/users/me/addresses", headers=headers)
    remaining_addresses = remaining.json()
    assert len(remaining_addresses) == 1
    assert remaining_addresses[0]["id"] == second.json()["id"]
    assert remaining_addresses[0]["is_default"] is True


async def test_update_nonexistent_address_returns_404(client: AsyncClient) -> None:
    headers = auth_headers()
    response = await client.put(
        "/api/v1/users/me/addresses/00000000-0000-0000-0000-000000000000",
        headers=headers,
        json={"city": "Nowhere"},
    )
    assert response.status_code == 404


async def test_cannot_access_another_users_address(client: AsyncClient) -> None:
    owner_headers = auth_headers()
    other_headers = auth_headers()

    created = await client.post(
        "/api/v1/users/me/addresses", headers=owner_headers, json=_address_payload()
    )
    address_id = created.json()["id"]

    response = await client.delete(
        f"/api/v1/users/me/addresses/{address_id}", headers=other_headers
    )
    assert response.status_code == 404
