import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models.transaction import TransactionStatus

# A small, explicit reference table rather than a bare ISO-4217 format check:
# transaction-service is currency-aware for the whole platform even though
# wallet-service currently only issues INR wallets, so a transfer in any
# other listed currency will still fail downstream (wallet not found /
# currency mismatch) — this validator only rejects clearly bogus codes.
SUPPORTED_CURRENCIES: frozenset[str] = frozenset({"INR", "USD", "EUR", "GBP"})

_MAX_DECIMAL_PLACES = Decimal("0.01")


def _validate_money_precision(value: Decimal) -> Decimal:
    if value <= 0:
        raise ValueError("amount must be greater than zero")
    quantized = value.quantize(_MAX_DECIMAL_PLACES, rounding=ROUND_HALF_UP)
    if quantized != value:
        raise ValueError("amount must not have more than 2 decimal places")
    return quantized


class TransferRequest(BaseModel):
    reference_id: str = Field(..., min_length=1, max_length=100)
    from_wallet_id: uuid.UUID
    to_wallet_id: uuid.UUID
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        return _validate_money_precision(v)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        v = v.upper()
        if v not in SUPPORTED_CURRENCIES:
            raise ValueError(
                f"currency must be one of {sorted(SUPPORTED_CURRENCIES)}"
            )
        return v

    @model_validator(mode="after")
    def validate_distinct_wallets(self) -> "TransferRequest":
        if self.from_wallet_id == self.to_wallet_id:
            raise ValueError("from_wallet_id and to_wallet_id must be different")
        return self


class ReverseTransactionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference_id: str
    from_wallet_id: uuid.UUID
    to_wallet_id: uuid.UUID
    amount: Decimal
    currency: str
    status: TransactionStatus
    initiated_by_user_id: uuid.UUID
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    page: int
    page_size: int


class TransactionAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transaction_id: uuid.UUID
    action: str
    audit_metadata: dict | None = Field(serialization_alias="metadata")
    timestamp: datetime
