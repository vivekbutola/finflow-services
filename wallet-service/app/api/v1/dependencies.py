import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token, extract_auth_user_id
from app.db.session import get_db
from app.services.wallet_service import WalletService

bearer_scheme = HTTPBearer(auto_error=True)


def get_wallet_service(session: AsyncSession = Depends(get_db)) -> WalletService:
    return WalletService(session)


async def get_current_auth_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> uuid.UUID:
    """Validates the JWT access token issued by auth-service and returns the
    authenticated user's id. This service never issues, refreshes, or
    revokes tokens — it only verifies them, identically to user-service."""
    payload = decode_access_token(credentials.credentials)
    return extract_auth_user_id(payload)
