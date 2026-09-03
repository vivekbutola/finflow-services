import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import InvalidTokenError, TokenExpiredError

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.BCRYPT_ROUNDS,
)

TokenType = Literal["access", "refresh"]


# --------------------------------------------------------------------------
# Password hashing
# --------------------------------------------------------------------------

def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def needs_rehash(password_hash: str) -> bool:
    return pwd_context.needs_update(password_hash)


# --------------------------------------------------------------------------
# Access tokens (stateless JWT)
# --------------------------------------------------------------------------

def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "iat": now,
        "exp": expire,
        "nbf": now,
        "jti": str(uuid.uuid4()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expire


def decode_access_token(token: str) -> dict[str, Any]:
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


# --------------------------------------------------------------------------
# Refresh tokens (opaque, DB-backed, rotated on use)
# --------------------------------------------------------------------------

def generate_refresh_token() -> tuple[str, str]:
    """Returns (raw_token, token_hash). Only the hash is persisted."""
    raw_token = secrets.token_urlsafe(64)
    token_hash = hash_refresh_token(raw_token)
    return raw_token, token_hash


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
