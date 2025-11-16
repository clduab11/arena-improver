"""Integration tests for FastAPI endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport

SAMPLE_DECK_A = "4 Lightning Bolt (M11) 146\n20 Mountain (ZNR) 381"
SAMPLE_DECK_B = "4 Counterspell (MH2) 267\n20 Island (ZNR) 382"


async def _upload_deck(client: AsyncClient, deck_string: str) -> int:
    """Helper to upload a deck and return its ID."""
    response = await client.post(
        "/api/v1/upload/text",
        json={"deck_string": deck_string, "format": "Standard"}
    )
    assert response.status_code == 200
    return response.json()["deck_id"]


async def _record_result(
    client: AsyncClient,
    deck_id: int,
    opponent: str,
    result: str
):
    """Helper to record a match result for a deck."""
    payload = {
        "opponent_archetype": opponent,
        "result": result,
        "games_won": 2,
        "games_lost": 1,
        "notes": "integration test"
    }
    response = await client.post(
        f"/api/v1/performance/{deck_id}",
        json=payload
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_check(initialized_app):
    """Test health check endpoint."""
    transport = ASGITransport(app=initialized_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200, response.json()
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_upload_deck_text(initialized_app):
    """Test deck upload via text."""
    deck_string = """4 Lightning Bolt (M11) 146
20 Mountain (ZNR) 381"""
    
    transport = ASGITransport(app=initialized_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/upload/text",
            json={"deck_string": deck_string, "format": "Standard"}
        )
        assert response.status_code == 200, response.json()
        data = response.json()
        assert data["status"] == "success"
        assert "deck_id" in data


@pytest.mark.asyncio
async def test_list_decks(initialized_app):
    """Test listing decks."""
    transport = ASGITransport(app=initialized_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/decks")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
async def test_analyze_deck_not_found(initialized_app):
    """Test analyzing non-existent deck."""
    transport = ASGITransport(app=initialized_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/analyze/99999")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_record_performance_validation(initialized_app):
    """Test performance endpoint with validation."""
    transport = ASGITransport(app=initialized_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as client:
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
        assert response.status_code == 400, response.json()
        assert "Invalid result value" in response.json()["detail"]


@pytest.mark.asyncio
async def test_record_performance_not_found(initialized_app):
    """Test recording performance for non-existent deck."""
    transport = ASGITransport(app=initialized_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as client:
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
    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/meta/Standard")
        assert response.status_code == 200
        data = response.json()
        assert data["format"].lower() == "standard"
        assert "archetypes" in data
        assert isinstance(data["archetypes"], list)


@pytest.mark.asyncio
async def test_deck_trends_endpoint(initialized_app):
    """Test fetching deck performance trends."""
    transport = ASGITransport(app=initialized_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as client:
        deck_id = await _upload_deck(client, SAMPLE_DECK_A)
        for idx, result in enumerate(["win", "loss", "win"], start=1):
            await _record_result(client, deck_id, f"Archetype {idx}", result)

        response = await client.get(f"/api/v1/stats/{deck_id}/trends?days=14")
        assert response.status_code == 200
        data = response.json()
        assert data["sample_size"] == 3
        assert isinstance(data["weekly_stats"], list)


@pytest.mark.asyncio
async def test_compare_deck_stats_endpoint(initialized_app):
    """Test comparing statistics between two decks."""
    transport = ASGITransport(app=initialized_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as client:
        deck_id1 = await _upload_deck(client, SAMPLE_DECK_A)
        deck_id2 = await _upload_deck(client, SAMPLE_DECK_B)

        await _record_result(client, deck_id1, "Aggro", "win")
        await _record_result(client, deck_id2, "Control", "loss")

        response = await client.get(
            f"/api/v1/stats/compare?deck_id1={deck_id1}&deck_id2={deck_id2}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deck1"]["id"] == deck_id1
        assert data["deck2"]["id"] == deck_id2
        assert "better_deck" in data


@pytest.mark.asyncio
async def test_compare_deck_stats_requires_distinct_ids(initialized_app):
    """Ensure compare endpoint validates duplicate IDs."""
    transport = ASGITransport(app=initialized_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as client:
        deck_id = await _upload_deck(client, SAMPLE_DECK_A)
        response = await client.get(
            f"/api/v1/stats/compare?deck_id1={deck_id}&deck_id2={deck_id}"
        )
        assert response.status_code == 400
