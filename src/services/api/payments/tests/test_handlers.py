from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from core.payments.choices import PaymentStatus
from core.payments.entities import PaymentData, PaymentEntity
from core.payments.errors import IdempotencyConflictError
from core.payments.repository import PaymentRepository
from main import app

DATA = {
    "amount": "100.50",
    "currency": "RUB",
    "description": "Test payment",
    "metadata": {"order_id": "42"},
    "webhook_url": "https://example.com/webhook",
}
HEADERS = {"X-API-Key": "test-api-key"}


@pytest.fixture
async def client():
    session = AsyncMock(spec=AsyncSession)
    repository = AsyncMock(spec=PaymentRepository)
    entity = PaymentEntity(
        **DATA,
        payment_id=uuid4(),
        status=PaymentStatus.PENDING,
        created_at=datetime.now(tz=UTC),
    )
    repository.create_with_event.return_value = entity
    repository.get_payment.return_value = entity
    app.dependency_overrides[get_session] = lambda: session
    broker = AsyncMock()
    broker.__aenter__.return_value = broker
    broker.__aexit__.return_value = False
    try:
        with (
            patch(
                "services.api.payments.services.create.PaymentRepository",
                return_value=repository,
            ) as create_repository,
            patch(
                "services.api.payments.services.get.PaymentRepository",
                return_value=repository,
            ) as get_repository,
            patch("main.broker", broker),
            patch("main.outbox_publisher.start"),
            patch("main.outbox_publisher.stop", AsyncMock()),
        ):
            async with app.router.lifespan_context(app):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as test_client:
                    yield test_client, repository, entity
            for factory in (create_repository, get_repository):
                for call in factory.call_args_list:
                    assert call.kwargs == {"session": session}
            assert not session.mock_calls
    finally:
        app.dependency_overrides.clear()


async def test_auth_and_validation(client):
    http, repository, _ = client
    assert (await http.get("/health")).status_code == 401
    assert (await http.get("/health", headers=HEADERS)).status_code == 200
    assert (await http.post("/api/v1/payments", json=DATA)).status_code == 401
    assert (
        await http.post("/api/v1/payments", headers=HEADERS, json=DATA)
    ).status_code == 422
    assert (
        await http.post(
            "/api/v1/payments",
            headers={**HEADERS, "Idempotency-Key": "order"},
            json={**DATA, "amount": "-1"},
        )
    ).status_code == 422
    repository.create_with_event.assert_not_awaited()


async def test_create_get_and_missing(client):
    http, repository, entity = client
    response = await http.post(
        "/api/v1/payments",
        headers={**HEADERS, "Idempotency-Key": "order"},
        json=DATA,
    )
    assert response.status_code == 202
    assert response.json()["payment_id"] == str(entity.payment_id)
    repository.create_with_event.assert_awaited_once_with(
        data=PaymentData.model_validate(DATA), idempotency_key="order"
    )
    response = await http.get(
        f"/api/v1/payments/{entity.payment_id}", headers=HEADERS
    )
    assert response.status_code == 200
    assert response.json()["metadata"] == DATA["metadata"]
    repository.get_payment.return_value = None
    assert (
        await http.get(f"/api/v1/payments/{uuid4()}", headers=HEADERS)
    ).status_code == 404


async def test_conflicting_key(client):
    http, repository, _ = client
    repository.create_with_event.side_effect = IdempotencyConflictError
    assert (
        await http.post(
            "/api/v1/payments",
            headers={**HEADERS, "Idempotency-Key": "order"},
            json=DATA,
        )
    ).status_code == 409
