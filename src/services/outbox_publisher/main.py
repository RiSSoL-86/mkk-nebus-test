import asyncio
import logging
from contextlib import suppress
from typing import final

from app_settings import settings
from core.common.broker import BaseProducer
from core.database.engine import async_session_factory
from services.outbox_publisher.services.publisher import OutboxPublisherService

logger = logging.getLogger(__name__)


@final
class OutboxPublisher:
    """Background task that relays outbox events to the broker."""

    def __init__(self, producer: BaseProducer) -> None:
        self._producer = producer
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        async def run() -> None:
            interval = settings.processing.outbox.poll_interval_seconds
            batch_size = settings.processing.outbox.batch_size
            while True:
                try:
                    async with async_session_factory() as session:
                        published = await OutboxPublisherService(
                            session=session, producer=self._producer
                        ).execute(batch_size=batch_size)
                    if published < batch_size:
                        await asyncio.sleep(delay=interval)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(msg="Outbox publisher iteration failed")
                    await asyncio.sleep(delay=interval)

        self._task = asyncio.create_task(coro=run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
