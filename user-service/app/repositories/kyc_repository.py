import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.kyc_profile import KycProfile


class KycRepository:
    """Persistence layer for `kyc_profiles`. No business logic lives here."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> KycProfile | None:
        result = await self._session.execute(
            select(KycProfile).where(KycProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, *, user_id: uuid.UUID, **fields) -> KycProfile:
        kyc_profile = KycProfile(user_id=user_id, **fields)
        self._session.add(kyc_profile)
        await self._session.flush()
        return kyc_profile

    async def update(self, kyc_profile: KycProfile, **fields) -> KycProfile:
        for key, value in fields.items():
            if value is not None:
                setattr(kyc_profile, key, value)
        await self._session.flush()
        return kyc_profile
