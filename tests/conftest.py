"""Pytest configuration and fixtures."""

import pytest
import asyncio
from src.services.smart_sql import SmartSQLService


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def sql_service():
    """Create a test database."""
    service = SmartSQLService("sqlite+aiosqlite:///:memory:")
    await service.init_db()
    yield service
    # Cleanup
    await service.engine.dispose()


@pytest.fixture(scope="function")
async def initialized_app():
    """Initialize FastAPI app with test database."""
    from src.main import app
    from src.api.routes import sql_service
    
    # Initialize test database
    await sql_service.init_db()
    
    yield app
    
    # Cleanup
    await sql_service.engine.dispose()
