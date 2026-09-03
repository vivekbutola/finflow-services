import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification_preference import NotificationPreference


class NotificationPreferenceRepository:
    """Persistence layer for `notification_preferences`. No business logic lives here."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> NotificationPreference | None:
        result = await self._session.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, *, user_id: uuid.UUID, **fields) -> NotificationPreference:
        preference = NotificationPreference(user_id=user_id, **fields)
        self._session.add(preference)
        await self._session.flush()
        return preference

    async def update(self, preference: NotificationPreference, **fields) -> NotificationPreference:
        for key, value in fields.items():
            if value is not None:
                setattr(preference, key, value)
        await self._session.flush()
        return preference
