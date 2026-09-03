import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user_preference import UserPreference


class PreferenceRepository:
    """Persistence layer for `user_preferences`. No business logic lives here."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> UserPreference | None:
        result = await self._session.execute(
            select(UserPreference).where(UserPreference.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, *, user_id: uuid.UUID, **fields) -> UserPreference:
        preference = UserPreference(user_id=user_id, **fields)
        self._session.add(preference)
        await self._session.flush()
        return preference

    async def update(self, preference: UserPreference, **fields) -> UserPreference:
        for key, value in fields.items():
            if value is not None:
                setattr(preference, key, value)
        await self._session.flush()
        return preference
