"""Deck and card data models."""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class Card(BaseModel):
    """Represents a single Magic: The Gathering card."""
    
    name: str
    quantity: int
    card_type: str  # Creature, Instant, Sorcery, Enchantment, Artifact, Land, Planeswalker
    mana_cost: str  # e.g., "2UU", "GG", "1"
    cmc: float = 0.0  # Converted mana cost
    colors: List[str] = Field(default_factory=list)  # W, U, B, R, G
    rarity: Optional[str] = None  # Common, Uncommon, Rare, Mythic
    set_code: Optional[str] = None


class Deck(BaseModel):
    """Represents a complete MTG Arena deck."""
    
    name: str
    format: str = "Standard"  # Standard, Historic, Explorer, etc.
    mainboard: List[Card]
    sideboard: List[Card] = Field(default_factory=list)
    commander: Optional[Card] = None


class ManaCurve(BaseModel):
    """Mana curve analysis for a deck."""
    
    distribution: Dict[int, int]  # CMC -> count
    average_cmc: float
    median_cmc: float
    curve_score: float  # 0-100 rating


class CardSynergy(BaseModel):
    """Represents synergy between two cards."""
    
    card1: str
    card2: str
    synergy_type: str  # combo, support, anti-synergy
    strength: float  # 0-100
    explanation: str


class MetaMatchup(BaseModel):
    """Meta matchup analysis."""
    
    archetype: str
    win_rate: float
    favorable: bool
    key_cards: List[str]
    sideboard_suggestions: List[str]


class DeckAnalysis(BaseModel):
    """Complete deck analysis result."""
    
    deck_name: str
    mana_curve: ManaCurve
    color_distribution: Dict[str, int]
    card_types: Dict[str, int]
    synergies: List[CardSynergy]
    meta_matchups: List[MetaMatchup]
    strengths: List[str]
    weaknesses: List[str]
    overall_score: float  # 0-100


class DeckSuggestion(BaseModel):
    """Deck optimization suggestion."""
    
    type: str  # add, remove, replace
    card_name: str
    quantity: int = 1
    reason: str
    impact_score: float  # 0-100
    replacement_for: Optional[str] = None


class OptimizedDeck(BaseModel):
    """Optimized deck with suggestions."""
    
    original_deck: Deck
    suggestions: List[DeckSuggestion]
    predicted_win_rate: float
    confidence: float
