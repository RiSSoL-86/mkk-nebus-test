from datetime import UTC, datetime
from typing import final, override

from sqlalchemy.ext.asyncio import AsyncSession

from core.common.broker import BaseProducer
from core.common.services import BaseService
from core.outbox.repository import OutboxRepository


@final
class OutboxPublisherService(BaseService[int]):
    """Relays unpublished outbox events to the broker."""

    def __init__(self, session: AsyncSession, producer: BaseProducer) -> None:
        self.session = session
        self._producer = producer

    @override
    async def execute(self, batch_size: int) -> int:
        repository = OutboxRepository(session=self.session)
        async with self.session.begin():
            events = await repository.fetch_unpublished_for_update(
                limit=batch_size
            )
            for event in events:
                await self._producer.publish(
                    payload=event.payload, event_type=event.event_type
                )
                await repository.mark_published(
                    event_id=event.id, published_at=datetime.now(tz=UTC)
                )
            return len(events)
