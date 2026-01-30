import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.redis import redis_client

# Define event_loop fixture to match scope of async fixtures if needed.
# Since pytest-asyncio 0.23+, loop scope config is handled in pyproject.toml or ini.
# But providing a session-scoped loop for session fixtures is often needed.
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    # We do NOT override get_db, so the app uses its own connection pool defined in src.database
    # against the real DATABASE_URL (localhost docker).
    
    # We rely on app lifespan to connect / disconnect Redis.
    # httpx.AsyncClient(transport=ASGITransport(app=app)) supports lifespan context manager?
    # No, we need to use LifespanManager or enter context manually if we want lifespan events.
    # However, create_async_engine is lazy, so DB might work.
    # Redis needs explicit connect.
    # Let's use ASGITransport which usually does not trigger lifespan automatically unless using TestClient/LifespanManager
    # BUT, we can just manually trigger startup/shutdown or use `async with app.router.lifespan_context(app):`
    # actually, modern httpx + fastapi:
    
    async with ASGITransport(app=app) as transport:
         async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
