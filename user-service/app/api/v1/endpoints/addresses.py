import uuid

from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import get_address_service, get_current_user
from app.db.models.user import User
from app.schemas.address import AddressCreateRequest, AddressResponse, AddressUpdateRequest
from app.services.address_service import AddressService

router = APIRouter(prefix="/users/me/addresses", tags=["addresses"])


@router.get("", response_model=list[AddressResponse], summary="List the current user's addresses")
async def list_addresses(
    current_user: User = Depends(get_current_user),
    address_service: AddressService = Depends(get_address_service),
) -> list[AddressResponse]:
    addresses = await address_service.list_addresses(current_user.id)
    return [AddressResponse.model_validate(a) for a in addresses]


@router.post(
    "",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new address",
)
async def create_address(
    payload: AddressCreateRequest,
    current_user: User = Depends(get_current_user),
    address_service: AddressService = Depends(get_address_service),
) -> AddressResponse:
    address = await address_service.create_address(current_user.id, payload)
    return AddressResponse.model_validate(address)


@router.put("/{address_id}", response_model=AddressResponse, summary="Update an existing address")
async def update_address(
    address_id: uuid.UUID,
    payload: AddressUpdateRequest,
    current_user: User = Depends(get_current_user),
    address_service: AddressService = Depends(get_address_service),
) -> AddressResponse:
    address = await address_service.update_address(current_user.id, address_id, payload)
    return AddressResponse.model_validate(address)


@router.delete(
    "/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an address",
)
async def delete_address(
    address_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    address_service: AddressService = Depends(get_address_service),
) -> None:
    await address_service.delete_address(current_user.id, address_id)
