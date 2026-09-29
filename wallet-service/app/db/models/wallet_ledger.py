import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.wallet import Wallet


class LedgerEntryType(str, enum.Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class WalletLedger(UUIDPrimaryKeyMixin, Base):
    """Append-only ledger of every balance-affecting operation. Never
    updated or deleted after creation — it is the audit trail that
    reconstructs how a wallet arrived at its current balance, and also
    backs idempotent replay via the (wallet_id, reference_id) unique index.
    """

    __tablename__ = "wallet_ledger"

    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
    )

    entry_type: Mapped[LedgerEntryType] = mapped_column(
        Enum(LedgerEntryType, name="ledger_entry_type", native_enum=True),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    balance_before: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)

    reference_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    wallet: Mapped["Wallet"] = relationship(back_populates="ledger_entries")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_wallet_ledger_amount_positive"),
        CheckConstraint("balance_before >= 0", name="ck_wallet_ledger_balance_before_nonneg"),
        CheckConstraint("balance_after >= 0", name="ck_wallet_ledger_balance_after_nonneg"),
        Index("ix_wallet_ledger_wallet_id_created_at", "wallet_id", "created_at"),
        Index(
            "ux_wallet_ledger_wallet_reference",
            "wallet_id",
            "reference_id",
            unique=True,
            postgresql_where=text("reference_id IS NOT NULL"),
        ),
    )
