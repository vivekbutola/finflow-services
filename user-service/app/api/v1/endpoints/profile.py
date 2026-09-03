from fastapi import APIRouter, Depends

from app.api.v1.dependencies import get_current_user, get_user_service
from app.db.models.user import User
from app.schemas.user import UserProfileResponse, UserProfileUpdateRequest
from app.services.user_service import UserService

router = APIRouter(tags=["profile"])


@router.get("/users/me", response_model=UserProfileResponse, summary="Get the current user's profile")
async def get_my_profile(current_user: User = Depends(get_current_user)) -> UserProfileResponse:
    return UserProfileResponse.model_validate(current_user)


@router.put("/users/me", response_model=UserProfileResponse, summary="Update the current user's profile")
async def update_my_profile(
    payload: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserProfileResponse:
    updated = await user_service.update_profile(current_user, payload)
    return UserProfileResponse.model_validate(updated)
