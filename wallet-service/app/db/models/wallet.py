import enum
import secrets
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.wallet_ledger import WalletLedger


class WalletStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


def generate_public_wallet_id() -> str:
    """Human-readable, non-guessable public identifier shown to clients,
    distinct from the internal UUID primary key (e.g. WAL-9F3A7C1B2E4D)."""
    return f"WAL-{secrets.token_hex(6).upper()}"


class Wallet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One row per user (enforced by a unique index on user_id). Money is
    always stored as NUMERIC/Decimal — float is never used anywhere in this
    codebase. `version` backs SQLAlchemy's optimistic-locking mechanism
    (mapper `version_id_col`) as defense-in-depth alongside the pessimistic
    `SELECT ... FOR UPDATE` row lock taken in WalletRepository.get_for_update.
    """

    __tablename__ = "wallets"

    wallet_id: Mapped[str] = mapped_column(
        String(32), nullable=False, default=generate_public_wallet_id
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    balance: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0.0000")
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")

    status: Mapped[WalletStatus] = mapped_column(
        Enum(WalletStatus, name="wallet_status", native_enum=True),
        nullable=False,
        default=WalletStatus.ACTIVE,
    )

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    ledger_entries: Mapped[list["WalletLedger"]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan"
    )

    __mapper_args__ = {"version_id_col": version}

    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_wallets_balance_nonnegative"),
        CheckConstraint("currency = 'INR'", name="ck_wallets_currency_inr_only"),
        Index("ux_wallets_user_id", "user_id", unique=True),
        Index("ux_wallets_wallet_id", "wallet_id", unique=True),
        Index("ix_wallets_status", "status"),
    )

    def is_active(self) -> bool:
        return self.status == WalletStatus.ACTIVE
