import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from tests.conftest import FakeWalletServiceClient, auth_headers

pytestmark = pytest.mark.asyncio


def _transfer_payload(**overrides) -> dict:
    payload = {
        "reference_id": str(uuid.uuid4()),
        "from_wallet_id": str(uuid.uuid4()),
        "to_wallet_id": str(uuid.uuid4()),
        "amount": "100.00",
        "currency": "INR",
    }
    payload.update(overrides)
    return payload


# --- JWT validation ----------------------------------------------------------


async def test_transfer_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/v1/transactions/transfer", json=_transfer_payload())
    assert response.status_code in (401, 403)


async def test_rejects_expired_token(client: AsyncClient) -> None:
    headers = auth_headers(expired=True)
    response = await client.post(
        "/api/v1/transactions/transfer", headers=headers, json=_transfer_payload()
    )
    assert response.status_code == 401
    assert response.json()["type"] == "https://errors.finflow.com/token_expired"


async def test_rejects_wrong_issuer(client: AsyncClient) -> None:
    headers = auth_headers(issuer="not-auth-service")
    response = await client.post(
        "/api/v1/transactions/transfer", headers=headers, json=_transfer_payload()
    )
    assert response.status_code == 401


async def test_rejects_wrong_audience(client: AsyncClient) -> None:
    headers = auth_headers(audience="some-other-platform")
    response = await client.post(
        "/api/v1/transactions/transfer", headers=headers, json=_transfer_payload()
    )
    assert response.status_code == 401


async def test_rejects_non_access_token(client: AsyncClient) -> None:
    headers = auth_headers(token_type="refresh")
    response = await client.post(
        "/api/v1/transactions/transfer", headers=headers, json=_transfer_payload()
    )
    assert response.status_code == 401


async def test_error_response_shape_matches_problem_details(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/transactions/transfer",
        headers={"Authorization": "Bearer garbage"},
        json=_transfer_payload(),
    )
    body = response.json()
    assert set(body.keys()) == {"type", "title", "status", "detail", "trace_id"}


# --- Transfer request validation ---------------------------------------------


async def test_transfer_rejects_zero_amount(client: AsyncClient) -> None:
    headers = auth_headers()
    response = await client.post(
        "/api/v1/transactions/transfer", headers=headers, json=_transfer_payload(amount="0")
    )
    assert response.status_code == 422


async def test_transfer_rejects_negative_amount(client: AsyncClient) -> None:
    headers = auth_headers()
    response = await client.post(
        "/api/v1/transactions/transfer", headers=headers, json=_transfer_payload(amount="-10")
    )
    assert response.status_code == 422


async def test_transfer_rejects_same_wallet(client: AsyncClient) -> None:
    headers = auth_headers()
    wallet_id = str(uuid.uuid4())
    response = await client.post(
        "/api/v1/transactions/transfer",
        headers=headers,
        json=_transfer_payload(from_wallet_id=wallet_id, to_wallet_id=wallet_id),
    )
    assert response.status_code == 422


async def test_transfer_rejects_invalid_currency(client: AsyncClient) -> None:
    headers = auth_headers()
    response = await client.post(
        "/api/v1/transactions/transfer", headers=headers, json=_transfer_payload(currency="XXX")
    )
    assert response.status_code == 422


async def test_transfer_rejects_duplicate_reference_id(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient
) -> None:
    from_wallet = uuid.uuid4()
    to_wallet = uuid.uuid4()
    fake_wallet_client.seed(from_wallet, Decimal("1000.00"))

    headers = auth_headers()
    reference_id = str(uuid.uuid4())
    payload = _transfer_payload(
        reference_id=reference_id, from_wallet_id=str(from_wallet), to_wallet_id=str(to_wallet)
    )

    first = await client.post("/api/v1/transactions/transfer", headers=headers, json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/transactions/transfer", headers=headers, json=payload)
    assert second.status_code == 409
    assert second.json()["type"] == "https://errors.finflow.com/duplicate_transaction_reference"


# --- Get / list ----------------------------------------------------------------


async def test_get_nonexistent_transaction_returns_404(client: AsyncClient) -> None:
    headers = auth_headers()
    response = await client.get(
        f"/api/v1/transactions/{uuid.uuid4()}", headers=headers
    )
    assert response.status_code == 404
    assert response.json()["type"] == "https://errors.finflow.com/transaction_not_found"


async def test_get_transaction_after_transfer(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient
) -> None:
    from_wallet = uuid.uuid4()
    to_wallet = uuid.uuid4()
    fake_wallet_client.seed(from_wallet, Decimal("500.00"))

    headers = auth_headers()
    created = await client.post(
        "/api/v1/transactions/transfer",
        headers=headers,
        json=_transfer_payload(from_wallet_id=str(from_wallet), to_wallet_id=str(to_wallet)),
    )
    transaction_id = created.json()["id"]

    response = await client.get(f"/api/v1/transactions/{transaction_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == transaction_id


async def test_list_transactions(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient
) -> None:
    headers = auth_headers()
    for _ in range(3):
        from_wallet = uuid.uuid4()
        to_wallet = uuid.uuid4()
        fake_wallet_client.seed(from_wallet, Decimal("1000.00"))
        await client.post(
            "/api/v1/transactions/transfer",
            headers=headers,
            json=_transfer_payload(from_wallet_id=str(from_wallet), to_wallet_id=str(to_wallet)),
        )

    response = await client.get("/api/v1/transactions", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert body["page"] == 1
    assert body["page_size"] == 20


async def test_list_transactions_filters_by_status(
    client: AsyncClient, fake_wallet_client: FakeWalletServiceClient
) -> None:
    headers = auth_headers()

    success_from = uuid.uuid4()
    success_to = uuid.uuid4()
    fake_wallet_client.seed(success_from, Decimal("1000.00"))
    await client.post(
        "/api/v1/transactions/transfer",
        headers=headers,
        json=_transfer_payload(from_wallet_id=str(success_from), to_wallet_id=str(success_to)),
    )

    failed_from = uuid.uuid4()
    failed_to = uuid.uuid4()
    fake_wallet_client.seed(failed_from, Decimal("0.00"))  # insufficient funds
    await client.post(
        "/api/v1/transactions/transfer",
        headers=headers,
        json=_transfer_payload(from_wallet_id=str(failed_from), to_wallet_id=str(failed_to)),
    )

    response = await client.get("/api/v1/transactions?status=SUCCESS", headers=headers)
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "SUCCESS"
