from unittest.mock import AsyncMock

from services.payment_processor import main


async def test_setup_declares_topology(monkeypatch):
    setup_mock = AsyncMock()
    monkeypatch.setattr(main.broker, "setup", setup_mock)

    await main.setup()

    setup_mock.assert_awaited_once_with()
