import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.kyc_profile import KycStatus

_PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_AADHAAR_LAST4_PATTERN = re.compile(r"^\d{4}$")


def mask_pan(pan_number: str | None) -> str | None:
    """Masks all but the first 2 and last 2 characters, e.g. ABCDE1234F -> AB******F."""
    if pan_number is None or len(pan_number) < 4:
        return pan_number
    return pan_number[:2] + "*" * (len(pan_number) - 3) + pan_number[-1]


class KycProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    kyc_status: KycStatus
    pan_number_masked: str | None
    aadhaar_last4: str | None
    verification_date: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, kyc_profile) -> "KycProfileResponse":
        return cls(
            id=kyc_profile.id,
            user_id=kyc_profile.user_id,
            kyc_status=kyc_profile.kyc_status,
            pan_number_masked=mask_pan(kyc_profile.pan_number),
            aadhaar_last4=kyc_profile.aadhaar_last4,
            verification_date=kyc_profile.verification_date,
            created_at=kyc_profile.created_at,
            updated_at=kyc_profile.updated_at,
        )


class KycProfileSubmitRequest(BaseModel):
    pan_number: str = Field(..., min_length=10, max_length=10)
    aadhaar_last4: str = Field(..., min_length=4, max_length=4)

    @field_validator("pan_number")
    @classmethod
    def validate_pan_format(cls, v: str) -> str:
        v = v.upper()
        if not _PAN_PATTERN.match(v):
            raise ValueError("PAN must match the format AAAAA9999A")
        return v

    @field_validator("aadhaar_last4")
    @classmethod
    def validate_aadhaar_last4(cls, v: str) -> str:
        if not _AADHAAR_LAST4_PATTERN.match(v):
            raise ValueError("aadhaar_last4 must be exactly 4 digits")
        return v


class KycProfileUpdateRequest(BaseModel):
    pan_number: str | None = Field(default=None, min_length=10, max_length=10)
    aadhaar_last4: str | None = Field(default=None, min_length=4, max_length=4)

    @field_validator("pan_number")
    @classmethod
    def validate_pan_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.upper()
        if not _PAN_PATTERN.match(v):
            raise ValueError("PAN must match the format AAAAA9999A")
        return v

    @field_validator("aadhaar_last4")
    @classmethod
    def validate_aadhaar_last4(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _AADHAAR_LAST4_PATTERN.match(v):
            raise ValueError("aadhaar_last4 must be exactly 4 digits")
        return v
