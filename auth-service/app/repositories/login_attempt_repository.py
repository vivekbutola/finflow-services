import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.login_attempt import LoginAttempt


class LoginAttemptRepository:
    """Append-only persistence layer for login_attempts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(
        self,
        *,
        email_attempted: str,
        ip_address: str,
        success: bool,
        auth_user_id: uuid.UUID | None = None,
        user_agent: str | None = None,
        failure_reason: str | None = None,
    ) -> LoginAttempt:
        attempt = LoginAttempt(
            auth_user_id=auth_user_id,
            email_attempted=email_attempted,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            failure_reason=failure_reason,
            attempted_at=datetime.now(timezone.utc),
        )
        self._session.add(attempt)
        await self._session.flush()
        return attempt
