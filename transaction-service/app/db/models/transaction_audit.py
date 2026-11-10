import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.transaction import Transaction


class TransactionAudit(UUIDPrimaryKeyMixin, Base):
    """Append-only audit trail of every state transition a transaction goes
    through (initiation, wallet-service call outcomes, completion, reversal,
    compensation). This is what a support engineer or compliance reviewer
    reconstructs a transaction's history from — never updated or deleted."""

    __tablename__ = "transaction_audit"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
    )

    action: Mapped[str] = mapped_column(String(100), nullable=False)

    # Mapped to a DB column literally named `metadata` (per the required
    # field list) via an explicit column name — the Python/ORM attribute
    # can't be called `metadata` itself, since DeclarativeBase already
    # reserves that name for SQLAlchemy's own schema-metadata object.
    audit_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    transaction: Mapped["Transaction"] = relationship(back_populates="audit_entries")

    __table_args__ = (
        Index("ix_transaction_audit_transaction_id_timestamp", "transaction_id", "timestamp"),
    )
