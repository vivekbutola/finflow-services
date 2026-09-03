import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import CITEXT, INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.auth_user import AuthUser


class LoginAttempt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "login_attempts"

    auth_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    email_attempted: Mapped[str | None] = mapped_column(CITEXT, nullable=True)
    ip_address: Mapped[str] = mapped_column(INET, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    auth_user: Mapped["AuthUser | None"] = relationship(back_populates="login_attempts")

    __table_args__ = (
        Index("ix_login_attempts_auth_user_id", "auth_user_id"),
        Index("ix_login_attempts_ip_attempted_at", "ip_address", "attempted_at"),
    )
