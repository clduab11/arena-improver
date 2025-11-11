"""Tests for SmartSQL service."""

import pytest
import os
import tempfile
from pathlib import Path
from src.services.smart_sql import SmartSQLService


@pytest.mark.asyncio
async def test_init_db_creates_directory():
    """Test that init_db creates the necessary directory for SQLite database."""
    # Use a temporary directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_dir", "test.db")
        db_url = f"sqlite+aiosqlite:///{db_path}"
        
        # Verify directory doesn't exist yet
        db_dir = os.path.dirname(db_path)
        assert not os.path.exists(db_dir)
        
        # Create service and initialize
        service = SmartSQLService(db_url)
        await service.init_db()
        
        # Verify directory was created
        assert os.path.exists(db_dir)
        assert os.path.isdir(db_dir)
        
        # Cleanup
        await service.engine.dispose()


@pytest.mark.asyncio
async def test_init_db_with_memory_database():
    """Test that init_db works with in-memory database without creating directories."""
    service = SmartSQLService("sqlite+aiosqlite:///:memory:")
    
    # Should not raise any errors
    await service.init_db()
    
    # Cleanup
    await service.engine.dispose()


@pytest.mark.asyncio
async def test_init_db_with_existing_directory():
    """Test that init_db works when directory already exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = os.path.join(tmpdir, "existing_dir")
        os.makedirs(db_dir)
        
        db_path = os.path.join(db_dir, "test.db")
        db_url = f"sqlite+aiosqlite:///{db_path}"
        
        # Create service and initialize
        service = SmartSQLService(db_url)
        await service.init_db()
        
        # Verify directory still exists
        assert os.path.exists(db_dir)
        assert os.path.isdir(db_dir)
        
        # Cleanup
        await service.engine.dispose()
