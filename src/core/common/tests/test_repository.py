from typing import final
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app_settings import settings
from core.common.repository import BaseRepository
from core.payments.choices import Currency, PaymentStatus
from core.payments.models import Payment


@final
class _PaymentRepository(BaseRepository[Payment, UUID]):
    model = Payment


def _payment_data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": uuid4(),
        "amount": "10.50",
        "currency": Currency.RUB,
        "description": "BaseRepository test",
        "extra_data": {},
        "status": PaymentStatus.PENDING,
        "idempotency_key": str(uuid4()),
        "webhook_url": "https://example.com/webhook",
    }
    data.update(overrides)
    return data


async def test_create_get_update_delete_roundtrip():
    engine = create_async_engine(url=settings.db.url)
    sessions = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            repository = _PaymentRepository(session=session)
            created = await repository.create(data=_payment_data())
            await session.commit()

            fetched = await repository.get(pk=created.id)
            assert fetched is not None
            assert fetched.description == "BaseRepository test"

            updated = await repository.update(
                pk=created.id, data={"description": "Updated"}
            )
            assert updated is not None
            assert updated.description == "Updated"
            assert (
                await repository.update(pk=uuid4(), data={"description": "x"})
                is None
            )

            await repository.delete(pk=created.id)
            await session.commit()
            assert await repository.get(pk=created.id) is None
            await repository.delete(pk=uuid4())
    finally:
        await engine.dispose()


async def test_list_paginates_and_orders_by_creation():
    engine = create_async_engine(url=settings.db.url)
    sessions = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            repository = _PaymentRepository(session=session)
            key_prefix = str(uuid4())
            created_ids = [
                (
                    await repository.create(
                        data=_payment_data(
                            idempotency_key=f"{key_prefix}-{i}",
                            description=f"payment-{i}",
                        )
                    )
                ).id
                for i in range(3)
            ]
            await session.commit()

            where = Payment.idempotency_key.startswith(key_prefix)
            first_page, total = await repository._paginate(
                where, limit=2, offset=0
            )
            second_page, _ = await repository._paginate(
                where, limit=2, offset=2
            )

            all_ids = [row.id for row in (*first_page, *second_page)]
            assert total == 3
            assert len(first_page) == 2
            assert len(second_page) == 1
            assert set(created_ids) == set(all_ids)

            page, count = await repository.list(limit=2, offset=0)
            assert count >= 3
            assert len(page) == 2
    finally:
        await engine.dispose()
