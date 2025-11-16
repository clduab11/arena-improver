"""Integration tests for health check and monitoring endpoints."""

import pytest
from httpx import AsyncClient
from src.main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test root endpoint returns service information."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    data = response.json()

    assert data["service"] == "Arena Improver"
    assert "version" in data
    assert "description" in data
    assert "docs" in data


@pytest.mark.asyncio
async def test_health_check_endpoint():
    """Test basic health check endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_liveness_probe():
    """Test liveness probe endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "alive"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_readiness_probe():
    """Test readiness probe endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health/ready")

    # Should return 200 if database is initialized
    assert response.status_code in [200, 503]

    data = response.json()

    if response.status_code == 200:
        assert data["status"] == "ready"
        assert "checks" in data
        assert "database" in data["checks"]
    else:
        assert data["status"] == "not_ready"


@pytest.mark.asyncio
async def test_metrics_endpoint():
    """Test metrics endpoint returns monitoring data."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    data = response.json()

    # Check structure
    assert "timestamp" in data
    assert "version" in data
    assert "system" in data
    assert "cache" in data

    # Check system metrics
    system = data["system"]
    assert "cpu_percent" in system
    assert "memory_mb" in system
    assert "memory_percent" in system
    assert "num_threads" in system
    assert "open_files" in system

    # Check cache metrics
    cache = data["cache"]
    assert "meta" in cache
    assert "deck" in cache

    # Validate meta cache stats
    meta_cache = cache["meta"]
    assert "size" in meta_cache
    assert "max_size" in meta_cache
    assert "hit_rate" in meta_cache
    assert "hits" in meta_cache
    assert "misses" in meta_cache
    assert "utilization" in meta_cache

    # Validate deck cache stats
    deck_cache = cache["deck"]
    assert "size" in deck_cache
    assert "max_size" in deck_cache


@pytest.mark.asyncio
async def test_status_endpoint():
    """Test status endpoint returns comprehensive service status."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/status")

    assert response.status_code == 200
    data = response.json()

    # Check structure
    assert data["service"] == "Arena Improver"
    assert data["status"] == "operational"
    assert "version" in data
    assert "timestamp" in data
    assert "environment" in data
    assert "dependencies" in data
    assert "features" in data

    # Check environment status
    env = data["environment"]
    assert "OPENAI_API_KEY" in env
    assert "TAVILY_API_KEY" in env
    assert "EXA_API_KEY" in env
    assert env["OPENAI_API_KEY"] in ["configured", "missing"]

    # Check dependencies
    deps = data["dependencies"]
    assert "database" in deps
    assert "cache" in deps

    # Check features
    features = data["features"]
    assert "deck_analysis" in features
    assert "ai_optimization" in features
    assert "meta_intelligence" in features
    assert "semantic_search" in features
    assert features["deck_analysis"] is True


@pytest.mark.asyncio
async def test_metrics_cpu_values():
    """Test that CPU metrics are reasonable."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/metrics")

    data = response.json()
    system = data["system"]

    # CPU percent should be between 0 and 100
    assert 0 <= system["cpu_percent"] <= 100

    # Memory should be positive
    assert system["memory_mb"] > 0
    assert system["memory_percent"] > 0


@pytest.mark.asyncio
async def test_metrics_cache_values():
    """Test that cache metrics are valid."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/metrics")

    data = response.json()
    cache = data["cache"]

    # Check meta cache
    meta = cache["meta"]
    assert 0 <= meta["size"] <= meta["max_size"]
    assert 0 <= meta["hit_rate"] <= 1
    assert meta["hits"] >= 0
    assert meta["misses"] >= 0
    assert 0 <= meta["utilization"] <= 1

    # Check deck cache
    deck = cache["deck"]
    assert 0 <= deck["size"] <= deck["max_size"]
    assert 0 <= deck["hit_rate"] <= 1
    assert deck["hits"] >= 0
    assert deck["misses"] >= 0
    assert 0 <= deck["utilization"] <= 1


@pytest.mark.asyncio
async def test_health_endpoints_response_time():
    """Test that health endpoints respond quickly."""
    import time

    async with AsyncClient(app=app, base_url="http://test") as client:
        start = time.time()
        response = await client.get("/health")
        elapsed = time.time() - start

    assert response.status_code == 200
    # Health check should respond in less than 100ms
    assert elapsed < 0.1


@pytest.mark.asyncio
async def test_multiple_health_checks():
    """Test that multiple health checks work consistently."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        responses = []
        for _ in range(5):
            response = await client.get("/health")
            responses.append(response)

    # All should succeed
    for response in responses:
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_status_features_reflect_environment():
    """Test that feature flags reflect actual environment."""
    import os

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/status")

    data = response.json()
    features = data["features"]

    # AI optimization should match OPENAI_API_KEY presence
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    assert features["ai_optimization"] == has_openai

    # Meta intelligence should match TAVILY_API_KEY presence
    has_tavily = bool(os.getenv("TAVILY_API_KEY"))
    assert features["meta_intelligence"] == has_tavily
