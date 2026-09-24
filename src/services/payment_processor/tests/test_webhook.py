from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx2 import AsyncClient, ConnectError, Request, Response

from core.payments.choices import Currency, PaymentStatus
from core.payments.entities import PaymentEntity
from services.payment_processor.services.webhook import WebhookSenderService


def _entity() -> PaymentEntity:
    return PaymentEntity(
        amount=Decimal("10.00"),
        currency=Currency.RUB,
        description="test",
        metadata={},
        webhook_url="https://example.com/webhook",
        payment_id=uuid4(),
        status=PaymentStatus.SUCCEEDED,
        created_at=datetime.now(tz=UTC),
        processed_at=datetime.now(tz=UTC),
    )


def _response(status_code: int) -> Response:
    return Response(
        status_code=status_code,
        request=Request(method="POST", url="https://example.com/webhook"),
    )


async def test_webhook_is_delivered_on_2xx():
    client = AsyncMock(spec=AsyncClient)
    client.post.return_value = _response(status_code=200)

    delivered = await WebhookSenderService(client=client).execute(
        payment=_entity()
    )

    assert delivered is True
    client.post.assert_awaited_once()


@pytest.mark.parametrize(
    "outcome",
    [
        _response(status_code=503),
        ConnectError(message="All connection attempts failed"),
    ],
)
async def test_webhook_is_sent_once_and_not_delivered_on_error(outcome):
    client = AsyncMock(spec=AsyncClient)
    client.post.side_effect = [outcome]

    delivered = await WebhookSenderService(client=client).execute(
        payment=_entity()
    )

    assert delivered is False
    client.post.assert_awaited_once()
