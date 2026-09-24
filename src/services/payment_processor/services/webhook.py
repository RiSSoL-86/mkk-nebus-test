import logging
from typing import final, override

from httpx2 import AsyncClient, HTTPError

from app_settings import settings
from core.common.services import BaseService
from core.payments.entities import PaymentEntity

logger = logging.getLogger(__name__)


@final
class WebhookSenderService(BaseService[bool]):
    """Delivers a payment status notification; retries go via the broker."""

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    @override
    async def execute(self, payment: PaymentEntity) -> bool:
        payload = {
            "payment_id": str(payment.payment_id),
            "status": payment.status.value,
            "amount": str(payment.amount),
            "currency": payment.currency.value,
            "processed_at": (
                payment.processed_at.isoformat()
                if payment.processed_at is not None
                else None
            ),
        }
        try:
            response = await self._client.post(
                url=str(payment.webhook_url),
                json=payload,
                timeout=settings.processing.webhook.timeout_seconds,
            )
            response.raise_for_status()
        except HTTPError as error:
            logger.warning(
                msg=f"Webhook delivery failed for payment "
                f"{payment.payment_id}: {error!r}"
            )
            return False
        return True
