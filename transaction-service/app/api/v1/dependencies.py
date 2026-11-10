import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token, extract_auth_user_id
from app.db.session import get_db
from app.services.transaction_service import TransactionService
from app.services.wallet_client import WalletServiceClient

bearer_scheme = HTTPBearer(auto_error=True)


def get_wallet_client() -> WalletServiceClient:
    return WalletServiceClient()


def get_transaction_service(
    session: AsyncSession = Depends(get_db),
    wallet_client: WalletServiceClient = Depends(get_wallet_client),
) -> TransactionService:
    return TransactionService(session, wallet_client)


async def get_current_auth_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> uuid.UUID:
    """Validates the JWT access token issued by auth-service and returns the
    authenticated user's id. This service never issues, refreshes, or
    revokes tokens — it only verifies them, identically to user-service and
    wallet-service."""
    payload = decode_access_token(credentials.credentials)
    return extract_auth_user_id(payload)
