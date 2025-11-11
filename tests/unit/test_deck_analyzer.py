"""Tests for deck analyzer."""

import pytest
from src.models.deck import Deck, Card
from src.services.deck_analyzer import DeckAnalyzer


@pytest.fixture
def sample_deck():
    """Create a sample deck for testing."""
    cards = [
        Card(name="Lightning Bolt", quantity=4, card_type="Instant", 
             mana_cost="R", cmc=1.0, colors=["R"]),
        Card(name="Monastery Swiftspear", quantity=4, card_type="Creature",
             mana_cost="R", cmc=1.0, colors=["R"]),
        Card(name="Bonecrusher Giant", quantity=4, card_type="Creature",
             mana_cost="2R", cmc=3.0, colors=["R"]),
        Card(name="Mountain", quantity=20, card_type="Land",
             mana_cost="", cmc=0.0, colors=[]),
    ]
    
    return Deck(name="Mono-Red Aggro", format="Standard", mainboard=cards)


def test_analyze_deck(sample_deck):
    """Test basic deck analysis."""
    analyzer = DeckAnalyzer()
    analysis = analyzer.analyze_deck(sample_deck)
    
    assert analysis.deck_name == "Mono-Red Aggro"
    assert "R" in analysis.color_distribution
    assert "Instant" in analysis.card_types
    assert "Creature" in analysis.card_types
    assert analysis.overall_score > 0


def test_mana_curve_analysis(sample_deck):
    """Test mana curve analysis."""
    analyzer = DeckAnalyzer()
    analysis = analyzer.analyze_deck(sample_deck)
    
    assert analysis.mana_curve.average_cmc > 0
    assert analysis.mana_curve.curve_score >= 0
    assert analysis.mana_curve.curve_score <= 100
    assert 1 in analysis.mana_curve.distribution
    assert 3 in analysis.mana_curve.distribution


def test_color_distribution(sample_deck):
    """Test color distribution analysis."""
    analyzer = DeckAnalyzer()
    analysis = analyzer.analyze_deck(sample_deck)
    
    assert len(analysis.color_distribution) == 1
    assert analysis.color_distribution["R"] == 12  # 4+4+4


def test_strengths_weaknesses(sample_deck):
    """Test strength and weakness identification."""
    analyzer = DeckAnalyzer()
    analysis = analyzer.analyze_deck(sample_deck)
    
    assert len(analysis.strengths) > 0
    # Mono-colored should be identified as strength
    assert any("mono" in s.lower() for s in analysis.strengths)
