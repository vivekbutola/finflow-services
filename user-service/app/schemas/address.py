import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.address import AddressType


class AddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    address_type: AddressType
    line1: str
    line2: str | None
    city: str
    state: str | None
    country: str
    postal_code: str | None
    is_default: bool
    created_at: datetime
    updated_at: datetime


class AddressCreateRequest(BaseModel):
    address_type: AddressType = AddressType.RESIDENTIAL
    line1: str = Field(..., min_length=1, max_length=255)
    line2: str | None = Field(default=None, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str = Field(..., min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=20)
    is_default: bool = False

    @field_validator("country")
    @classmethod
    def uppercase_country(cls, v: str) -> str:
        return v.upper()


class AddressUpdateRequest(BaseModel):
    address_type: AddressType | None = None
    line1: str | None = Field(default=None, min_length=1, max_length=255)
    line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    postal_code: str | None = Field(default=None, max_length=20)
    is_default: bool | None = None

    @field_validator("country")
    @classmethod
    def uppercase_country(cls, v: str | None) -> str | None:
        return v.upper() if v else v
