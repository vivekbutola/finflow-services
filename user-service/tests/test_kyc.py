import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio

VALID_KYC_PAYLOAD = {"pan_number": "ABCDE1234F", "aadhaar_last4": "6789"}


async def test_get_kyc_before_submission_returns_404(client: AsyncClient) -> None:
    headers = auth_headers()
    response = await client.get("/api/v1/users/me/kyc", headers=headers)
    assert response.status_code == 404
    assert response.json()["type"] == "https://errors.finflow.com/kyc_profile_not_found"


async def test_submit_kyc_success(client: AsyncClient) -> None:
    headers = auth_headers()
    response = await client.post(
        "/api/v1/users/me/kyc", headers=headers, json=VALID_KYC_PAYLOAD
    )
    assert response.status_code == 201
    body = response.json()
    assert body["kyc_status"] == "in_review"
    assert body["pan_number_masked"] == "AB******F"
    assert body["aadhaar_last4"] == "6789"


async def test_submit_kyc_twice_is_rejected(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/users/me/kyc", headers=headers, json=VALID_KYC_PAYLOAD)

    response = await client.post(
        "/api/v1/users/me/kyc", headers=headers, json=VALID_KYC_PAYLOAD
    )
    assert response.status_code == 409
    assert response.json()["type"] == "https://errors.finflow.com/kyc_already_submitted"


async def test_submit_kyc_rejects_invalid_pan_format(client: AsyncClient) -> None:
    headers = auth_headers()
    response = await client.post(
        "/api/v1/users/me/kyc",
        headers=headers,
        json={"pan_number": "invalid", "aadhaar_last4": "6789"},
    )
    assert response.status_code == 422


async def test_update_kyc_while_in_review_is_rejected(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/users/me/kyc", headers=headers, json=VALID_KYC_PAYLOAD)

    response = await client.put(
        "/api/v1/users/me/kyc",
        headers=headers,
        json={"pan_number": "ZYXWV9876Q"},
    )
    assert response.status_code == 409
    assert response.json()["type"] == "https://errors.finflow.com/kyc_immutable_state"


async def test_get_kyc_after_submission(client: AsyncClient) -> None:
    headers = auth_headers()
    await client.post("/api/v1/users/me/kyc", headers=headers, json=VALID_KYC_PAYLOAD)

    response = await client.get("/api/v1/users/me/kyc", headers=headers)
    assert response.status_code == 200
    assert response.json()["kyc_status"] == "in_review"
