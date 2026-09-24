from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app_settings import settings

engine: AsyncEngine = create_async_engine(
    url=settings.db.url,
    echo=settings.app.debug,
    pool_pre_ping=True,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency: one session per request, closed afterwards."""
    async with async_session_factory() as session:
        yield session
