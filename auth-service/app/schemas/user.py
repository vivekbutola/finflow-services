import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models.auth_user import AuthUserStatus


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    phone_number: str | None
    status: AuthUserStatus
    email_verified: bool
    phone_verified: bool
    created_at: datetime

    @classmethod
    def from_auth_user(cls, auth_user) -> "UserResponse":
        return cls(
            id=auth_user.id,
            email=auth_user.email,
            phone_number=auth_user.phone_number,
            status=auth_user.status,
            email_verified=auth_user.email_verified_at is not None,
            phone_verified=auth_user.phone_verified_at is not None,
            created_at=auth_user.created_at,
        )
