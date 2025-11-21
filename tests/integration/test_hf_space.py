"""Integration tests for Hugging Face Space wrapper."""

import asyncio
import subprocess
import time
import httpx
import pytest


def test_app_imports():
    """Test that app.py imports without errors."""
    import app
    assert hasattr(app, 'main')
    assert hasattr(app, 'start_fastapi_server')
    assert hasattr(app, 'wait_for_fastapi_ready')
    assert hasattr(app, 'create_gradio_interface')


def test_gradio_interface_creation():
    """Test that Gradio interface can be created."""
    from app import create_gradio_interface
    
    interface = create_gradio_interface()
    assert interface is not None


def test_environment_check():
    """Test environment variable checking."""
    from app import check_environment
    
    html = check_environment()
    assert "Environment Configuration" in html
    assert "OPENAI_API_KEY" in html
    assert "ANTHROPIC_API_KEY" in html


@pytest.mark.asyncio
async def test_fastapi_server_can_start():
    """Test that FastAPI server can start and respond to health checks."""
    from app import start_fastapi_server, wait_for_fastapi_ready, kill_existing_uvicorn
    
    # Kill any existing servers
    kill_existing_uvicorn()
    time.sleep(2)
    
    # Start server
    process = start_fastapi_server()
    
    try:
        # Wait for it to be ready
        is_ready = await wait_for_fastapi_ready(max_wait=30)
        assert is_ready, "FastAPI server did not become ready"
        
        # Test health endpoint
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:7860/health", timeout=5.0)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
        
    finally:
        # Clean up
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        kill_existing_uvicorn()


def test_kill_existing_uvicorn():
    """Test that kill_existing_uvicorn doesn't error."""
    from app import kill_existing_uvicorn
    
    # Should not raise an error even if no processes exist
    kill_existing_uvicorn()
