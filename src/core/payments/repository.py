from datetime import datetime
from typing import final
from uuid import UUID, uuid7

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from core.common.repository import BaseRepository
from core.outbox.models import OutboxEvent
from core.payments.choices import PaymentStatus
from core.payments.entities import PaymentData, PaymentEntity
from core.payments.errors import IdempotencyConflictError
from core.payments.event_types import PAYMENTS_ROUTING_KEY
from core.payments.models import Payment


@final
class PaymentRepository(BaseRepository[Payment, UUID]):
    model = Payment

    @staticmethod
    def _to_entity(payment: Payment) -> PaymentEntity:
        return PaymentEntity(
            payment_id=payment.id,
            amount=payment.amount,
            currency=payment.currency,
            description=payment.description,
            metadata=payment.extra_data,
            webhook_url=payment.webhook_url,
            status=payment.status,
            created_at=payment.created_at,
            processed_at=payment.processed_at,
            webhook_delivered_at=payment.webhook_delivered_at,
        )

    async def create_with_event(
        self, data: PaymentData, idempotency_key: str
    ) -> PaymentEntity:
        async with self.session.begin():
            statement = (
                insert(Payment)
                .values(
                    id=uuid7(),
                    amount=data.amount,
                    currency=data.currency,
                    description=data.description,
                    extra_data=data.metadata,
                    webhook_url=str(data.webhook_url),
                    status=PaymentStatus.PENDING,
                    idempotency_key=idempotency_key,
                )
                .on_conflict_do_nothing(index_elements=["idempotency_key"])
                .returning(Payment)
            )
            payment = (
                await self.session.scalars(statement=statement)
            ).one_or_none()
            if payment is None:
                existing = (
                    await self.session.scalars(
                        statement=select(Payment).where(
                            Payment.idempotency_key == idempotency_key
                        )
                    )
                ).one()
                entity = self._to_entity(payment=existing)
                original = PaymentData.model_validate(obj=entity.model_dump())
                if original != data:
                    raise IdempotencyConflictError
                return entity

            self.session.add(
                instance=OutboxEvent(
                    payment_id=payment.id,
                    event_type=PAYMENTS_ROUTING_KEY,
                    payload={"payment_id": str(payment.id)},
                )
            )
            await self.session.flush()
            return self._to_entity(payment=payment)

    async def get_payment(self, payment_id: UUID) -> PaymentEntity | None:
        async with self.session.begin():
            payment = await self.session.get(entity=Payment, ident=payment_id)
            return self._to_entity(payment=payment) if payment else None

    async def mark_processed(
        self,
        payment_id: UUID,
        status: PaymentStatus,
        processed_at: datetime,
    ) -> PaymentEntity | None:
        """Atomically move a PENDING payment to a terminal status."""
        async with self.session.begin():
            statement = (
                update(Payment)
                .where(
                    Payment.id == payment_id,
                    Payment.status == PaymentStatus.PENDING,
                )
                .values(status=status, processed_at=processed_at)
                .returning(Payment)
            )
            payment = (
                await self.session.scalars(statement=statement)
            ).one_or_none()
            return self._to_entity(payment=payment) if payment else None

    async def mark_webhook_delivered(
        self, payment_id: UUID, delivered_at: datetime
    ) -> None:
        async with self.session.begin():
            await self.session.execute(
                statement=update(Payment)
                .where(Payment.id == payment_id)
                .values(webhook_delivered_at=delivered_at)
            )
