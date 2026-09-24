from typing import final, override
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.common.services import BaseService
from core.payments.entities import PaymentEntity
from core.payments.repository import PaymentRepository


@final
class GetPaymentService(BaseService[PaymentEntity | None]):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @override
    async def execute(self, payment_id: UUID) -> PaymentEntity | None:
        repository = PaymentRepository(session=self.session)
        return await repository.get_payment(payment_id=payment_id)
