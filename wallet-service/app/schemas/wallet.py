import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.wallet import WalletStatus
from app.db.models.wallet_ledger import LedgerEntryType

_MAX_DECIMAL_PLACES = 2  # INR minor unit (paise)


def _validate_money_precision(value: Decimal) -> Decimal:
    if value <= 0:
        raise ValueError("amount must be greater than zero")
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if quantized != value:
        raise ValueError("amount must not have more than 2 decimal places")
    return quantized


class WalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    wallet_id: str
    user_id: uuid.UUID
    available_balance: Decimal
    currency: str
    status: WalletStatus
    created_at: datetime

    @classmethod
    def from_model(cls, wallet) -> "WalletResponse":
        return cls(
            wallet_id=wallet.wallet_id,
            user_id=wallet.user_id,
            available_balance=wallet.balance,
            currency=wallet.currency,
            status=wallet.status,
            created_at=wallet.created_at,
        )


class WalletCreditRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    reference_id: str = Field(..., min_length=1, max_length=100)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        return _validate_money_precision(v)


class WalletDebitRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    reference_id: str = Field(..., min_length=1, max_length=100)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        return _validate_money_precision(v)


class WalletLedgerEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entry_type: LedgerEntryType
    amount: Decimal
    balance_before: Decimal
    balance_after: Decimal
    reference_id: str | None
    created_at: datetime


class WalletBalanceOperationResponse(BaseModel):
    wallet_id: str
    available_balance: Decimal
    currency: str
    status: WalletStatus
    ledger_entry: WalletLedgerEntryResponse
