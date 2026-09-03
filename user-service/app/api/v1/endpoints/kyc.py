from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import get_current_user, get_kyc_service
from app.db.models.user import User
from app.schemas.kyc import KycProfileResponse, KycProfileSubmitRequest, KycProfileUpdateRequest
from app.services.kyc_service import KycService

router = APIRouter(prefix="/users/me/kyc", tags=["kyc"])


@router.get("", response_model=KycProfileResponse, summary="Get the current user's KYC profile")
async def get_kyc(
    current_user: User = Depends(get_current_user),
    kyc_service: KycService = Depends(get_kyc_service),
) -> KycProfileResponse:
    kyc_profile = await kyc_service.get_kyc(current_user.id)
    return KycProfileResponse.from_model(kyc_profile)


@router.post(
    "",
    response_model=KycProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit KYC details for verification",
)
async def submit_kyc(
    payload: KycProfileSubmitRequest,
    current_user: User = Depends(get_current_user),
    kyc_service: KycService = Depends(get_kyc_service),
) -> KycProfileResponse:
    kyc_profile = await kyc_service.submit_kyc(current_user.id, payload)
    return KycProfileResponse.from_model(kyc_profile)


@router.put(
    "",
    response_model=KycProfileResponse,
    summary="Amend a KYC submission (only while pending or rejected)",
)
async def update_kyc(
    payload: KycProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    kyc_service: KycService = Depends(get_kyc_service),
) -> KycProfileResponse:
    kyc_profile = await kyc_service.update_kyc(current_user.id, payload)
    return KycProfileResponse.from_model(kyc_profile)
