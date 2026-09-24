import asyncio
import logging
from types import TracebackType
from typing import Self, override

from aio_pika.exceptions import AMQPError
from faststream.rabbit import RabbitBroker

from app_settings import settings
from core.brokers.rabbitmq.consumer import RabbitMQConsumer
from core.brokers.rabbitmq.producer import RabbitMQProducer
from core.brokers.rabbitmq.topology import (
    DLQ_EXCHANGE,
    PAYMENTS_DLQ_QUEUE,
    PAYMENTS_EXCHANGE,
    PAYMENTS_NEW_QUEUE,
    RETRY_EXCHANGE,
    retry_queue,
)
from core.common.broker.broker import BaseBroker
from core.payments.event_types import PAYMENTS_ROUTING_KEY

logger = logging.getLogger(__name__)


class RabbitMQBroker(BaseBroker):
    """RabbitMQ connection with its producer and consumer."""

    def __init__(self) -> None:
        self.raw_broker = RabbitBroker(
            url=settings.brokers.rabbitmq.url.get_secret_value()
        )
        self.producer = RabbitMQProducer(raw_broker=self.raw_broker)
        self.consumer = RabbitMQConsumer(raw_broker=self.raw_broker)

    @override
    async def connect(self) -> None:
        """Connect with retries to wait for a broker that is still starting."""
        attempts = settings.brokers.rabbitmq.connect_attempts
        for attempt in range(1, attempts + 1):
            try:
                await self.raw_broker.connect()
            except (AMQPError, OSError) as error:
                if attempt == attempts:
                    raise
                logger.warning(
                    msg=f"RabbitMQ connection failed "
                    f"(attempt {attempt}/{attempts}): {error!r}"
                )
                await asyncio.sleep(
                    delay=settings.brokers.rabbitmq.connect_retry_delay_seconds
                )
            else:
                return

    @override
    async def setup(self) -> None:
        """Declare the full topology so no message hits a missing queue."""
        payments_exchange = await self.raw_broker.declare_exchange(
            exchange=PAYMENTS_EXCHANGE
        )
        retry_exchange = await self.raw_broker.declare_exchange(
            exchange=RETRY_EXCHANGE
        )
        dlq_exchange = await self.raw_broker.declare_exchange(
            exchange=DLQ_EXCHANGE
        )

        new_queue = await self.raw_broker.declare_queue(
            queue=PAYMENTS_NEW_QUEUE
        )
        await new_queue.bind(
            exchange=payments_exchange, routing_key=PAYMENTS_ROUTING_KEY
        )
        dlq_queue = await self.raw_broker.declare_queue(
            queue=PAYMENTS_DLQ_QUEUE
        )
        await dlq_queue.bind(
            exchange=dlq_exchange, routing_key=PAYMENTS_ROUTING_KEY
        )

        for attempt in range(1, settings.processing.retry.max_attempts):
            queue = retry_queue(attempt=attempt)
            declared_queue = await self.raw_broker.declare_queue(queue=queue)
            await declared_queue.bind(
                exchange=retry_exchange, routing_key=queue.name
            )

    @override
    async def start(self) -> None:
        await self.raw_broker.start()

    @override
    async def stop(self) -> None:
        await self.raw_broker.stop()

    @override
    async def __aenter__(self) -> Self:
        await self.connect()
        await self.raw_broker.__aenter__()
        return self

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.raw_broker.__aexit__(exc_type, exc_value, traceback)
