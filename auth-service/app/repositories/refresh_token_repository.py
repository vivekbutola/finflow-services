import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    """Persistence layer for refresh_tokens. No business logic lives here."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        auth_user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        device_fingerprint: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> RefreshToken:
        refresh_token = RefreshToken(
            auth_user_id=auth_user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            issued_at=datetime.now(timezone.utc),
            device_fingerprint=device_fingerprint,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._session.add(refresh_token)
        await self._session.flush()
        return refresh_token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(self, refresh_token: RefreshToken, replaced_by_id: uuid.UUID | None = None) -> None:
        refresh_token.revoked_at = datetime.now(timezone.utc)
        refresh_token.replaced_by_token_id = replaced_by_id
        await self._session.flush()

    async def revoke_all_for_user(self, auth_user_id: uuid.UUID) -> None:
        await self._session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.auth_user_id == auth_user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await self._session.flush()
