import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class ThemePreference(str, enum.Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class UserPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    theme: Mapped[ThemePreference] = mapped_column(
        Enum(ThemePreference, name="theme_preference", native_enum=True),
        nullable=False,
        default=ThemePreference.SYSTEM,
    )

    user: Mapped["User"] = relationship(back_populates="preferences")

    __table_args__ = (
        Index("ux_user_preferences_user_id", "user_id", unique=True),
    )
