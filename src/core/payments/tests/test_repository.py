import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app_settings import settings
from core.outbox.models import OutboxEvent
from core.payments.choices import PaymentStatus
from core.payments.entities import PaymentData, PaymentEntity
from core.payments.errors import IdempotencyConflictError
from core.payments.models import Payment
from core.payments.repository import PaymentRepository


async def test_concurrent_creation_and_conflict():
    engine = create_async_engine(url=settings.db.url)
    sessions = async_sessionmaker(bind=engine, expire_on_commit=False)
    key = str(uuid4())
    data = PaymentData(
        amount="10.50",
        currency="RUB",
        description="Concurrent request",
        metadata={"order": key},
        webhook_url="https://example.com/webhook",
    )

    async def create() -> PaymentEntity:
        async with sessions() as session:
            return await PaymentRepository(session=session).create_with_event(
                data=data, idempotency_key=key
            )

    try:
        results = await asyncio.gather(*(create() for _ in range(8)))
        assert len({payment.payment_id for payment in results}) == 1
        async with sessions() as session:
            assert (
                await session.scalar(
                    statement=select(func.count())
                    .select_from(Payment)
                    .where(Payment.idempotency_key == key)
                )
                == 1
            )
            assert (
                await session.scalar(
                    statement=select(func.count())
                    .select_from(OutboxEvent)
                    .where(OutboxEvent.payment_id == results[0].payment_id)
                )
                == 1
            )
        async with sessions() as session:
            with pytest.raises(IdempotencyConflictError):
                await PaymentRepository(session=session).create_with_event(
                    data=data.model_copy(update={"description": "Changed"}),
                    idempotency_key=key,
                )
        async with sessions() as session:
            payment = await PaymentRepository(session=session).get_payment(
                payment_id=results[0].payment_id
            )
            assert payment is not None
            assert payment.description == data.description
    finally:
        await engine.dispose()


async def test_outbox_failure_rolls_back_payment():
    engine = create_async_engine(url=settings.db.url)
    sessions = async_sessionmaker(bind=engine, expire_on_commit=False)
    key = str(uuid4())
    data = PaymentData(
        amount="10.50",
        currency="RUB",
        description="Rollback test",
        webhook_url="https://example.com/webhook",
    )
    try:
        async with sessions() as session:
            with patch.object(
                session, "flush", AsyncMock(side_effect=RuntimeError("outbox"))
            ):
                with pytest.raises(RuntimeError, match="outbox"):
                    await PaymentRepository(session=session).create_with_event(
                        data=data, idempotency_key=key
                    )
        async with sessions() as session:
            assert (
                await session.scalar(
                    statement=select(Payment.id).where(
                        Payment.idempotency_key == key
                    )
                )
                is None
            )
    finally:
        await engine.dispose()


async def test_mark_processed_claims_exactly_once_under_concurrency():
    engine = create_async_engine(url=settings.db.url)
    sessions = async_sessionmaker(bind=engine, expire_on_commit=False)
    key = str(uuid4())
    data = PaymentData(
        amount="10.50",
        currency="RUB",
        description="mark_processed test",
        webhook_url="https://example.com/webhook",
    )
    try:
        async with sessions() as session:
            payment = await PaymentRepository(
                session=session
            ).create_with_event(data=data, idempotency_key=key)

        async def claim() -> PaymentEntity | None:
            async with sessions() as session:
                return await PaymentRepository(session=session).mark_processed(
                    payment_id=payment.payment_id,
                    status=PaymentStatus.SUCCEEDED,
                    processed_at=datetime.now(tz=UTC),
                )

        results = await asyncio.gather(*(claim() for _ in range(8)))
        winners = [result for result in results if result is not None]
        assert len(winners) == 1
        assert winners[0].status == PaymentStatus.SUCCEEDED

        async with sessions() as session:
            payment_row = await session.get(
                entity=Payment, ident=payment.payment_id
            )
            assert payment_row is not None
            assert payment_row.status == PaymentStatus.SUCCEEDED
    finally:
        await engine.dispose()


async def test_mark_webhook_delivered_sets_the_timestamp():
    engine = create_async_engine(url=settings.db.url)
    sessions = async_sessionmaker(bind=engine, expire_on_commit=False)
    key = str(uuid4())
    data = PaymentData(
        amount="10.50",
        currency="RUB",
        description="mark_webhook_delivered test",
        webhook_url="https://example.com/webhook",
    )
    try:
        async with sessions() as session:
            payment = await PaymentRepository(
                session=session
            ).create_with_event(data=data, idempotency_key=key)

        delivered_at = datetime.now(tz=UTC)
        async with sessions() as session:
            await PaymentRepository(session=session).mark_webhook_delivered(
                payment_id=payment.payment_id, delivered_at=delivered_at
            )

        async with sessions() as session:
            payment_row = await session.get(
                entity=Payment, ident=payment.payment_id
            )
            assert payment_row is not None
            assert payment_row.webhook_delivered_at == delivered_at
    finally:
        await engine.dispose()


async def test_repeating_create_with_same_data_returns_existing_entity():
    engine = create_async_engine(url=settings.db.url)
    sessions = async_sessionmaker(bind=engine, expire_on_commit=False)
    key = str(uuid4())
    data = PaymentData(
        amount="10.50",
        currency="RUB",
        description="Idempotent replay",
        webhook_url="https://example.com/webhook",
    )
    try:
        async with sessions() as session:
            first = await PaymentRepository(session=session).create_with_event(
                data=data, idempotency_key=key
            )
        async with sessions() as session:
            second = await PaymentRepository(
                session=session
            ).create_with_event(data=data, idempotency_key=key)
        assert second.payment_id == first.payment_id
    finally:
        await engine.dispose()


async def test_mark_processed_skips_missing_payment():
    engine = create_async_engine(url=settings.db.url)
    sessions = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            result = await PaymentRepository(session=session).mark_processed(
                payment_id=uuid4(),
                status=PaymentStatus.SUCCEEDED,
                processed_at=datetime.now(tz=UTC),
            )
        assert result is None
    finally:
        await engine.dispose()
