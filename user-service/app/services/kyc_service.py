import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    KycAlreadySubmittedError,
    KycImmutableStateError,
    KycProfileNotFoundError,
)
from app.core.logging import get_logger
from app.core.metrics import kyc_submissions_total
from app.db.models.kyc_profile import KycProfile, KycStatus
from app.repositories.kyc_repository import KycRepository
from app.schemas.kyc import KycProfileSubmitRequest, KycProfileUpdateRequest

logger = get_logger(__name__)

# Once a KYC profile reaches one of these terminal/in-flight states it can no
# longer be edited directly by the user; a new review workflow (outside the
# scope of this service) would be required to change it.
_IMMUTABLE_STATES = (KycStatus.VERIFIED, KycStatus.IN_REVIEW)


class KycService:
    """Orchestrates KYC submission and update use-cases, enforcing the
    verification-state machine."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.kyc_profiles = KycRepository(session)

    async def get_kyc(self, user_id: uuid.UUID) -> KycProfile:
        kyc_profile = await self.kyc_profiles.get_by_user_id(user_id)
        if kyc_profile is None:
            raise KycProfileNotFoundError()
        return kyc_profile

    async def submit_kyc(self, user_id: uuid.UUID, payload: KycProfileSubmitRequest) -> KycProfile:
        existing = await self.kyc_profiles.get_by_user_id(user_id)
        if existing is not None:
            raise KycAlreadySubmittedError(
                "A KYC profile already exists for this user; use PUT to amend it"
            )

        kyc_profile = await self.kyc_profiles.create(
            user_id=user_id,
            pan_number=payload.pan_number,
            aadhaar_last4=payload.aadhaar_last4,
            kyc_status=KycStatus.IN_REVIEW,
        )
        await self._session.commit()

        kyc_submissions_total.labels(status=KycStatus.IN_REVIEW.value).inc()
        logger.info("kyc_submitted", extra={"user_id": str(user_id), "kyc_profile_id": str(kyc_profile.id)})
        return kyc_profile

    async def update_kyc(
        self, user_id: uuid.UUID, payload: KycProfileUpdateRequest
    ) -> KycProfile:
        kyc_profile = await self.kyc_profiles.get_by_user_id(user_id)
        if kyc_profile is None:
            raise KycProfileNotFoundError()

        if kyc_profile.kyc_status in _IMMUTABLE_STATES:
            raise KycImmutableStateError(
                f"KYC profile cannot be modified while status is '{kyc_profile.kyc_status.value}'"
            )

        updated = await self.kyc_profiles.update(
            kyc_profile,
            pan_number=payload.pan_number,
            aadhaar_last4=payload.aadhaar_last4,
            kyc_status=KycStatus.IN_REVIEW,
            verification_date=None,
        )
        await self._session.commit()

        kyc_submissions_total.labels(status=KycStatus.IN_REVIEW.value).inc()
        logger.info("kyc_updated", extra={"user_id": str(user_id), "kyc_profile_id": str(kyc_profile.id)})
        return updated
