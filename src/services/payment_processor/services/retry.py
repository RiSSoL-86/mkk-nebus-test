import logging
from typing import final, override

from app_settings import settings
from core.common.broker import BaseProducer
from core.common.services import BaseService
from services.payment_processor.schemas import PaymentNewEvent

logger = logging.getLogger(__name__)


@final
class ReroutePaymentService(BaseService[None]):
    """Sends a failed payment event to the retry queue or to the DLQ."""

    def __init__(self, producer: BaseProducer) -> None:
        self._producer = producer

    @override
    async def execute(self, event: PaymentNewEvent, retry_count: int) -> None:
        next_count = retry_count + 1
        body = event.model_dump(mode="json")

        if next_count >= settings.processing.retry.max_attempts:
            await self._producer.dead_letter(payload=body, attempt=next_count)
            logger.error(
                msg=f"Payment {event.payment_id} moved to the DLQ "
                f"after {next_count} attempts"
            )
            return

        await self._producer.retry(payload=body, attempt=next_count)
