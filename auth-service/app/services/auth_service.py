import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AccountLockedError,
    AccountNotActiveError,
    InvalidCredentialsError,
    InvalidTokenError,
    RefreshTokenReusedError,
    TokenExpiredError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.db.models.auth_user import AuthUser, AuthUserStatus
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.login_attempt_repository import LoginAttemptRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.schemas.token import TokenResponse

logger = get_logger(__name__)


class AuthService:
    """Orchestrates registration, authentication, and token lifecycle use-cases."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.users = AuthUserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)
        self.login_attempts = LoginAttemptRepository(session)

    # ----------------------------------------------------------------
    # Registration
    # ----------------------------------------------------------------

    async def register(
        self,
        *,
        email: str,
        password: str,
        phone_number: str | None = None,
    ) -> AuthUser:
        normalized_email = email.strip().lower()

        existing = await self.users.get_by_email(normalized_email)
        if existing is not None:
            raise UserAlreadyExistsError(f"An account with email '{email}' already exists")

        password_hash = hash_password(password)
        auth_user = await self.users.create(
            email=normalized_email,
            password_hash=password_hash,
            phone_number=phone_number,
        )
        await self._session.commit()

        logger.info("auth_user_registered", extra={"auth_user_id": str(auth_user.id)})
        return auth_user

    # ----------------------------------------------------------------
    # Login
    # ----------------------------------------------------------------

    async def authenticate(
        self,
        *,
        email: str,
        password: str,
        ip_address: str,
        user_agent: str | None = None,
        device_fingerprint: str | None = None,
    ) -> tuple[AuthUser, TokenResponse]:
        normalized_email = email.strip().lower()
        now = datetime.now(timezone.utc)

        auth_user = await self.users.get_by_email(normalized_email)

        if auth_user is None:
            await self.login_attempts.log(
                email_attempted=normalized_email,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                failure_reason="user_not_found",
            )
            await self._session.commit()
            raise InvalidCredentialsError()

        if auth_user.is_locked(now):
            await self.login_attempts.log(
                email_attempted=normalized_email,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                auth_user_id=auth_user.id,
                failure_reason="account_locked",
            )
            await self._session.commit()
            raise AccountLockedError(
                f"Account is locked until {auth_user.locked_until.isoformat()}"
            )

        if auth_user.status not in (AuthUserStatus.ACTIVE, AuthUserStatus.LOCKED):
            await self.login_attempts.log(
                email_attempted=normalized_email,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                auth_user_id=auth_user.id,
                failure_reason=f"status_{auth_user.status.value}",
            )
            await self._session.commit()
            raise AccountNotActiveError(f"Account status is '{auth_user.status.value}'")

        if not verify_password(password, auth_user.password_hash):
            await self.users.record_failed_login(auth_user)
            await self.login_attempts.log(
                email_attempted=normalized_email,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                auth_user_id=auth_user.id,
                failure_reason="bad_password",
            )
            await self._session.commit()
            raise InvalidCredentialsError()

        # Success path
        if auth_user.status == AuthUserStatus.LOCKED:
            auth_user.status = AuthUserStatus.ACTIVE

        await self.users.record_successful_login(auth_user)
        await self.login_attempts.log(
            email_attempted=normalized_email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            auth_user_id=auth_user.id,
        )

        tokens = await self._issue_token_pair(
            auth_user,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
        )
        await self._session.commit()

        logger.info("auth_user_login_success", extra={"auth_user_id": str(auth_user.id)})
        return auth_user, tokens

    # ----------------------------------------------------------------
    # Token refresh (with rotation + reuse detection)
    # ----------------------------------------------------------------

    async def refresh(
        self,
        *,
        raw_refresh_token: str,
        ip_address: str,
        user_agent: str | None = None,
    ) -> TokenResponse:
        token_hash = hash_refresh_token(raw_refresh_token)
        stored_token = await self.refresh_tokens.get_by_hash(token_hash)

        if stored_token is None:
            raise InvalidTokenError("Refresh token is invalid")

        now = datetime.now(timezone.utc)

        if stored_token.revoked_at is not None:
            # Reuse of an already-rotated/revoked token: treat as compromised
            # and revoke the entire token family for this user.
            logger.warning(
                "refresh_token_reuse_detected",
                extra={"auth_user_id": str(stored_token.auth_user_id)},
            )
            await self.refresh_tokens.revoke_all_for_user(stored_token.auth_user_id)
            await self._session.commit()
            raise RefreshTokenReusedError()

        if stored_token.expires_at <= now:
            raise TokenExpiredError("Refresh token has expired")

        auth_user = await self.users.get_by_id(stored_token.auth_user_id)
        if auth_user is None:
            raise UserNotFoundError()

        if not auth_user.is_active():
            raise AccountNotActiveError(f"Account status is '{auth_user.status.value}'")

        tokens = await self._issue_token_pair(
            auth_user,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=stored_token.device_fingerprint,
            revoke_and_replace=stored_token,
        )
        await self._session.commit()
        return tokens

    # ----------------------------------------------------------------
    # Logout
    # ----------------------------------------------------------------

    async def logout(self, *, raw_refresh_token: str) -> None:
        token_hash = hash_refresh_token(raw_refresh_token)
        stored_token = await self.refresh_tokens.get_by_hash(token_hash)
        if stored_token is not None and stored_token.revoked_at is None:
            await self.refresh_tokens.revoke(stored_token)
        await self._session.commit()

    async def logout_all(self, *, auth_user_id: uuid.UUID) -> None:
        await self.refresh_tokens.revoke_all_for_user(auth_user_id)
        await self._session.commit()

    # ----------------------------------------------------------------
    # Lookup
    # ----------------------------------------------------------------

    async def get_user_or_raise(self, user_id: uuid.UUID) -> AuthUser:
        auth_user = await self.users.get_by_id(user_id)
        if auth_user is None:
            raise UserNotFoundError()
        return auth_user

    # ----------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------

    async def _issue_token_pair(
        self,
        auth_user: AuthUser,
        *,
        ip_address: str,
        user_agent: str | None,
        device_fingerprint: str | None,
        revoke_and_replace=None,
    ) -> TokenResponse:
        access_token, expire_at = create_access_token(
            subject=str(auth_user.id),
            extra_claims={"status": auth_user.status.value},
        )

        raw_refresh, refresh_hash = generate_refresh_token()
        new_token = await self.refresh_tokens.create(
            auth_user_id=auth_user.id,
            token_hash=refresh_hash,
            expires_at=refresh_token_expiry(),
            device_fingerprint=device_fingerprint,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if revoke_and_replace is not None:
            await self.refresh_tokens.revoke(revoke_and_replace, replaced_by_id=new_token.id)

        expires_in = int((expire_at - datetime.now(timezone.utc)).total_seconds())

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",
            expires_in=max(expires_in, 0),
        )
