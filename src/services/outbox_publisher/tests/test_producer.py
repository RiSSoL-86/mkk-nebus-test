import asyncio
from unittest.mock import AsyncMock

import pytest

from app_settings import settings
from services.outbox_publisher.main import OutboxPublisher


async def test_stop_cancels_the_running_task():
    publisher = OutboxPublisher(producer=AsyncMock())
    publisher.start()
    assert publisher._task is not None
    task = publisher._task

    await publisher.stop()

    assert task.cancelled()


async def test_stop_is_a_noop_when_never_started():
    publisher = OutboxPublisher(producer=AsyncMock())

    await publisher.stop()


class _FakeSessionContext:
    def __init__(self) -> None:
        self.session = AsyncMock()

    async def __aenter__(self) -> AsyncMock:
        return self.session

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


async def test_run_polls_until_cancelled(monkeypatch):
    executed = []

    class _FakePublisherService:
        def __init__(self, session: object, producer: object) -> None:
            pass

        async def execute(self, batch_size: int) -> int:
            executed.append(batch_size)
            return 0

    monkeypatch.setattr(
        "services.outbox_publisher.main.OutboxPublisherService",
        _FakePublisherService,
    )
    monkeypatch.setattr(
        "services.outbox_publisher.main.async_session_factory",
        _FakeSessionContext,
    )

    sleep_calls = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        if len(sleep_calls) >= 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(
        "services.outbox_publisher.main.asyncio.sleep", fake_sleep
    )

    publisher = OutboxPublisher(producer=AsyncMock())
    publisher.start()
    assert publisher._task is not None
    with pytest.raises(asyncio.CancelledError):
        await publisher._task

    assert len(executed) == 2
    assert (
        sleep_calls == [settings.processing.outbox.poll_interval_seconds] * 2
    )


async def test_run_logs_and_continues_after_failure(monkeypatch):
    class _FailingPublisherService:
        def __init__(self, session: object, producer: object) -> None:
            pass

        async def execute(self, batch_size: int) -> int:
            raise RuntimeError("boom")

    monkeypatch.setattr(
        "services.outbox_publisher.main.OutboxPublisherService",
        _FailingPublisherService,
    )
    monkeypatch.setattr(
        "services.outbox_publisher.main.async_session_factory",
        _FakeSessionContext,
    )

    sleep_calls = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        raise asyncio.CancelledError

    monkeypatch.setattr(
        "services.outbox_publisher.main.asyncio.sleep", fake_sleep
    )

    publisher = OutboxPublisher(producer=AsyncMock())
    publisher.start()
    assert publisher._task is not None
    with pytest.raises(asyncio.CancelledError):
        await publisher._task

    assert sleep_calls == [settings.processing.outbox.poll_interval_seconds]
