from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from core.payments.entities import PaymentData, PaymentEntity
from core.payments.errors import IdempotencyConflictError
from services.api.payments.schemas import PaymentAccepted
from services.api.payments.services.create import CreatePaymentService
from services.api.payments.services.get import GetPaymentService


async def create_payment(
    data: PaymentData,
    session: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=255, pattern=r"\S")
    ],
) -> PaymentAccepted:
    service = CreatePaymentService(session=session)
    try:
        payment = await service.execute(
            data=data, idempotency_key=idempotency_key
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return PaymentAccepted(
        payment_id=payment.payment_id,
        status=payment.status,
        created_at=payment.created_at,
    )


async def get_payment(
    payment_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentEntity:
    service = GetPaymentService(session=session)
    payment = await service.execute(payment_id=payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment
