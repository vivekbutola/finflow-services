import uuid

from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import get_current_auth_user_id, get_wallet_service
from app.schemas.wallet import (
    WalletBalanceOperationResponse,
    WalletCreditRequest,
    WalletDebitRequest,
    WalletLedgerEntryResponse,
    WalletResponse,
)
from app.services.wallet_service import WalletService

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("", response_model=WalletResponse, summary="Get the current user's wallet")
async def get_wallet(
    user_id: uuid.UUID = Depends(get_current_auth_user_id),
    wallet_service: WalletService = Depends(get_wallet_service),
) -> WalletResponse:
    wallet = await wallet_service.get_wallet(user_id)
    return WalletResponse.from_model(wallet)


@router.post(
    "/create",
    response_model=WalletResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a wallet for the current user (one per user)",
)
async def create_wallet(
    user_id: uuid.UUID = Depends(get_current_auth_user_id),
    wallet_service: WalletService = Depends(get_wallet_service),
) -> WalletResponse:
    wallet = await wallet_service.create_wallet(user_id)
    return WalletResponse.from_model(wallet)


@router.post(
    "/credit",
    response_model=WalletBalanceOperationResponse,
    summary="Credit funds into the current user's wallet",
)
async def credit_wallet(
    payload: WalletCreditRequest,
    user_id: uuid.UUID = Depends(get_current_auth_user_id),
    wallet_service: WalletService = Depends(get_wallet_service),
) -> WalletBalanceOperationResponse:
    wallet, entry = await wallet_service.credit(
        user_id, amount=payload.amount, reference_id=payload.reference_id
    )
    return WalletBalanceOperationResponse(
        wallet_id=wallet.wallet_id,
        available_balance=wallet.balance,
        currency=wallet.currency,
        status=wallet.status,
        ledger_entry=WalletLedgerEntryResponse.model_validate(entry),
    )


@router.post(
    "/debit",
    response_model=WalletBalanceOperationResponse,
    summary="Debit funds from the current user's wallet",
)
async def debit_wallet(
    payload: WalletDebitRequest,
    user_id: uuid.UUID = Depends(get_current_auth_user_id),
    wallet_service: WalletService = Depends(get_wallet_service),
) -> WalletBalanceOperationResponse:
    wallet, entry = await wallet_service.debit(
        user_id, amount=payload.amount, reference_id=payload.reference_id
    )
    return WalletBalanceOperationResponse(
        wallet_id=wallet.wallet_id,
        available_balance=wallet.balance,
        currency=wallet.currency,
        status=wallet.status,
        ledger_entry=WalletLedgerEntryResponse.model_validate(entry),
    )


@router.post("/freeze", response_model=WalletResponse, summary="Freeze the current user's wallet")
async def freeze_wallet(
    user_id: uuid.UUID = Depends(get_current_auth_user_id),
    wallet_service: WalletService = Depends(get_wallet_service),
) -> WalletResponse:
    wallet = await wallet_service.freeze_wallet(user_id)
    return WalletResponse.from_model(wallet)


@router.post("/unfreeze", response_model=WalletResponse, summary="Unfreeze the current user's wallet")
async def unfreeze_wallet(
    user_id: uuid.UUID = Depends(get_current_auth_user_id),
    wallet_service: WalletService = Depends(get_wallet_service),
) -> WalletResponse:
    wallet = await wallet_service.unfreeze_wallet(user_id)
    return WalletResponse.from_model(wallet)


@router.post("/close", response_model=WalletResponse, summary="Close the current user's wallet")
async def close_wallet(
    user_id: uuid.UUID = Depends(get_current_auth_user_id),
    wallet_service: WalletService = Depends(get_wallet_service),
) -> WalletResponse:
    wallet = await wallet_service.close_wallet(user_id)
    return WalletResponse.from_model(wallet)
