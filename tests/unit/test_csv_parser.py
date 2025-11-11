"""Tests for CSV parser."""

import pytest
from src.utils.csv_parser import parse_deck_string, parse_arena_csv


def test_parse_deck_string_basic():
    """Test basic deck string parsing."""
    deck_string = """4 Lightning Bolt (M11) 146
2 Counterspell (MH2) 267
20 Island (ZNR) 381"""
    
    deck = parse_deck_string(deck_string)
    
    assert deck.name == "Imported Deck"
    assert len(deck.mainboard) == 3
    assert deck.mainboard[0].name == "Lightning Bolt"
    assert deck.mainboard[0].quantity == 4


def test_parse_deck_string_with_sideboard():
    """Test deck string parsing with sideboard."""
    deck_string = """4 Lightning Bolt (M11) 146
    
Sideboard:
2 Spell Pierce (XLN) 81"""
    
    deck = parse_deck_string(deck_string)
    
    assert len(deck.mainboard) == 1
    assert len(deck.sideboard) == 1
    assert deck.sideboard[0].name == "Spell Pierce"


def test_parse_arena_csv():
    """Test CSV parsing."""
    csv_content = """Quantity,Name,Set,Type,Mana Cost,CMC,Colors,Rarity
4,Lightning Bolt,M11,Instant,R,1,R,Uncommon
20,Island,ZNR,Land,,0,,Common"""
    
    deck = parse_arena_csv(csv_content)
    
    assert deck.name == "CSV Import"
    assert len(deck.mainboard) == 2
    assert deck.mainboard[0].name == "Lightning Bolt"
    assert deck.mainboard[0].quantity == 4
    assert deck.mainboard[0].colors == ["R"]
