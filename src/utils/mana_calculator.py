"""Mana cost calculation utilities."""

import re
from typing import List, Dict


def parse_mana_cost(mana_cost: str) -> Dict[str, int]:
    """
    Parse mana cost string into components.
    
    Examples:
        "2UU" -> {generic: 2, U: 2}
        "GG" -> {G: 2}
        "1WB" -> {generic: 1, W: 1, B: 1}
    """
    if not mana_cost:
        return {}
    
    components = {}
    
    # Remove brackets and spaces
    mana_cost = mana_cost.replace('{', '').replace('}', '').replace(' ', '')
    
    # Match patterns like 2, U, W, B, R, G, C, X
    # Handle hybrid mana (W/U), Phyrexian (W/P), etc.
    pattern = r'(\d+|[WUBRGC]|X|[WUBRG]/[WUBRG]|[WUBRG]/P)'
    matches = re.findall(pattern, mana_cost)
    
    generic = 0
    
    for match in matches:
        if match.isdigit():
            generic += int(match)
        elif match in ['W', 'U', 'B', 'R', 'G', 'C']:
            components[match] = components.get(match, 0) + 1
        elif match == 'X':
            components['X'] = components.get('X', 0) + 1
        elif '/' in match:
            # Hybrid mana - count as 1 generic for CMC purposes
            generic += 1
    
    if generic > 0:
        components['generic'] = generic
    
    return components


def calculate_cmc(mana_cost: str) -> float:
    """Calculate converted mana cost (CMC) from mana cost string."""
    if not mana_cost:
        return 0.0
    
    components = parse_mana_cost(mana_cost)
    
    # CMC is sum of all components (X counts as 0)
    cmc = sum(count for symbol, count in components.items() if symbol != 'X')
    
    return float(cmc)


def extract_colors(mana_cost: str) -> List[str]:
    """Extract color identity from mana cost."""
    if not mana_cost:
        return []
    
    colors = set()
    
    # Find all color symbols (W, U, B, R, G)
    color_pattern = r'[WUBRG]'
    matches = re.findall(color_pattern, mana_cost.upper())
    
    for match in matches:
        colors.add(match)
    
    return sorted(list(colors))
