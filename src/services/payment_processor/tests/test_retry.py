from unittest.mock import AsyncMock
from uuid import uuid4

from app_settings import settings
from services.payment_processor.schemas import PaymentNewEvent
from services.payment_processor.services.retry import ReroutePaymentService


async def test_reroutes_to_retry_with_the_next_attempt():
    producer = AsyncMock()
    event = PaymentNewEvent(payment_id=uuid4())

    await ReroutePaymentService(producer=producer).execute(
        event=event, retry_count=1
    )

    producer.retry.assert_awaited_once_with(
        payload=event.model_dump(mode="json"), attempt=2
    )


async def test_moves_to_dlq_once_retry_budget_exhausted():
    producer = AsyncMock()
    event = PaymentNewEvent(payment_id=uuid4())

    await ReroutePaymentService(producer=producer).execute(
        event=event, retry_count=settings.processing.retry.max_attempts - 1
    )

    producer.dead_letter.assert_awaited_once_with(
        payload=event.model_dump(mode="json"),
        attempt=settings.processing.retry.max_attempts,
    )
