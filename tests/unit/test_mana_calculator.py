"""Tests for mana calculation utilities."""

import pytest
from src.utils.mana_calculator import calculate_cmc, parse_mana_cost, extract_colors


def test_calculate_cmc_basic():
    """Test basic CMC calculation."""
    assert calculate_cmc("2UU") == 4.0
    assert calculate_cmc("GG") == 2.0
    assert calculate_cmc("1WB") == 3.0
    assert calculate_cmc("") == 0.0


def test_calculate_cmc_with_x():
    """Test CMC calculation with X."""
    assert calculate_cmc("XUU") == 2.0  # X counts as 0


def test_parse_mana_cost():
    """Test mana cost parsing."""
    result = parse_mana_cost("2UU")
    assert result == {"generic": 2, "U": 2}
    
    result = parse_mana_cost("GG")
    assert result == {"G": 2}
    
    result = parse_mana_cost("1WB")
    assert result == {"generic": 1, "W": 1, "B": 1}


def test_extract_colors():
    """Test color extraction."""
    assert extract_colors("2UU") == ["U"]
    assert extract_colors("WUB") == ["B", "U", "W"]  # Sorted
    assert extract_colors("GG") == ["G"]
    assert extract_colors("2") == []  # Colorless
