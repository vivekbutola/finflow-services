from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token, extract_auth_user_id
from app.db.models.user import User
from app.db.session import get_db
from app.services.address_service import AddressService
from app.services.kyc_service import KycService
from app.services.notification_preference_service import NotificationPreferenceService
from app.services.preference_service import PreferenceService
from app.services.user_service import UserService

bearer_scheme = HTTPBearer(auto_error=True)


def get_user_service(session: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(session)


def get_address_service(session: AsyncSession = Depends(get_db)) -> AddressService:
    return AddressService(session)


def get_kyc_service(session: AsyncSession = Depends(get_db)) -> KycService:
    return KycService(session)


def get_preference_service(session: AsyncSession = Depends(get_db)) -> PreferenceService:
    return PreferenceService(session)


def get_notification_preference_service(
    session: AsyncSession = Depends(get_db),
) -> NotificationPreferenceService:
    return NotificationPreferenceService(session)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """Validates the JWT access token issued by auth-service, then resolves
    (or lazily provisions) the corresponding local profile row. This service
    never issues, refreshes, or revokes tokens — it only verifies them."""
    payload = decode_access_token(credentials.credentials)
    auth_user_id = extract_auth_user_id(payload)
    return await user_service.get_or_create_profile(auth_user_id)
