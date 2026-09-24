from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from services.api.payments.services.get import GetPaymentService


async def test_delegates_to_repository():
    entity = object()
    repository = AsyncMock(get_payment=AsyncMock(return_value=entity))
    session = AsyncMock(spec=AsyncSession)
    payment_id = uuid4()

    with patch(
        "services.api.payments.services.get.PaymentRepository",
        return_value=repository,
    ) as repository_factory:
        result = await GetPaymentService(session=session).execute(
            payment_id=payment_id
        )

    repository_factory.assert_called_once_with(session=session)
    repository.get_payment.assert_awaited_once_with(payment_id=payment_id)
    assert result is entity


async def test_returns_none_when_payment_missing():
    repository = AsyncMock(get_payment=AsyncMock(return_value=None))
    session = AsyncMock(spec=AsyncSession)

    with patch(
        "services.api.payments.services.get.PaymentRepository",
        return_value=repository,
    ):
        result = await GetPaymentService(session=session).execute(
            payment_id=uuid4()
        )

    assert result is None
