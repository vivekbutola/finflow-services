import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.config import settings

_PASSWORD_UPPER = re.compile(r"[A-Z]")
_PASSWORD_LOWER = re.compile(r"[a-z]")
_PASSWORD_DIGIT = re.compile(r"\d")
_PASSWORD_SPECIAL = re.compile(r"[^A-Za-z0-9]")


def _validate_password_strength(value: str) -> str:
    if len(value) < settings.PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long"
        )
    if not _PASSWORD_UPPER.search(value):
        raise ValueError("Password must contain at least one uppercase letter")
    if not _PASSWORD_LOWER.search(value):
        raise ValueError("Password must contain at least one lowercase letter")
    if not _PASSWORD_DIGIT.search(value):
        raise ValueError("Password must contain at least one digit")
    if not _PASSWORD_SPECIAL.search(value):
        raise ValueError("Password must contain at least one special character")
    return value


class RegisterRequest(BaseModel):
    email: EmailStr
    phone_number: str | None = Field(default=None, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return _validate_password_strength(value)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
    device_fingerprint: str | None = Field(default=None, max_length=255)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return _validate_password_strength(value)


class LogoutRequest(BaseModel):
    refresh_token: str
