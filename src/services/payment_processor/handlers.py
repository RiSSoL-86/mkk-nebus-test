import logging
from typing import Any, final

from httpx2 import AsyncClient

from core.common.broker import BaseProducer
from core.database.engine import async_session_factory
from services.payment_processor.errors import WebhookDeliveryError
from services.payment_processor.schemas import PaymentNewEvent
from services.payment_processor.services.processing import (
    ProcessPaymentService,
)
from services.payment_processor.services.retry import ReroutePaymentService
from services.payment_processor.services.webhook import WebhookSenderService

logger = logging.getLogger(__name__)


@final
class PaymentNewHandler:
    """Processes payments.new events and reroutes failed ones."""

    def __init__(self, producer: BaseProducer) -> None:
        self._producer = producer

    async def handle(self, payload: dict[str, Any], retry_count: int) -> None:
        event = PaymentNewEvent.model_validate(obj=payload)
        try:
            async with (
                AsyncClient() as client,
                async_session_factory() as session,
            ):
                service = ProcessPaymentService(
                    session=session,
                    webhook_sender=WebhookSenderService(client=client),
                )
                await service.execute(payment_id=event.payment_id)
        except WebhookDeliveryError:
            logger.warning(
                msg=f"Webhook not delivered for payment {event.payment_id} "
                f"(attempt {retry_count + 1})"
            )
        except Exception:
            logger.exception(
                msg=f"Failed to process payment {event.payment_id} "
                f"(attempt {retry_count + 1})"
            )
        else:
            return
        await ReroutePaymentService(producer=self._producer).execute(
            event=event, retry_count=retry_count
        )
