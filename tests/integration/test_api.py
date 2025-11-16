"""Integration tests for FastAPI endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health_check(initialized_app):
    """Test health check endpoint."""
    transport = ASGITransport(app=initialized_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_upload_deck_text(initialized_app):
    """Test deck upload via text."""
    deck_string = """4 Lightning Bolt (M11) 146
20 Mountain (ZNR) 381"""
    
    transport = ASGITransport(app=initialized_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/upload/text",
            json={"deck_string": deck_string, "format": "Standard"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "deck_id" in data


@pytest.mark.asyncio
async def test_list_decks(initialized_app):
    """Test listing decks."""
    transport = ASGITransport(app=initialized_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/decks")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_analyze_deck_not_found(initialized_app):
    """Test analyzing non-existent deck."""
    transport = ASGITransport(app=initialized_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/analyze/99999")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_record_performance_validation(initialized_app):
    """Test performance endpoint with validation."""
    transport = ASGITransport(app=initialized_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test with invalid result value
        response = await client.post(
            "/api/v1/performance/1",
            json={
                "opponent_archetype": "Test Deck",
                "result": "invalid_result",
                "games_won": 2,
                "games_lost": 1
            }
        )
        assert response.status_code == 400
        assert "Invalid result value" in response.json()["detail"]


@pytest.mark.asyncio
async def test_record_performance_not_found(initialized_app):
    """Test recording performance for non-existent deck."""
    transport = ASGITransport(app=initialized_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/performance/99999",
            json={
                "opponent_archetype": "Test Deck",
                "result": "win",
                "games_won": 2,
                "games_lost": 1
            }
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_meta_snapshot(initialized_app):
    """Test fetching meta intelligence snapshot."""
    transport = ASGITransport(app=initialized_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/meta/Standard")
        assert response.status_code == 200
        data = response.json()
        assert data["format"].lower() == "standard"
        assert "archetypes" in data
        assert isinstance(data["archetypes"], list)
