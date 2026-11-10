from fastapi import APIRouter

from app.api.v1.endpoints import transaction

api_router = APIRouter()
api_router.include_router(transaction.router)
