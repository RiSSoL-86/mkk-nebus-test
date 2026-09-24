from sqlalchemy.ext.asyncio import AsyncSession

from core.database.engine import get_session


async def test_get_session_yields_and_closes_a_session():
    generator = get_session()
    session = await anext(generator)
    try:
        assert isinstance(session, AsyncSession)
        assert session.is_active
    finally:
        await generator.aclose()
