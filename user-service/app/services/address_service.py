import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AddressNotFoundError, MaxAddressesExceededError
from app.core.logging import get_logger
from app.db.models.address import Address
from app.repositories.address_repository import AddressRepository
from app.schemas.address import AddressCreateRequest, AddressUpdateRequest

logger = get_logger(__name__)

MAX_ADDRESSES_PER_USER = 10


class AddressService:
    """Orchestrates address book use-cases, including default-address invariants."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.addresses = AddressRepository(session)

    async def list_addresses(self, user_id: uuid.UUID) -> list[Address]:
        return await self.addresses.list_for_user(user_id)

    async def create_address(self, user_id: uuid.UUID, payload: AddressCreateRequest) -> Address:
        existing_count = await self.addresses.count_for_user(user_id)
        if existing_count >= MAX_ADDRESSES_PER_USER:
            raise MaxAddressesExceededError(
                f"A user may have at most {MAX_ADDRESSES_PER_USER} saved addresses"
            )

        # First address for a user is always the default, regardless of the flag supplied.
        is_default = payload.is_default or existing_count == 0

        if is_default:
            await self.addresses.unset_default_for_user(user_id)

        address = await self.addresses.create(
            user_id=user_id,
            address_type=payload.address_type,
            line1=payload.line1,
            line2=payload.line2,
            city=payload.city,
            state=payload.state,
            country=payload.country,
            postal_code=payload.postal_code,
            is_default=is_default,
        )
        await self._session.commit()

        logger.info("address_created", extra={"user_id": str(user_id), "address_id": str(address.id)})
        return address

    async def update_address(
        self, user_id: uuid.UUID, address_id: uuid.UUID, payload: AddressUpdateRequest
    ) -> Address:
        address = await self.addresses.get_by_id_for_user(address_id, user_id)
        if address is None:
            raise AddressNotFoundError()

        if payload.is_default is True:
            await self.addresses.unset_default_for_user(user_id, except_address_id=address_id)

        updated = await self.addresses.update(
            address,
            address_type=payload.address_type,
            line1=payload.line1,
            line2=payload.line2,
            city=payload.city,
            state=payload.state,
            country=payload.country,
            postal_code=payload.postal_code,
            is_default=payload.is_default,
        )
        await self._session.commit()

        logger.info("address_updated", extra={"user_id": str(user_id), "address_id": str(address_id)})
        return updated

    async def delete_address(self, user_id: uuid.UUID, address_id: uuid.UUID) -> None:
        address = await self.addresses.get_by_id_for_user(address_id, user_id)
        if address is None:
            raise AddressNotFoundError()

        was_default = address.is_default
        await self.addresses.delete(address)

        if was_default:
            remaining = await self.addresses.list_for_user(user_id)
            if remaining:
                await self.addresses.update(remaining[0], is_default=True)

        await self._session.commit()
        logger.info("address_deleted", extra={"user_id": str(user_id), "address_id": str(address_id)})
