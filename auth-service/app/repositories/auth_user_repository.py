import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.auth_user import AuthUser, AuthUserStatus


class AuthUserRepository:
    """Persistence layer for auth_users. No business logic lives here."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> AuthUser | None:
        result = await self._session.execute(
            select(AuthUser).where(AuthUser.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> AuthUser | None:
        result = await self._session.execute(
            select(AuthUser).where(AuthUser.email == email)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        phone_number: str | None = None,
    ) -> AuthUser:
        auth_user = AuthUser(
            email=email,
            phone_number=phone_number,
            password_hash=password_hash,
            status=AuthUserStatus.ACTIVE,
        )
        self._session.add(auth_user)
        await self._session.flush()
        return auth_user

    async def record_successful_login(self, auth_user: AuthUser) -> None:
        auth_user.failed_login_attempts = 0
        auth_user.locked_until = None
        auth_user.last_login_at = datetime.now(timezone.utc)
        await self._session.flush()

    async def record_failed_login(self, auth_user: AuthUser) -> None:
        auth_user.failed_login_attempts += 1
        if auth_user.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
            auth_user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCOUNT_LOCKOUT_MINUTES
            )
            auth_user.status = AuthUserStatus.LOCKED
        await self._session.flush()

    async def update_password(self, auth_user: AuthUser, password_hash: str) -> None:
        auth_user.password_hash = password_hash
        await self._session.flush()
