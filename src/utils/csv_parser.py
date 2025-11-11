"""CSV parser for MTG Arena deck exports."""

import re
from typing import List, Tuple
from io import StringIO
import pandas as pd

from ..models.deck import Card, Deck
from .mana_calculator import calculate_cmc, parse_mana_cost, extract_colors


def parse_deck_string(deck_string: str) -> Deck:
    """
    Parse MTG Arena deck format string.
    
    Format examples:
        4 Lightning Bolt (M11) 146
        2 Counterspell (MH2) 267
        20 Island (ZNR) 381
    """
    lines = deck_string.strip().split('\n')
    mainboard = []
    sideboard = []
    current_section = mainboard
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check for sideboard marker
        if line.lower() in ['sideboard', 'sideboard:']:
            current_section = sideboard
            continue
        
        # Parse card line: "4 Card Name (SET) 123"
        # Split by parentheses to avoid ReDoS vulnerability
        paren_match = re.search(r'\(([A-Z0-9]+)\)\s+(\d+)$', line)
        if paren_match:
            # Extract quantity and name from beginning
            prefix = line[:paren_match.start()].strip()
            # Use simple split to avoid ReDoS
            parts = prefix.split(None, 1)  # Split on first whitespace
            if len(parts) == 2 and parts[0].isdigit():
                quantity = int(parts[0])
                card_name = parts[1].strip()
                set_code = paren_match.group(1)
                
                # Determine card type and mana cost (simplified - would need card database)
                card_type = determine_card_type(card_name)
                # WARNING: Text format parsing limitation - mana cost is not available
                # This will result in CMC=0 and no colors for all non-land cards,
                # which significantly affects deck analysis accuracy.
                # Use CSV format for accurate mana curve and color analysis.
                mana_cost = ""  # Would need card database lookup
                
                card = Card(
                    name=card_name,
                    quantity=quantity,
                    card_type=card_type,
                    mana_cost=mana_cost,
                    cmc=calculate_cmc(mana_cost),
                    colors=extract_colors(mana_cost),
                    set_code=set_code
                )
                current_section.append(card)
    
    return Deck(
        name="Imported Deck",
        mainboard=mainboard,
        sideboard=sideboard
    )


def parse_arena_csv(csv_content: str) -> Deck:
    """
    Parse CSV export from Steam MTG Arena.
    
    Expected CSV format:
        Quantity,Name,Set,Collector Number,Type,Mana Cost,CMC,Colors,Rarity
    """
    # Read CSV
    df = pd.read_csv(StringIO(csv_content))
    
    # Normalize column names
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    
    mainboard = []
    sideboard = []
    
    for _, row in df.iterrows():
        quantity = int(row.get('quantity', 1))
        name = str(row.get('name', ''))
        set_code = str(row.get('set', '')) if 'set' in row else None
        card_type = str(row.get('type', 'Unknown'))
        mana_cost = str(row.get('mana_cost', ''))
        
        # Calculate CMC if not provided
        if 'cmc' in row:
            cmc = float(row['cmc'])
        else:
            cmc = calculate_cmc(mana_cost)
        
        # Extract colors if not provided
        if 'colors' in row and pd.notna(row['colors']):
            colors = [c.strip() for c in str(row['colors']).split(',')]
        else:
            colors = extract_colors(mana_cost)
        
        rarity = str(row.get('rarity', '')) if 'rarity' in row else None
        is_sideboard = row.get('sideboard', False) if 'sideboard' in row else False
        
        card = Card(
            name=name,
            quantity=quantity,
            card_type=card_type,
            mana_cost=mana_cost,
            cmc=cmc,
            colors=colors,
            rarity=rarity,
            set_code=set_code
        )
        
        if is_sideboard:
            sideboard.append(card)
        else:
            mainboard.append(card)
    
    return Deck(
        name="CSV Import",
        mainboard=mainboard,
        sideboard=sideboard
    )


def determine_card_type(card_name: str) -> str:
    """Determine card type based on name (simplified heuristic)."""
    # This is a simplified version - in production would use card database
    name_lower = card_name.lower()
    
    if any(land in name_lower for land in ['island', 'mountain', 'forest', 'plains', 'swamp']):
        return "Land"
    
    # Default to Unknown - should be looked up from card database
    return "Unknown"
