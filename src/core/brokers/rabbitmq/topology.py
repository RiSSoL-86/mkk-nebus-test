from typing import Final

from faststream.rabbit import ExchangeType, RabbitExchange, RabbitQueue

from app_settings import settings
from core.payments.event_types import PAYMENTS_ROUTING_KEY

RETRY_COUNT_HEADER: Final = "x-retry-count"

PAYMENTS_EXCHANGE: Final = RabbitExchange(
    name="payments", type=ExchangeType.DIRECT, durable=True
)
RETRY_EXCHANGE: Final = RabbitExchange(
    name="payments.retry", type=ExchangeType.DIRECT, durable=True
)
DLQ_EXCHANGE: Final = RabbitExchange(
    name="payments.dlq", type=ExchangeType.DIRECT, durable=True
)

PAYMENTS_NEW_QUEUE: Final = RabbitQueue(
    name="payments.new",
    durable=True,
    routing_key=PAYMENTS_ROUTING_KEY,
    arguments={
        "x-dead-letter-exchange": DLQ_EXCHANGE.name,
        "x-dead-letter-routing-key": PAYMENTS_ROUTING_KEY,
    },
)
PAYMENTS_DLQ_QUEUE: Final = RabbitQueue(
    name="payments.new.dlq", durable=True, routing_key=PAYMENTS_ROUTING_KEY
)


def retry_queue(attempt: int) -> RabbitQueue:
    """Per-attempt delay queue with exponential backoff TTL."""
    backoff_seconds = settings.processing.retry.backoff_base_seconds * (
        2 ** (attempt - 1)
    )
    name = f"payments.new.retry.{attempt}"
    return RabbitQueue(
        name=name,
        durable=True,
        routing_key=name,
        arguments={
            "x-message-ttl": int(backoff_seconds * 1000),
            "x-dead-letter-exchange": PAYMENTS_EXCHANGE.name,
            "x-dead-letter-routing-key": PAYMENTS_ROUTING_KEY,
        },
    )
