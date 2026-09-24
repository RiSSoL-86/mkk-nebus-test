from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app_settings import settings
from core.brokers.rabbitmq import RabbitMQBroker
from core.database import engine
from services.api.common.dependencies import require_api_key
from services.api.urls import router
from services.outbox_publisher.main import OutboxPublisher

broker = RabbitMQBroker()
outbox_publisher = OutboxPublisher(producer=broker.producer)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with broker:
        await broker.setup()
        outbox_publisher.start()
        try:
            yield
        finally:
            await outbox_publisher.stop()
            await engine.dispose()


app = FastAPI(
    title=settings.app.project_name,
    debug=settings.app.debug,
    lifespan=lifespan,
    dependencies=[Depends(require_api_key)],
)
app.include_router(router=router)


@app.get("/health", tags=["service"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
