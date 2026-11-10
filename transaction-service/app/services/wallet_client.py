import uuid
from decimal import Decimal
from typing import Literal

import httpx

from app.core.config import settings
from app.core.exceptions import (
    InsufficientFundsError,
    WalletNotFoundError,
    WalletNotOperableError,
    WalletServiceUnavailableError,
)
from app.core.logging import get_logger
from app.core.metrics import wallet_service_call_total

logger = get_logger(__name__)

_ERROR_TYPE_MAP: dict[str, type[Exception]] = {
    "wallet_not_found": WalletNotFoundError,
    "wallet_frozen": WalletNotOperableError,
    "wallet_closed": WalletNotOperableError,
    "insufficient_balance": InsufficientFundsError,
}


class WalletServiceClient:
    """HTTP client for the internal, service-to-service wallet-service API.

    This is a deliberately distinct surface from wallet-service's public
    `/api/v1/wallet/*` endpoints, which resolve "the wallet" from the
    caller's own JWT `sub` claim and therefore cannot debit or credit an
    arbitrary `wallet_id` on behalf of two different users in the same
    transfer. Moving money between two wallets requires wallet-service to
    expose an internal endpoint set keyed by `wallet_id` and authenticated
    with a shared service secret instead of a user token:

        POST {WALLET_SERVICE_BASE_URL}/internal/v1/wallets/{wallet_id}/debit
        POST {WALLET_SERVICE_BASE_URL}/internal/v1/wallets/{wallet_id}/credit
        Headers: {"X-Internal-Api-Key": <shared secret>}
        Body:    {"amount": "100.00", "reference_id": "<idempotency key>"}

    This client is written against that contract. `reference_id` is always
    passed through so wallet-service's own ledger idempotency (unique
    `(wallet_id, reference_id)`) makes every call here safe to retry.
    """

    def __init__(self) -> None:
        self._base_url = settings.WALLET_SERVICE_BASE_URL
        self._api_key = settings.WALLET_SERVICE_INTERNAL_API_KEY
        self._timeout = settings.WALLET_SERVICE_TIMEOUT_SECONDS

    async def debit(self, wallet_id: uuid.UUID, amount: Decimal, reference_id: str) -> None:
        await self._call("debit", wallet_id, amount, reference_id)

    async def credit(self, wallet_id: uuid.UUID, amount: Decimal, reference_id: str) -> None:
        await self._call("credit", wallet_id, amount, reference_id)

    async def _call(
        self,
        operation: Literal["debit", "credit"],
        wallet_id: uuid.UUID,
        amount: Decimal,
        reference_id: str,
    ) -> None:
        url = f"{self._base_url}/internal/v1/wallets/{wallet_id}/{operation}"
        payload = {"amount": str(amount), "reference_id": reference_id}
        headers = {"X-Internal-Api-Key": self._api_key}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            wallet_service_call_total.labels(operation=operation, outcome="timeout").inc()
            logger.error(
                "wallet_service_call_timeout",
                extra={"operation": operation, "wallet_id": str(wallet_id), "reference_id": reference_id},
            )
            raise WalletServiceUnavailableError(
                f"wallet-service timed out during {operation}"
            ) from exc
        except httpx.HTTPError as exc:
            wallet_service_call_total.labels(operation=operation, outcome="connection_error").inc()
            logger.error(
                "wallet_service_call_connection_error",
                extra={"operation": operation, "wallet_id": str(wallet_id), "reference_id": reference_id},
            )
            raise WalletServiceUnavailableError(
                f"wallet-service could not be reached during {operation}"
            ) from exc

        if response.status_code < 300:
            wallet_service_call_total.labels(operation=operation, outcome="success").inc()
            return

        error_type = "unknown_error"
        try:
            body = response.json()
            error_type = body.get("type", "").rsplit("/", 1)[-1] or "unknown_error"
        except ValueError:
            pass

        wallet_service_call_total.labels(operation=operation, outcome=error_type).inc()
        logger.warning(
            "wallet_service_call_failed",
            extra={
                "operation": operation,
                "wallet_id": str(wallet_id),
                "reference_id": reference_id,
                "status_code": response.status_code,
                "error_type": error_type,
            },
        )

        exception_cls = _ERROR_TYPE_MAP.get(error_type, WalletServiceUnavailableError)
        raise exception_cls(
            f"wallet-service rejected {operation} for wallet {wallet_id}: {error_type}"
        )
