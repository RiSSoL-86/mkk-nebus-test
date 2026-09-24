from unittest.mock import AsyncMock, patch

import pytest
from aio_pika.exceptions import AMQPConnectionError
from faststream.rabbit import TestRabbitBroker

from app_settings import settings
from core.brokers.rabbitmq import RabbitMQBroker
from core.brokers.rabbitmq.topology import (
    DLQ_EXCHANGE,
    PAYMENTS_DLQ_QUEUE,
    PAYMENTS_EXCHANGE,
    PAYMENTS_NEW_QUEUE,
    RETRY_COUNT_HEADER,
    RETRY_EXCHANGE,
    retry_queue,
)
from core.payments.event_types import PAYMENTS_ROUTING_KEY


async def test_publish_sends_to_the_payments_exchange():
    broker = RabbitMQBroker()

    with patch.object(broker.raw_broker, "publish", AsyncMock()) as publish:
        await broker.producer.publish(
            payload={"payment_id": "1"}, event_type=PAYMENTS_ROUTING_KEY
        )

    publish.assert_awaited_once_with(
        message={"payment_id": "1"},
        exchange=PAYMENTS_EXCHANGE,
        routing_key=PAYMENTS_ROUTING_KEY,
        persist=True,
    )


async def test_retry_sends_to_the_queue_of_its_attempt():
    broker = RabbitMQBroker()

    with patch.object(broker.raw_broker, "publish", AsyncMock()) as publish:
        await broker.producer.retry(payload={"payment_id": "1"}, attempt=2)

    publish.assert_awaited_once_with(
        message={"payment_id": "1"},
        exchange=RETRY_EXCHANGE,
        routing_key="payments.new.retry.2",
        headers={RETRY_COUNT_HEADER: 2},
        persist=True,
    )


def test_retry_queue_ttl_doubles_on_each_attempt():
    base_ms = int(settings.processing.retry.backoff_base_seconds * 1000)

    assert retry_queue(attempt=1).arguments["x-message-ttl"] == base_ms
    assert retry_queue(attempt=2).arguments["x-message-ttl"] == base_ms * 2
    assert retry_queue(attempt=3).arguments["x-message-ttl"] == base_ms * 4


def test_payments_queue_dead_letters_rejected_messages_to_the_dlq():
    arguments = PAYMENTS_NEW_QUEUE.arguments
    assert arguments["x-dead-letter-exchange"] == DLQ_EXCHANGE.name
    assert arguments["x-dead-letter-routing-key"] == PAYMENTS_ROUTING_KEY


async def test_dead_letter_sends_to_the_dlq_exchange():
    broker = RabbitMQBroker()

    with patch.object(broker.raw_broker, "publish", AsyncMock()) as publish:
        await broker.producer.dead_letter(
            payload={"payment_id": "1"}, attempt=3
        )

    publish.assert_awaited_once_with(
        message={"payment_id": "1"},
        exchange=DLQ_EXCHANGE,
        routing_key=PAYMENTS_ROUTING_KEY,
        headers={RETRY_COUNT_HEADER: 3},
        persist=True,
    )


async def test_setup_declares_the_whole_topology():
    broker = RabbitMQBroker()

    async with TestRabbitBroker(broker.raw_broker) as test_broker:
        with (
            patch.object(
                test_broker,
                "declare_queue",
                wraps=test_broker.declare_queue,
            ) as declare_queue,
            patch.object(
                test_broker,
                "declare_exchange",
                wraps=test_broker.declare_exchange,
            ) as declare_exchange,
        ):
            await broker.setup()

    declared_queue_names = {
        call.kwargs["queue"].name for call in declare_queue.await_args_list
    }
    declared_exchange_names = {
        call.kwargs["exchange"].name
        for call in declare_exchange.await_args_list
    }
    retry_queue_names = {
        retry_queue(attempt=attempt).name
        for attempt in range(1, settings.processing.retry.max_attempts)
    }
    assert declared_queue_names == {
        PAYMENTS_NEW_QUEUE.name,
        PAYMENTS_DLQ_QUEUE.name,
        *retry_queue_names,
    }
    assert declared_exchange_names == {
        PAYMENTS_EXCHANGE.name,
        RETRY_EXCHANGE.name,
        DLQ_EXCHANGE.name,
    }


async def test_connect_retries_until_the_broker_is_up(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr("core.brokers.rabbitmq.broker.asyncio.sleep", sleep)
    broker = RabbitMQBroker()

    with patch.object(
        broker.raw_broker,
        "connect",
        AsyncMock(side_effect=[AMQPConnectionError(), OSError(), None]),
    ) as connect:
        await broker.connect()

    assert connect.await_count == 3
    assert sleep.await_count == 2


async def test_connect_gives_up_after_the_last_attempt(monkeypatch):
    monkeypatch.setattr(
        "core.brokers.rabbitmq.broker.asyncio.sleep", AsyncMock()
    )
    broker = RabbitMQBroker()

    with (
        patch.object(
            broker.raw_broker,
            "connect",
            AsyncMock(side_effect=AMQPConnectionError()),
        ) as connect,
        pytest.raises(AMQPConnectionError),
    ):
        await broker.connect()

    assert connect.await_count == settings.brokers.rabbitmq.connect_attempts


async def test_start_stop_and_context_manager_delegate_to_the_raw_broker():
    broker = RabbitMQBroker()

    with (
        patch.object(broker.raw_broker, "connect", AsyncMock()) as connect,
        patch.object(broker.raw_broker, "start", AsyncMock()) as start,
        patch.object(broker.raw_broker, "stop", AsyncMock()) as stop,
        patch.object(
            broker.raw_broker,
            "__aenter__",
            AsyncMock(return_value=broker.raw_broker),
        ) as aenter,
        patch.object(
            broker.raw_broker, "__aexit__", AsyncMock(return_value=None)
        ) as aexit,
    ):
        await broker.start()
        await broker.stop()
        start.assert_awaited_once()
        stop.assert_awaited_once()

        async with broker as entered:
            assert entered is broker
        connect.assert_awaited_once()
        aenter.assert_awaited_once()
        aexit.assert_awaited_once_with(None, None, None)
