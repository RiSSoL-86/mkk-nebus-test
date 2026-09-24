from fastapi import APIRouter

from services.api.payments.handlers import create_payment, get_payment

router = APIRouter(prefix="/payments", tags=["payments"])
router.add_api_route(
    path="", endpoint=create_payment, methods=["POST"], status_code=202
)
router.add_api_route(
    path="/{payment_id}", endpoint=get_payment, methods=["GET"]
)
