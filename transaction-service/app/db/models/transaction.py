import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.transaction_audit import TransactionAudit


class TransactionStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The immutable system-of-record for a wallet-to-wallet transfer. Money
    itself is never moved here — wallet-service owns balances — this table
    is the authoritative ledger of *what was attempted and what happened*.
    `from_wallet_id`/`to_wallet_id`/`initiated_by_user_id` are logical
    references to wallet-service/auth-service; no physical foreign key
    crosses a service/database boundary.
    """

    __tablename__ = "transactions"

    reference_id: Mapped[str] = mapped_column(String(100), nullable=False)

    from_wallet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    to_wallet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, name="transaction_status", native_enum=True),
        nullable=False,
        default=TransactionStatus.PENDING,
    )

    # Practical additions beyond the minimum required field set: who
    # requested the transfer, and — when it didn't succeed — why, both of
    # which any real operations/support team needs to triage a transaction.
    initiated_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    audit_entries: Mapped[list["TransactionAudit"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        CheckConstraint("from_wallet_id != to_wallet_id", name="ck_transactions_distinct_wallets"),
        Index("ux_transactions_reference_id", "reference_id", unique=True),
        Index("ix_transactions_from_wallet_id_created_at", "from_wallet_id", "created_at"),
        Index("ix_transactions_to_wallet_id_created_at", "to_wallet_id", "created_at"),
        Index("ix_transactions_status", "status"),
        Index("ix_transactions_initiated_by_user_id", "initiated_by_user_id"),
    )

    def is_reversible(self) -> bool:
        return self.status == TransactionStatus.SUCCESS
