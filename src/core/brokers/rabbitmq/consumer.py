from typing import Any, override

from faststream.rabbit import Channel, RabbitBroker
from faststream.rabbit.annotations import RabbitMessage

from app_settings import settings
from core.brokers.rabbitmq.topology import (
    PAYMENTS_EXCHANGE,
    PAYMENTS_NEW_QUEUE,
    RETRY_COUNT_HEADER,
)
from core.common.broker.consumer import BaseConsumer, MessageHandler


class RabbitMQConsumer(BaseConsumer):
    """Delivers payments.new messages to the handler."""

    def __init__(self, raw_broker: RabbitBroker) -> None:
        self._raw_broker = raw_broker

    @override
    def subscribe(self, handler: MessageHandler) -> None:
        @self._raw_broker.subscriber(
            queue=PAYMENTS_NEW_QUEUE,
            exchange=PAYMENTS_EXCHANGE,
            channel=Channel(
                prefetch_count=settings.brokers.rabbitmq.prefetch_count
            ),
        )
        async def _on_message(
            payload: dict[str, Any], message: RabbitMessage
        ) -> None:
            retry_count = int(message.headers.get(RETRY_COUNT_HEADER, 0))
            await handler(payload, retry_count)
