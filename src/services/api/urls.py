from fastapi import APIRouter

from services.api.payments.urls import router as payments_router

router = APIRouter(prefix="/api/v1")
router.include_router(router=payments_router)
