from fastapi import APIRouter, Depends

from app.api.v1.dependencies import get_current_user, get_preference_service
from app.db.models.user import User
from app.schemas.preferences import UserPreferenceResponse, UserPreferenceUpdateRequest
from app.services.preference_service import PreferenceService

router = APIRouter(prefix="/users/me/preferences", tags=["preferences"])


@router.get("", response_model=UserPreferenceResponse, summary="Get the current user's display preferences")
async def get_preferences(
    current_user: User = Depends(get_current_user),
    preference_service: PreferenceService = Depends(get_preference_service),
) -> UserPreferenceResponse:
    preference = await preference_service.get_or_create_preferences(current_user.id)
    return UserPreferenceResponse.model_validate(preference)


@router.put("", response_model=UserPreferenceResponse, summary="Update the current user's display preferences")
async def update_preferences(
    payload: UserPreferenceUpdateRequest,
    current_user: User = Depends(get_current_user),
    preference_service: PreferenceService = Depends(get_preference_service),
) -> UserPreferenceResponse:
    preference = await preference_service.update_preferences(current_user.id, payload)
    return UserPreferenceResponse.model_validate(preference)
