import enum
import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, Index, String
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.address import Address
    from app.db.models.kyc_profile import KycProfile
    from app.db.models.notification_preference import NotificationPreference
    from app.db.models.user_preference import UserPreference


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The user-service's own profile record. `auth_user_id` is a logical
    reference to auth-service's auth_users.id — authentication itself is
    never performed here, only profile data ownership.

    A row is auto-provisioned on first authenticated access if one does not
    yet exist (see UserService.get_or_create_profile), mirroring how this
    would be created by a `user.registered` domain event in a fully
    event-driven deployment.
    """

    __tablename__ = "users"

    auth_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Cached copy of the login email for display/search convenience only.
    # auth-service remains the source of truth for credentials.
    email: Mapped[str | None] = mapped_column(CITEXT, nullable=True)

    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    profile_photo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", native_enum=True),
        nullable=False,
        default=UserStatus.ACTIVE,
    )

    addresses: Mapped[list["Address"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    kyc_profile: Mapped["KycProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    preferences: Mapped["UserPreference | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    notification_preferences: Mapped["NotificationPreference | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (
        Index("ux_users_auth_user_id", "auth_user_id", unique=True),
        Index("ix_users_status", "status"),
    )
