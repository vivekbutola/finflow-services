from fastapi import APIRouter

from app.api.v1.endpoints import wallet

api_router = APIRouter()
api_router.include_router(wallet.router)
