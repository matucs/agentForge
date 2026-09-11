from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.session import engine, get_session
from app.main import app


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Each test runs inside a transaction that is rolled back afterwards, so
    tests can hit the real Postgres instance (per project rule: no mocked
    persistence) without leaving data behind or depending on test order."""
    connection = await engine.connect()
    transaction = await connection.begin()
    session_factory = async_sessionmaker(bind=connection, expire_on_commit=False)
    session = session_factory()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session

    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
