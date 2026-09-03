import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, Index, SmallInteger, String
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.login_attempt import LoginAttempt
    from app.db.models.refresh_token import RefreshToken


class AuthUserStatus(str, enum.Enum):
    ACTIVE = "active"
    LOCKED = "locked"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class AuthUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "auth_users"

    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_algo_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    status: Mapped[AuthUserStatus] = mapped_column(
        Enum(AuthUserStatus, name="auth_user_status", native_enum=True),
        nullable=False,
        default=AuthUserStatus.ACTIVE,
    )

    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    failed_login_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="auth_user",
        cascade="all, delete-orphan",
    )
    login_attempts: Mapped[list["LoginAttempt"]] = relationship(
        back_populates="auth_user",
    )

    __table_args__ = (
        CheckConstraint("failed_login_attempts >= 0", name="ck_auth_users_failed_attempts_nonneg"),
        Index("ix_auth_users_status", "status"),
    )

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and self.locked_until > now

    def is_active(self) -> bool:
        return self.status == AuthUserStatus.ACTIVE
