import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class KycStatus(str, enum.Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    VERIFIED = "verified"
    REJECTED = "rejected"


class KycProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """KYC identity-verification record. `pan_number` is stored as supplied
    by the verification workflow; production deployments should encrypt this
    column at rest (e.g. pgcrypto / KMS envelope encryption) and mask it in
    every API response (see schemas.kyc.mask_pan)."""

    __tablename__ = "kyc_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    kyc_status: Mapped[KycStatus] = mapped_column(
        Enum(KycStatus, name="kyc_status", native_enum=True),
        nullable=False,
        default=KycStatus.PENDING,
    )

    pan_number: Mapped[str | None] = mapped_column(String(10), nullable=True)
    aadhaar_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    verification_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="kyc_profile")

    __table_args__ = (
        CheckConstraint(
            "aadhaar_last4 IS NULL OR aadhaar_last4 ~ '^[0-9]{4}$'",
            name="ck_kyc_profiles_aadhaar_last4_format",
        ),
        Index("ux_kyc_profiles_user_id", "user_id", unique=True),
        Index("ix_kyc_profiles_kyc_status", "kyc_status"),
    )
