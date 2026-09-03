import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.user import UserStatus


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    auth_user_id: uuid.UUID
    email: str | None
    first_name: str | None
    last_name: str | None
    phone_number: str | None
    date_of_birth: date | None
    profile_photo_url: str | None
    status: UserStatus
    created_at: datetime
    updated_at: datetime


class UserProfileUpdateRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone_number: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    profile_photo_url: str | None = Field(default=None, max_length=1024)
