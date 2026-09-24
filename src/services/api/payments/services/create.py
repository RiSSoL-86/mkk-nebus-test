from typing import final, override

from sqlalchemy.ext.asyncio import AsyncSession

from core.common.services import BaseService
from core.payments.entities import PaymentData, PaymentEntity
from core.payments.repository import PaymentRepository


@final
class CreatePaymentService(BaseService[PaymentEntity]):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @override
    async def execute(
        self, data: PaymentData, idempotency_key: str
    ) -> PaymentEntity:
        repository = PaymentRepository(session=self.session)
        return await repository.create_with_event(
            data=data, idempotency_key=idempotency_key
        )
