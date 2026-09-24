from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from faststream.rabbit import TestRabbitBroker

from core.brokers.rabbitmq import RabbitMQBroker
from core.brokers.rabbitmq.topology import (
    PAYMENTS_EXCHANGE,
    PAYMENTS_NEW_QUEUE,
    RETRY_COUNT_HEADER,
)
from services.payment_processor.errors import WebhookDeliveryError
from services.payment_processor.handlers import PaymentNewHandler


class _FakeSessionContext:
    def __init__(self) -> None:
        self.session = AsyncMock()

    async def __aenter__(self) -> AsyncMock:
        return self.session

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


async def test_handler_processes_payment_successfully(monkeypatch):
    broker = RabbitMQBroker()
    handler = PaymentNewHandler(producer=broker.producer)
    broker.consumer.subscribe(handler=handler.handle)
    process_service = AsyncMock()
    monkeypatch.setattr(
        "services.payment_processor.handlers.ProcessPaymentService",
        lambda session, webhook_sender: process_service,
    )
    monkeypatch.setattr(
        "services.payment_processor.handlers.async_session_factory",
        _FakeSessionContext,
    )
    payment_id = uuid4()

    async with TestRabbitBroker(broker.raw_broker) as test_broker:
        await test_broker.publish(
            message={"payment_id": str(payment_id)},
            queue=PAYMENTS_NEW_QUEUE,
            exchange=PAYMENTS_EXCHANGE,
        )

    process_service.execute.assert_awaited_once_with(payment_id=payment_id)


@pytest.mark.parametrize(
    "error",
    [RuntimeError("gateway down"), WebhookDeliveryError(uuid4())],
)
async def test_handler_reroutes_to_retry_on_failure(monkeypatch, error):
    broker = RabbitMQBroker()
    handler = PaymentNewHandler(producer=broker.producer)
    broker.consumer.subscribe(handler=handler.handle)
    process_service = AsyncMock()
    process_service.execute.side_effect = error
    monkeypatch.setattr(
        "services.payment_processor.handlers.ProcessPaymentService",
        lambda session, webhook_sender: process_service,
    )
    monkeypatch.setattr(
        "services.payment_processor.handlers.async_session_factory",
        _FakeSessionContext,
    )
    reroute_service = AsyncMock()
    reroute_producers = []

    def fake_reroute_service(producer):
        reroute_producers.append(producer)
        return reroute_service

    monkeypatch.setattr(
        "services.payment_processor.handlers.ReroutePaymentService",
        fake_reroute_service,
    )
    payment_id = uuid4()

    async with TestRabbitBroker(broker.raw_broker) as test_broker:
        await test_broker.publish(
            message={"payment_id": str(payment_id)},
            queue=PAYMENTS_NEW_QUEUE,
            exchange=PAYMENTS_EXCHANGE,
            headers={RETRY_COUNT_HEADER: 2},
        )

    process_service.execute.assert_awaited_once_with(payment_id=payment_id)
    assert reroute_producers == [broker.producer]
    reroute_service.execute.assert_awaited_once()
    assert reroute_service.execute.await_args is not None
    _, kwargs = reroute_service.execute.await_args
    assert kwargs["event"].payment_id == payment_id
    assert kwargs["retry_count"] == 2
