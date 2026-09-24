from unittest.mock import AsyncMock, patch
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from core.payments.entities import PaymentData
from services.api.payments.services.create import CreatePaymentService


async def test_delegates_to_repository():
    entity = object()
    repository = AsyncMock(create_with_event=AsyncMock(return_value=entity))
    session = AsyncMock(spec=AsyncSession)
    data = PaymentData(
        amount="10.50",
        currency="RUB",
        description="test",
        webhook_url="https://example.com/webhook",
    )
    key = str(uuid4())

    with patch(
        "services.api.payments.services.create.PaymentRepository",
        return_value=repository,
    ) as repository_factory:
        result = await CreatePaymentService(session=session).execute(
            data=data, idempotency_key=key
        )

    repository_factory.assert_called_once_with(session=session)
    repository.create_with_event.assert_awaited_once_with(
        data=data, idempotency_key=key
    )
    assert result is entity
