from typing import Any, override

from faststream.rabbit import RabbitBroker

from core.brokers.rabbitmq.topology import (
    DLQ_EXCHANGE,
    PAYMENTS_EXCHANGE,
    RETRY_COUNT_HEADER,
    RETRY_EXCHANGE,
    retry_queue,
)
from core.common.broker.producer import BaseProducer
from core.payments.event_types import PAYMENTS_ROUTING_KEY


class RabbitMQProducer(BaseProducer):
    """Publishes payment events to RabbitMQ exchanges."""

    def __init__(self, raw_broker: RabbitBroker) -> None:
        self._raw_broker = raw_broker

    @override
    async def publish(self, payload: dict[str, Any], event_type: str) -> None:
        await self._raw_broker.publish(
            message=payload,
            exchange=PAYMENTS_EXCHANGE,
            routing_key=event_type,
            persist=True,
        )

    @override
    async def retry(self, payload: dict[str, Any], attempt: int) -> None:
        await self._raw_broker.publish(
            message=payload,
            exchange=RETRY_EXCHANGE,
            routing_key=retry_queue(attempt=attempt).name,
            headers={RETRY_COUNT_HEADER: attempt},
            persist=True,
        )

    @override
    async def dead_letter(self, payload: dict[str, Any], attempt: int) -> None:
        await self._raw_broker.publish(
            message=payload,
            exchange=DLQ_EXCHANGE,
            routing_key=PAYMENTS_ROUTING_KEY,
            headers={RETRY_COUNT_HEADER: attempt},
            persist=True,
        )
