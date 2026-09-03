import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.address import Address


class AddressRepository:
    """Persistence layer for `addresses`. No business logic lives here."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: uuid.UUID) -> list[Address]:
        result = await self._session.execute(
            select(Address).where(Address.user_id == user_id).order_by(Address.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id_for_user(self, address_id: uuid.UUID, user_id: uuid.UUID) -> Address | None:
        result = await self._session.execute(
            select(Address).where(Address.id == address_id, Address.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(Address).where(Address.user_id == user_id)
        )
        return len(result.scalars().all())

    async def create(self, *, user_id: uuid.UUID, **fields) -> Address:
        address = Address(user_id=user_id, **fields)
        self._session.add(address)
        await self._session.flush()
        return address

    async def update(self, address: Address, **fields) -> Address:
        for key, value in fields.items():
            if value is not None:
                setattr(address, key, value)
        await self._session.flush()
        return address

    async def delete(self, address: Address) -> None:
        await self._session.delete(address)
        await self._session.flush()

    async def unset_default_for_user(self, user_id: uuid.UUID, except_address_id: uuid.UUID | None = None) -> None:
        stmt = update(Address).where(Address.user_id == user_id, Address.is_default.is_(True))
        if except_address_id is not None:
            stmt = stmt.where(Address.id != except_address_id)
        await self._session.execute(stmt.values(is_default=False))
        await self._session.flush()
