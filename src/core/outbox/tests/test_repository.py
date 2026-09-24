import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app_settings import settings
from core.outbox.repository import OutboxRepository
from core.payments.entities import PaymentData
from core.payments.repository import PaymentRepository


async def test_fetch_respects_limit_and_marks_published():
    engine = create_async_engine(url=settings.db.url)
    sessions = async_sessionmaker(bind=engine, expire_on_commit=False)
    data = PaymentData(
        amount="10.50",
        currency="RUB",
        description="Outbox repository test",
        webhook_url="https://example.com/webhook",
    )
    try:
        async with sessions() as session:
            payment = await PaymentRepository(
                session=session
            ).create_with_event(data=data, idempotency_key=str(uuid4()))

        async with sessions() as session:
            repository = OutboxRepository(session=session)
            events = await repository.fetch_unpublished_for_update(limit=0)
            assert events == []

            events = await repository.fetch_unpublished_for_update(limit=1000)
            matching = [
                event
                for event in events
                if event.payment_id == payment.payment_id
            ]
            assert len(matching) == 1
            await repository.mark_published(
                event_id=matching[0].id, published_at=datetime.now(tz=UTC)
            )
            await session.commit()

        async with sessions() as session:
            repository = OutboxRepository(session=session)
            events = await repository.fetch_unpublished_for_update(limit=1000)
            assert all(
                event.payment_id != payment.payment_id for event in events
            )
    finally:
        await engine.dispose()


async def test_skip_locked_avoids_contending_on_locked_rows():
    engine = create_async_engine(url=settings.db.url)
    sessions = async_sessionmaker(bind=engine, expire_on_commit=False)
    data = PaymentData(
        amount="10.50",
        currency="RUB",
        description="Outbox repository lock test",
        webhook_url="https://example.com/webhook",
    )
    try:
        async with sessions() as session:
            payment = await PaymentRepository(
                session=session
            ).create_with_event(data=data, idempotency_key=str(uuid4()))

        holder = sessions()
        try:
            async with holder.begin():
                held = await OutboxRepository(
                    session=holder
                ).fetch_unpublished_for_update(limit=1000)
                assert any(
                    event.payment_id == payment.payment_id for event in held
                )

                async def fetch_concurrently() -> bool:
                    async with sessions() as other:
                        other_events = await OutboxRepository(
                            session=other
                        ).fetch_unpublished_for_update(limit=1000)
                        return any(
                            event.payment_id == payment.payment_id
                            for event in other_events
                        )

                assert (
                    await asyncio.wait_for(fut=fetch_concurrently(), timeout=5)
                    is False
                )
        finally:
            await holder.close()
    finally:
        await engine.dispose()
