import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.dependencies import get_current_auth_user_id, get_transaction_service
from app.db.models.transaction import TransactionStatus
from app.schemas.transaction import (
    ReverseTransactionRequest,
    TransactionListResponse,
    TransactionResponse,
    TransferRequest,
)
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post(
    "/transfer",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Transfer funds from one wallet to another",
)
async def transfer_funds(
    payload: TransferRequest,
    initiated_by_user_id: uuid.UUID = Depends(get_current_auth_user_id),
    transaction_service: TransactionService = Depends(get_transaction_service),
) -> TransactionResponse:
    transaction = await transaction_service.transfer_funds(initiated_by_user_id, payload)
    return TransactionResponse.model_validate(transaction)


@router.get(
    "",
    response_model=TransactionListResponse,
    summary="List transactions, optionally filtered by status or wallet",
)
async def list_transactions(
    status_filter: TransactionStatus | None = Query(default=None, alias="status"),
    wallet_id: uuid.UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _initiated_by_user_id: uuid.UUID = Depends(get_current_auth_user_id),
    transaction_service: TransactionService = Depends(get_transaction_service),
) -> TransactionListResponse:
    items, total = await transaction_service.list_transactions(
        status=status_filter, wallet_id=wallet_id, page=page, page_size=page_size
    )
    return TransactionListResponse(
        items=[TransactionResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get a single transaction by id",
)
async def get_transaction(
    transaction_id: uuid.UUID,
    _initiated_by_user_id: uuid.UUID = Depends(get_current_auth_user_id),
    transaction_service: TransactionService = Depends(get_transaction_service),
) -> TransactionResponse:
    transaction = await transaction_service.get_transaction(transaction_id)
    return TransactionResponse.model_validate(transaction)


@router.post(
    "/{transaction_id}/reverse",
    response_model=TransactionResponse,
    summary="Reverse a completed (SUCCESS) transaction",
)
async def reverse_transaction(
    transaction_id: uuid.UUID,
    payload: ReverseTransactionRequest = ReverseTransactionRequest(),
    _initiated_by_user_id: uuid.UUID = Depends(get_current_auth_user_id),
    transaction_service: TransactionService = Depends(get_transaction_service),
) -> TransactionResponse:
    transaction = await transaction_service.reverse_transaction(
        transaction_id, reason=payload.reason
    )
    return TransactionResponse.model_validate(transaction)
