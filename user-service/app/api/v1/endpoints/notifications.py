from fastapi import APIRouter, Depends

from app.api.v1.dependencies import get_current_user, get_notification_preference_service
from app.db.models.user import User
from app.schemas.notifications import (
    NotificationPreferenceResponse,
    NotificationPreferenceUpdateRequest,
)
from app.services.notification_preference_service import NotificationPreferenceService

router = APIRouter(prefix="/users/me/notifications", tags=["notifications"])


@router.get(
    "",
    response_model=NotificationPreferenceResponse,
    summary="Get the current user's notification channel preferences",
)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    notification_service: NotificationPreferenceService = Depends(get_notification_preference_service),
) -> NotificationPreferenceResponse:
    preference = await notification_service.get_or_create_preferences(current_user.id)
    return NotificationPreferenceResponse.model_validate(preference)


@router.put(
    "",
    response_model=NotificationPreferenceResponse,
    summary="Update the current user's notification channel preferences",
)
async def update_notification_preferences(
    payload: NotificationPreferenceUpdateRequest,
    current_user: User = Depends(get_current_user),
    notification_service: NotificationPreferenceService = Depends(get_notification_preference_service),
) -> NotificationPreferenceResponse:
    preference = await notification_service.update_preferences(current_user.id, payload)
    return NotificationPreferenceResponse.model_validate(preference)
