import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


class UserRepository:
    """Persistence layer for `users`. No business logic lives here."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_auth_user_id(self, auth_user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(
            select(User).where(User.auth_user_id == auth_user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, *, auth_user_id: uuid.UUID) -> User:
        user = User(auth_user_id=auth_user_id)
        self._session.add(user)
        await self._session.flush()
        return user

    async def update(self, user: User, **fields) -> User:
        for key, value in fields.items():
            if value is not None:
                setattr(user, key, value)
        await self._session.flush()
        return user
