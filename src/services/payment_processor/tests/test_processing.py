from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app_settings import settings
from core.payments.choices import Currency, PaymentStatus
from core.payments.entities import PaymentData, PaymentEntity
from core.payments.repository import PaymentRepository
from services.payment_processor.errors import WebhookDeliveryError
from services.payment_processor.services.processing import (
    ProcessPaymentService,
)


def _entity(
    status: PaymentStatus, webhook_delivered_at: datetime | None = None
) -> PaymentEntity:
    return PaymentEntity(
        amount=Decimal("10.00"),
        currency=Currency.RUB,
        description="test",
        metadata={},
        webhook_url="https://example.com/webhook",
        payment_id=uuid4(),
        status=status,
        created_at=datetime.now(tz=UTC),
        webhook_delivered_at=webhook_delivered_at,
    )


async def test_skips_missing_payment():
    repository = AsyncMock(get_payment=AsyncMock(return_value=None))
    webhook_sender = AsyncMock()
    with patch(
        "services.payment_processor.services.processing.PaymentRepository",
        return_value=repository,
    ):
        await ProcessPaymentService(
            session=AsyncMock(), webhook_sender=webhook_sender
        ).execute(payment_id=uuid4())

    repository.mark_processed.assert_not_called()
    webhook_sender.execute.assert_not_called()


async def test_skips_already_delivered_payment():
    payment = _entity(
        status=PaymentStatus.SUCCEEDED,
        webhook_delivered_at=datetime.now(tz=UTC),
    )
    repository = AsyncMock(get_payment=AsyncMock(return_value=payment))
    webhook_sender = AsyncMock()
    with patch(
        "services.payment_processor.services.processing.PaymentRepository",
        return_value=repository,
    ):
        await ProcessPaymentService(
            session=AsyncMock(), webhook_sender=webhook_sender
        ).execute(payment_id=payment.payment_id)

    repository.mark_processed.assert_not_called()
    webhook_sender.execute.assert_not_called()


async def test_retries_webhook_for_already_processed_payment():
    payment = _entity(status=PaymentStatus.SUCCEEDED)
    repository = AsyncMock(get_payment=AsyncMock(return_value=payment))
    webhook_sender = AsyncMock(execute=AsyncMock(return_value=True))
    with patch(
        "services.payment_processor.services.processing.PaymentRepository",
        return_value=repository,
    ):
        await ProcessPaymentService(
            session=AsyncMock(), webhook_sender=webhook_sender
        ).execute(payment_id=payment.payment_id)

    repository.mark_processed.assert_not_called()
    webhook_sender.execute.assert_awaited_once_with(payment=payment)
    repository.mark_webhook_delivered.assert_awaited_once()


async def test_raises_when_webhook_delivery_ultimately_fails():
    payment = _entity(status=PaymentStatus.SUCCEEDED)
    repository = AsyncMock(get_payment=AsyncMock(return_value=payment))
    webhook_sender = AsyncMock(execute=AsyncMock(return_value=False))
    with (
        patch(
            "services.payment_processor.services.processing.PaymentRepository",
            return_value=repository,
        ),
        pytest.raises(WebhookDeliveryError),
    ):
        await ProcessPaymentService(
            session=AsyncMock(), webhook_sender=webhook_sender
        ).execute(payment_id=payment.payment_id)

    repository.mark_webhook_delivered.assert_not_called()


async def test_processes_pending_payment_and_notifies():
    pending = _entity(status=PaymentStatus.PENDING)
    processed = pending.model_copy(update={"status": PaymentStatus.SUCCEEDED})
    repository = AsyncMock(
        get_payment=AsyncMock(return_value=pending),
        mark_processed=AsyncMock(return_value=processed),
    )
    webhook_sender = AsyncMock()
    with (
        patch(
            "services.payment_processor.services.processing.PaymentRepository",
            return_value=repository,
        ),
        patch(
            "services.payment_processor.services.processing.asyncio.sleep",
            AsyncMock(),
        ),
    ):
        await ProcessPaymentService(
            session=AsyncMock(), webhook_sender=webhook_sender
        ).execute(payment_id=pending.payment_id)

    repository.mark_processed.assert_awaited_once()
    webhook_sender.execute.assert_awaited_once_with(payment=processed)


async def test_skips_webhook_when_already_processed_concurrently():
    pending = _entity(status=PaymentStatus.PENDING)
    repository = AsyncMock(
        get_payment=AsyncMock(return_value=pending),
        mark_processed=AsyncMock(return_value=None),
    )
    webhook_sender = AsyncMock()
    with (
        patch(
            "services.payment_processor.services.processing.PaymentRepository",
            return_value=repository,
        ),
        patch(
            "services.payment_processor.services.processing.asyncio.sleep",
            AsyncMock(),
        ),
    ):
        await ProcessPaymentService(
            session=AsyncMock(), webhook_sender=webhook_sender
        ).execute(payment_id=pending.payment_id)

    webhook_sender.execute.assert_not_called()


async def test_processes_pending_payment_in_one_session_against_the_db():
    engine = create_async_engine(url=settings.db.url)
    sessions = async_sessionmaker(bind=engine, expire_on_commit=False)
    data = PaymentData(
        amount="10.50",
        currency="RUB",
        description="Processing test",
        webhook_url="https://example.com/webhook",
    )
    webhook_sender = AsyncMock(execute=AsyncMock(return_value=True))
    try:
        async with sessions() as session:
            payment = await PaymentRepository(
                session=session
            ).create_with_event(data=data, idempotency_key=str(uuid4()))

        with patch(
            "services.payment_processor.services.processing.asyncio.sleep",
            AsyncMock(),
        ):
            async with sessions() as session:
                await ProcessPaymentService(
                    session=session, webhook_sender=webhook_sender
                ).execute(payment_id=payment.payment_id)

        async with sessions() as session:
            processed = await PaymentRepository(session=session).get_payment(
                payment_id=payment.payment_id
            )

        assert processed is not None
        assert processed.status in {
            PaymentStatus.SUCCEEDED,
            PaymentStatus.FAILED,
        }
        assert processed.webhook_delivered_at is not None
    finally:
        await engine.dispose()
