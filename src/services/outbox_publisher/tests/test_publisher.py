from unittest.mock import AsyncMock
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app_settings import settings
from core.outbox.models import OutboxEvent
from core.payments.entities import PaymentData
from core.payments.event_types import PAYMENTS_ROUTING_KEY
from core.payments.repository import PaymentRepository
from services.outbox_publisher.services.publisher import OutboxPublisherService


async def test_publishes_unpublished_events_once():
    engine = create_async_engine(url=settings.db.url)
    sessions = async_sessionmaker(bind=engine, expire_on_commit=False)
    key = str(uuid4())
    data = PaymentData(
        amount="10.50",
        currency="RUB",
        description="Outbox publisher test",
        webhook_url="https://example.com/webhook",
    )
    try:
        async with sessions() as session:
            payment = await PaymentRepository(
                session=session
            ).create_with_event(data=data, idempotency_key=key)

        producer = AsyncMock()
        async with sessions() as session:
            published = await OutboxPublisherService(
                session=session, producer=producer
            ).execute(batch_size=1000)

        assert published >= 1
        producer.publish.assert_any_await(
            payload={"payment_id": str(payment.payment_id)},
            event_type=PAYMENTS_ROUTING_KEY,
        )

        async with sessions() as session:
            event = (
                await session.scalars(
                    statement=select(OutboxEvent).where(
                        OutboxEvent.payment_id == payment.payment_id
                    )
                )
            ).one()
            assert event.published_at is not None

        producer.reset_mock()
        async with sessions() as session:
            published_again = await OutboxPublisherService(
                session=session, producer=producer
            ).execute(batch_size=1000)

        assert published_again == 0
        producer.publish.assert_not_awaited()
    finally:
        await engine.dispose()
