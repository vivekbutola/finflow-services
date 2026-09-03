import uuid

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountNotActiveError, InvalidTokenError
from app.core.security import decode_access_token
from app.db.models.auth_user import AuthUser
from app.db.session import get_db
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(auto_error=True)


def get_auth_service(session: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(session)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthUser:
    payload = decode_access_token(credentials.credentials)

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError("Access token subject is invalid") from exc

    auth_user = await auth_service.get_user_or_raise(user_id)

    if not auth_user.is_active():
        raise AccountNotActiveError(f"Account status is '{auth_user.status.value}'")

    return auth_user


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"
