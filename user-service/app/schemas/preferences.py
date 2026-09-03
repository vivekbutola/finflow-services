import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.user_preference import ThemePreference


class UserPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    language: str
    timezone: str
    currency: str
    theme: ThemePreference
    created_at: datetime
    updated_at: datetime


class UserPreferenceUpdateRequest(BaseModel):
    language: str | None = Field(default=None, min_length=2, max_length=10)
    timezone: str | None = Field(default=None, min_length=1, max_length=50)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    theme: ThemePreference | None = None
