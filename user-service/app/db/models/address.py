import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class AddressType(str, enum.Enum):
    RESIDENTIAL = "residential"
    BILLING = "billing"
    BUSINESS = "business"
    SHIPPING = "shipping"


class Address(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "addresses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    address_type: Mapped[AddressType] = mapped_column(
        Enum(AddressType, name="address_type", native_enum=True),
        nullable=False,
        default=AddressType.RESIDENTIAL,
    )

    line1: Mapped[str] = mapped_column(String(255), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped["User"] = relationship(back_populates="addresses")

    __table_args__ = (
        CheckConstraint("char_length(country) = 2", name="ck_addresses_country_iso2"),
        Index("ix_addresses_user_id", "user_id"),
    )
