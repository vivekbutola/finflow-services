from fastapi import APIRouter

from app.api.v1.endpoints import addresses, kyc, notifications, preferences, profile

api_router = APIRouter()
api_router.include_router(profile.router)
api_router.include_router(addresses.router)
api_router.include_router(kyc.router)
api_router.include_router(preferences.router)
api_router.include_router(notifications.router)
