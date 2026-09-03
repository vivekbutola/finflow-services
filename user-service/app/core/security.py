import uuid
from typing import Any

from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import InvalidTokenError, TokenExpiredError


def decode_access_token(token: str) -> dict[str, Any]:
    """Validates signature, issuer, audience, and expiration of an access token
    issued by auth-service. This service never issues or refreshes tokens —
    it only verifies them.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Access token has expired") from exc
    except JWTError as exc:
        raise InvalidTokenError("Access token is invalid") from exc

    if payload.get("type") != "access":
        raise InvalidTokenError("Token is not an access token")

    return payload


def extract_auth_user_id(payload: dict[str, Any]) -> uuid.UUID:
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError("Access token subject is invalid") from exc
