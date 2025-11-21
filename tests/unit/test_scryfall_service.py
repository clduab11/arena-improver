"""Tests for ScryfallService with connection pooling."""

import pytest
from unittest.mock import AsyncMock, MagicMock
import httpx

from src.services.scryfall_service import ScryfallService


@pytest.mark.asyncio
async def test_scryfall_service_uses_shared_client(mock_http_client):
    """Test that ScryfallService uses the provided shared client."""
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "name": "Lightning Bolt",
        "set": "lea",
        "games": ["paper", "arena"]
    }
    mock_http_client.get.return_value = mock_response
    
    # Act
    service = ScryfallService()
    service._client = mock_http_client  # Inject mock
    async with service:
        result = await service.get_card_by_name("Lightning Bolt")
    
    # Assert
    assert result is not None
    assert result["name"] == "Lightning Bolt"
    mock_http_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_scryfall_service_reuses_client_across_requests(mock_http_client):
    """Test that multiple requests reuse the same client instance."""
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "name": "Test Card",
        "games": ["paper"]
    }
    mock_http_client.get.return_value = mock_response
    
    # Act
    service = ScryfallService()
    service._client = mock_http_client  # Inject mock
    async with service:
        # Make multiple requests
        await service.get_card_by_name("Card 1")
        await service.get_card_by_name("Card 2")
        await service.get_card_by_name("Card 3")
    
    # Assert - All requests should use the same client instance
    assert mock_http_client.get.call_count == 3
    # Verify client was not recreated
    assert isinstance(service._client, (httpx.AsyncClient, AsyncMock))


@pytest.mark.asyncio
async def test_scryfall_service_context_manager_lifecycle():
    """Test async context manager properly initializes and cleans up."""
    # Arrange
    service = ScryfallService()
    
    # Act
    async with service:
        # Service should create client on enter
        assert service._client is not None
    
    # After context exit, client should be closed and set to None
    assert service._client is None


@pytest.mark.asyncio
async def test_scryfall_service_ensure_client():
    """Test lazy client initialization with _ensure_client."""
    # Arrange
    service = ScryfallService()
    
    # Act - Call _ensure_client - should create a new client
    client = await service._ensure_client()
    
    # Assert
    assert client is not None
    assert service._client is client
    assert isinstance(client, httpx.AsyncClient)
    
    # Cleanup
    await service.close()


@pytest.mark.asyncio
async def test_scryfall_service_rate_limiting(mock_http_client):
    """Test that rate limiting is enforced between requests."""
    # Arrange
    import asyncio
    from datetime import datetime, timedelta
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"name": "Test"}
    mock_http_client.get.return_value = mock_response
    
    # Act
    service = ScryfallService()
    service._client = mock_http_client
    async with service:
        start_time = datetime.now()
        
        # Make two requests
        await service.get_card_by_name("Card 1")
        await service.get_card_by_name("Card 2")
        
        elapsed = (datetime.now() - start_time).total_seconds()
    
    # Assert - At least one rate limit delay should have occurred (100ms)
    assert elapsed >= 0.1  # 100ms minimum delay


@pytest.mark.asyncio
async def test_scryfall_service_caching(mock_http_client):
    """Test that responses are cached to avoid redundant API calls."""
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "name": "Cached Card",
        "games": ["paper"]
    }
    mock_http_client.get.return_value = mock_response
    
    # Act
    service = ScryfallService()
    service._client = mock_http_client
    async with service:
        # First request - should hit API
        result1 = await service.get_card_by_name("Cached Card")
        
        # Second request with same card - should use cache
        result2 = await service.get_card_by_name("Cached Card")
    
    # Assert - API should only be called once due to caching
    assert mock_http_client.get.call_count == 1
    assert result1 == result2


@pytest.mark.asyncio
async def test_scryfall_service_is_arena_only(mock_http_client):
    """Test Arena-only detection logic."""
    # Arrange - Arena-only card
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "name": "Digital Card",
        "games": ["arena"]  # Only arena, not paper
    }
    mock_http_client.get.return_value = mock_response
    
    # Act
    service = ScryfallService()
    service._client = mock_http_client
    async with service:
        is_arena_only = await service.is_arena_only("Digital Card")
    
    # Assert
    assert is_arena_only is True


@pytest.mark.asyncio
async def test_scryfall_service_paper_available(mock_http_client):
    """Test that paper-available cards are not marked as Arena-only."""
    # Arrange - Paper-available card
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "name": "Paper Card",
        "games": ["paper", "arena"]  # Available in both
    }
    mock_http_client.get.return_value = mock_response
    
    # Act
    service = ScryfallService()
    service._client = mock_http_client
    async with service:
        is_arena_only = await service.is_arena_only("Paper Card")
    
    # Assert
    assert is_arena_only is False


@pytest.mark.asyncio
async def test_scryfall_service_search_cards(mock_http_client):
    """Test card search functionality with connection pooling."""
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {"name": "Lightning Bolt", "set": "lea"},
            {"name": "Lightning Bolt", "set": "leb"}
        ]
    }
    mock_http_client.get.return_value = mock_response
    
    # Act
    service = ScryfallService()
    service._client = mock_http_client
    async with service:
        results = await service.search_cards("Lightning Bolt")
    
    # Assert
    assert len(results) == 2
    assert results[0]["name"] == "Lightning Bolt"
    mock_http_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_scryfall_service_handles_404(mock_http_client):
    """Test that 404 responses are handled gracefully."""
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_http_client.get.return_value = mock_response
    
    # Act
    service = ScryfallService()
    service._client = mock_http_client
    async with service:
        result = await service.get_card_by_name("Nonexistent Card")
    
    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_scryfall_service_handles_timeout(mock_http_client):
    """Test that timeout exceptions are handled gracefully."""
    # Arrange
    mock_http_client.get.side_effect = httpx.TimeoutException("Request timeout")
    
    # Act
    service = ScryfallService()
    service._client = mock_http_client
    async with service:
        result = await service.get_card_by_name("Test Card")
    
    # Assert
    assert result is None
