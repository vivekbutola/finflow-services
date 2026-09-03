import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.user_preference import UserPreference
from app.repositories.preference_repository import PreferenceRepository
from app.schemas.preferences import UserPreferenceUpdateRequest

logger = get_logger(__name__)


class PreferenceService:
    """Orchestrates display/locale preference use-cases with upsert-on-first-access."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.preferences = PreferenceRepository(session)

    async def get_or_create_preferences(self, user_id: uuid.UUID) -> UserPreference:
        preference = await self.preferences.get_by_user_id(user_id)
        if preference is None:
            preference = await self.preferences.create(user_id=user_id)
            await self._session.commit()
        return preference

    async def update_preferences(
        self, user_id: uuid.UUID, payload: UserPreferenceUpdateRequest
    ) -> UserPreference:
        preference = await self.get_or_create_preferences(user_id)
        updated = await self.preferences.update(
            preference,
            language=payload.language,
            timezone=payload.timezone,
            currency=payload.currency,
            theme=payload.theme,
        )
        await self._session.commit()

        logger.info("user_preferences_updated", extra={"user_id": str(user_id)})
        return updated
