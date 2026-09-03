import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.metrics import user_profile_updates_total
from app.db.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserProfileUpdateRequest

logger = get_logger(__name__)


class UserService:
    """Orchestrates profile provisioning and mutation use-cases."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.users = UserRepository(session)

    async def get_or_create_profile(self, auth_user_id: uuid.UUID) -> User:
        """Fetches this user's profile, auto-provisioning a minimal row on
        first authenticated access if one does not exist yet. In a fully
        event-driven deployment this row would instead be created by
        consuming a `user.registered` event published by auth-service; this
        lazy-provisioning path keeps the service correct and self-contained
        without requiring that event bus to be wired up.
        """
        user = await self.users.get_by_auth_user_id(auth_user_id)
        if user is None:
            user = await self.users.create(auth_user_id=auth_user_id)
            await self._session.commit()
            logger.info("user_profile_provisioned", extra={"auth_user_id": str(auth_user_id)})
        return user

    async def update_profile(self, user: User, payload: UserProfileUpdateRequest) -> User:
        updated = await self.users.update(
            user,
            first_name=payload.first_name,
            last_name=payload.last_name,
            phone_number=payload.phone_number,
            date_of_birth=payload.date_of_birth,
            profile_photo_url=payload.profile_photo_url,
        )
        await self._session.commit()

        user_profile_updates_total.inc()
        logger.info("user_profile_updated", extra={"user_id": str(user.id)})
        return updated
