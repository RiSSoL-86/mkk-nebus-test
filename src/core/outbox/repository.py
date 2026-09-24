from collections.abc import Sequence
from datetime import datetime
from typing import final
from uuid import UUID

from sqlalchemy import select, update

from core.common.repository import BaseRepository
from core.outbox.models import OutboxEvent


@final
class OutboxRepository(BaseRepository[OutboxEvent, UUID]):
    model = OutboxEvent

    async def fetch_unpublished_for_update(
        self, limit: int
    ) -> Sequence[OutboxEvent]:
        """Lock a batch of unpublished events, skipping already-locked rows."""
        statement = (
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return (await self.session.scalars(statement=statement)).all()

    async def mark_published(
        self, event_id: UUID, published_at: datetime
    ) -> None:
        await self.session.execute(
            statement=update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(published_at=published_at)
        )
