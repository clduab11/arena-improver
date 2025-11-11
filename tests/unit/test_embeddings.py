"""Tests for embeddings service."""

import pytest
import numpy as np
from src.models.deck import Card
from src.services.embeddings import EmbeddingsService


@pytest.fixture
def embeddings_service():
    """Create embeddings service for testing."""
    return EmbeddingsService()


@pytest.fixture
def sample_cards():
    """Create sample cards for testing."""
    return [
        Card(name="Lightning Bolt", quantity=4, card_type="Instant",
             mana_cost="R", cmc=1.0, colors=["R"]),
        Card(name="Counterspell", quantity=4, card_type="Instant",
             mana_cost="UU", cmc=2.0, colors=["U"]),
        Card(name="Giant Growth", quantity=4, card_type="Instant",
             mana_cost="G", cmc=1.0, colors=["G"]),
    ]


def test_generate_card_embedding(embeddings_service, sample_cards):
    """Test generating a single card embedding."""
    card = sample_cards[0]
    embedding = embeddings_service.generate_card_embedding(card)
    
    assert isinstance(embedding, np.ndarray)
    assert embedding.shape[0] > 0  # Has dimensions


def test_batch_embeddings_generation(embeddings_service, sample_cards):
    """Test batch embedding generation."""
    embeddings = embeddings_service._generate_batch_embeddings(sample_cards)
    
    assert isinstance(embeddings, np.ndarray)
    assert embeddings.shape[0] == len(sample_cards)
    assert embeddings.shape[1] > 0  # Has dimensions


def test_find_similar_cards(embeddings_service, sample_cards):
    """Test finding similar cards."""
    target_card = sample_cards[0]
    similar = embeddings_service.find_similar_cards(target_card, sample_cards, top_k=2)
    
    assert isinstance(similar, list)
    assert len(similar) <= 2
    # Target card should not be in results
    assert all(s['card'].name != target_card.name for s in similar)


def test_calculate_deck_similarity(embeddings_service, sample_cards):
    """Test calculating deck similarity."""
    deck1 = sample_cards[:2]
    deck2 = sample_cards[1:]
    
    similarity = embeddings_service.calculate_deck_similarity(deck1, deck2)
    
    assert isinstance(similarity, float)
    assert 0.0 <= similarity <= 1.0


def test_embeddings_cache(embeddings_service, sample_cards):
    """Test that embeddings are cached properly."""
    card = sample_cards[0]
    
    # Generate embedding first time
    embedding1 = embeddings_service.generate_card_embedding(card)
    cache_size_1 = len(embeddings_service._embeddings_cache)
    
    # Generate same embedding again
    embedding2 = embeddings_service.generate_card_embedding(card)
    cache_size_2 = len(embeddings_service._embeddings_cache)
    
    # Cache size should not increase
    assert cache_size_1 == cache_size_2
    # Embeddings should be identical (same reference or equal values)
    assert np.array_equal(embedding1, embedding2)
