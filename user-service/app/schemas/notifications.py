import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    created_at: datetime
    updated_at: datetime


class NotificationPreferenceUpdateRequest(BaseModel):
    email_enabled: bool | None = None
    sms_enabled: bool | None = None
    push_enabled: bool | None = None
