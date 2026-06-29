"""
Test fixtures — shared setup for all tests.

Creates a fresh in-memory SQLite database per test to ensure isolation.
Uses httpx.AsyncClient for testing FastAPI without starting a real server.
"""

import pytest
import pytest_asyncio
import os
from httpx import AsyncClient, ASGITransport

# Use in-memory database for tests
os.environ["DATABASE_PATH"] = ":memory:"

from backend.app.main import app
from backend.app.database import get_db, SCHEMA_SQL, SEED_SQL


@pytest_asyncio.fixture
async def client():
    """
    Provide a test client with a fresh database.

    Each test gets its own database instance, ensuring complete isolation.
    """
    import aiosqlite

    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON")
    await db.executescript(SCHEMA_SQL)
    await db.executescript(SEED_SQL)
    await db.commit()

    async def override_get_db():
        """Yield the shared test database connection."""
        yield db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await db.close()
    app.dependency_overrides.clear()
