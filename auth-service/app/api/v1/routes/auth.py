from fastapi import APIRouter, Depends, Request, status

from app.api.v1.dependencies.auth import get_auth_service, get_client_ip, get_current_user
from app.db.models.auth_user import AuthUser
from app.schemas.auth import LoginRequest, LogoutRequest, RegisterRequest
from app.schemas.token import RefreshRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
)
async def register(
    payload: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    auth_user = await auth_service.register(
        email=payload.email,
        password=payload.password,
        phone_number=payload.phone_number,
    )
    return UserResponse.from_auth_user(auth_user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive an access/refresh token pair",
)
async def login(
    payload: LoginRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    _, tokens = await auth_service.authenticate(
        email=payload.email,
        password=payload.password,
        ip_address=ip_address,
        user_agent=user_agent,
        device_fingerprint=payload.device_fingerprint,
    )
    return tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new token pair (rotates the refresh token)",
)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    return await auth_service.refresh(
        raw_refresh_token=payload.refresh_token,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a single refresh token",
)
async def logout(
    payload: LogoutRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    await auth_service.logout(raw_refresh_token=payload.refresh_token)


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke all refresh tokens for the current user (all devices)",
)
async def logout_all(
    current_user: AuthUser = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    await auth_service.logout_all(auth_user_id=current_user.id)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the currently authenticated user",
)
async def get_me(current_user: AuthUser = Depends(get_current_user)) -> UserResponse:
    return UserResponse.from_auth_user(current_user)
