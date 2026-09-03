import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.notification_preference import NotificationPreference
from app.repositories.notification_preference_repository import NotificationPreferenceRepository
from app.schemas.notifications import NotificationPreferenceUpdateRequest

logger = get_logger(__name__)


class NotificationPreferenceService:
    """Orchestrates notification-channel preference use-cases with upsert-on-first-access."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.notification_preferences = NotificationPreferenceRepository(session)

    async def get_or_create_preferences(self, user_id: uuid.UUID) -> NotificationPreference:
        preference = await self.notification_preferences.get_by_user_id(user_id)
        if preference is None:
            preference = await self.notification_preferences.create(user_id=user_id)
            await self._session.commit()
        return preference

    async def update_preferences(
        self, user_id: uuid.UUID, payload: NotificationPreferenceUpdateRequest
    ) -> NotificationPreference:
        preference = await self.get_or_create_preferences(user_id)
        updated = await self.notification_preferences.update(
            preference,
            email_enabled=payload.email_enabled,
            sms_enabled=payload.sms_enabled,
            push_enabled=payload.push_enabled,
        )
        await self._session.commit()

        logger.info("notification_preferences_updated", extra={"user_id": str(user_id)})
        return updated
