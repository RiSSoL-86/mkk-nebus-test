import asyncio
import random
from datetime import UTC, datetime
from typing import final, override
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app_settings import settings
from core.common.services import BaseService
from core.payments.choices import PaymentStatus
from core.payments.repository import PaymentRepository
from services.payment_processor.errors import WebhookDeliveryError
from services.payment_processor.services.webhook import WebhookSenderService


@final
class ProcessPaymentService(BaseService[None]):
    """Emulates the payment gateway, persists the result and notifies."""

    def __init__(
        self, session: AsyncSession, webhook_sender: WebhookSenderService
    ) -> None:
        self.session = session
        self._webhook_sender = webhook_sender

    @override
    async def execute(self, payment_id: UUID) -> None:
        repository = PaymentRepository(session=self.session)
        payment = await repository.get_payment(payment_id=payment_id)
        if payment is None:
            return

        if payment.status == PaymentStatus.PENDING:
            delay = random.uniform(
                a=settings.processing.gateway.min_delay_seconds,
                b=settings.processing.gateway.max_delay_seconds,
            )
            await asyncio.sleep(delay=delay)
            status = (
                PaymentStatus.SUCCEEDED
                if random.random() < settings.processing.gateway.success_rate
                else PaymentStatus.FAILED
            )

            processed = await repository.mark_processed(
                payment_id=payment_id,
                status=status,
                processed_at=datetime.now(tz=UTC),
            )
            if processed is None:
                return
            payment = processed
        elif payment.webhook_delivered_at is not None:
            return

        delivered = await self._webhook_sender.execute(payment=payment)
        if not delivered:
            raise WebhookDeliveryError(payment_id)

        await repository.mark_webhook_delivered(
            payment_id=payment_id, delivered_at=datetime.now(tz=UTC)
        )
