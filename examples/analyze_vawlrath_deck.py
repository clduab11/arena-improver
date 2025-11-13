"""Example: Analyzing the Vawlrath the Small'n Commander Deck

This example demonstrates:
1. Loading a deck from JSON
2. Performing comprehensive analysis
3. Getting AI-powered optimization suggestions
4. Tracking performance metrics
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.deck import Deck, Card
from src.services.deck_analyzer import DeckAnalyzer
from src.services.smart_inference import SmartInferenceService
from src.services.smart_sql import SmartSQLService
from src.services.meta_intelligence import MetaIntelligenceService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_deck_from_json(json_path: str) -> Deck:
    """Load a deck from JSON file."""
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Convert mainboard cards
    mainboard_cards = []
    for card_data in data['mainboard']:
        card = Card(
            name=card_data['name'],
            quantity=card_data['quantity'],
            card_type=card_data['card_type'],
            cmc=card_data['cmc'],
            colors=card_data['colors'],
            set_code=card_data.get('set', 'UNK'),
            collector_number=card_data.get('collector_number', '000')
        )
        mainboard_cards.append(card)

    # Convert sideboard cards (if any)
    sideboard_cards = []
    for card_data in data.get('sideboard', []):
        card = Card(
            name=card_data['name'],
            quantity=card_data['quantity'],
            card_type=card_data['card_type'],
            cmc=card_data['cmc'],
            colors=card_data['colors'],
            set_code=card_data.get('set', 'UNK'),
            collector_number=card_data.get('collector_number', '000')
        )
        sideboard_cards.append(card)

    return Deck(
        name=data['name'],
        format=data['format'],
        mainboard=mainboard_cards,
        sideboard=sideboard_cards
    )


def print_deck_summary(deck: Deck, meta_data: Dict[str, Any]):
    """Print a formatted deck summary."""
    print("\n" + "="*70)
    print(f"  {deck.name}")
    print("="*70)
    print(f"Format: {deck.format}")
    print(f"Total Cards: {sum(c.quantity for c in deck.mainboard)}")
    print(f"Unique Cards: {len(deck.mainboard)}")
    print()

    # Print meta analysis if available
    if meta_data:
        print("📊 Meta Analysis:")
        print(f"  Strategy: {meta_data.get('strategy', 'N/A')}")
        print(f"  Power Level: {meta_data.get('power_level', 'N/A')}/10")
        print(f"  Budget Tier: {meta_data.get('budget_tier', 'N/A')}")
        print()

        print("💪 Strengths:")
        for strength in meta_data.get('strengths', []):
            print(f"  • {strength}")
        print()

        print("⚠️  Weaknesses:")
        for weakness in meta_data.get('weaknesses', []):
            print(f"  • {weakness}")
        print()

        print("🎯 Key Synergies:")
        for synergy in meta_data.get('key_synergies', []):
            print(f"  • {synergy}")
        print()


async def analyze_vawlrath_deck():
    """Complete analysis workflow for Vawlrath deck."""

    # 1. Load the deck
    print("📂 Loading Vawlrath the Small'n Commander deck...")
    deck_path = Path(__file__).parent / "vawlrath_commander_deck.json"

    with open(deck_path, 'r') as f:
        deck_data = json.load(f)

    deck = load_deck_from_json(str(deck_path))
    meta_data = deck_data.get('meta_analysis', {})

    print_deck_summary(deck, meta_data)

    # 2. Store in database
    print("💾 Storing deck in database...")
    sql_service = SmartSQLService()
    await sql_service.init_db()
    deck_id = await sql_service.store_deck(deck)
    print(f"✓ Deck stored with ID: {deck_id}")
    print()

    # 3. Perform comprehensive analysis
    print("🔍 Analyzing deck composition...")
    analyzer = DeckAnalyzer()
    analysis = await analyzer.analyze_deck(deck)

    print(f"Overall Score: {analysis.overall_score}/100")
    print()

    print("📈 Mana Curve:")
    print(f"  Average CMC: {analysis.mana_curve.average_cmc}")
    print(f"  Median CMC: {analysis.mana_curve.median_cmc}")
    print(f"  Curve Score: {analysis.mana_curve.curve_score}/100")
    print(f"  Distribution: {analysis.mana_curve.distribution}")
    print()

    print("🎨 Color Distribution:")
    for color, count in analysis.color_distribution.items():
        color_names = {
            'W': 'White', 'U': 'Blue', 'B': 'Black',
            'R': 'Red', 'G': 'Green', 'C': 'Colorless'
        }
        print(f"  {color_names.get(color, color)}: {count}")
    print()

    print("📦 Card Types:")
    for card_type, count in sorted(analysis.card_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {card_type}: {count}")
    print()

    # 4. Get AI optimization suggestions
    print("🤖 Generating AI-powered optimization suggestions...")
    inference_service = SmartInferenceService()

    try:
        suggestions = await inference_service.generate_suggestions(deck, analysis)

        if suggestions:
            print(f"✓ Generated {len(suggestions)} suggestions:")
            print()

            for i, suggestion in enumerate(suggestions[:5], 1):
                print(f"{i}. {suggestion.type.upper()}: {suggestion.card_name}")
                if suggestion.replacement_for:
                    print(f"   (replaces {suggestion.replacement_for})")
                print(f"   Reason: {suggestion.reason}")
                print(f"   Impact Score: {suggestion.impact_score}/100")
                print()

            # Predict win rate
            prediction = await inference_service.predict_win_rate(deck, suggestions)
            print(f"📊 Predicted Win Rate: {prediction.get('predicted_win_rate', 'N/A')}%")
            print(f"   Confidence: {prediction.get('confidence', 'N/A')}")
            print()
        else:
            print("⚠️  No suggestions generated (check OpenAI API key)")
            print()

    except Exception as e:
        logger.warning(f"Could not generate AI suggestions: {e}")
        print("⚠️  AI suggestions unavailable (OpenAI API key required)")
        print()

    # 5. Meta matchup analysis
    if analysis.meta_matchups:
        print("⚔️  Meta Matchups:")
        for matchup in analysis.meta_matchups[:5]:
            status = "✓ Favorable" if matchup.favorable else "✗ Unfavorable"
            print(f"  {status} vs {matchup.archetype}: {matchup.win_rate}%")
            if matchup.key_cards:
                print(f"    Key cards: {', '.join(matchup.key_cards[:3])}")
        print()

    # 6. Budget alternatives
    if 'budget_alternatives' in deck_data:
        print("💰 Budget Alternatives:")
        for alt in deck_data['budget_alternatives']['high_to_low']:
            print(f"  • {alt['expensive']} → {alt['budget']} (saves ${alt['savings']})")
        print()

    # 7. Upgrade path
    if 'upgrade_path' in deck_data:
        print("⬆️  Upgrade Path (Priority Order):")
        for upgrade in deck_data['upgrade_path']:
            print(f"  {upgrade['priority']}. {upgrade['card']} (~{upgrade['cost_estimate']})")
            print(f"     {upgrade['reason']}")
        print()

    # 8. Summary
    print("="*70)
    print("✅ Analysis Complete!")
    print(f"   Deck ID: {deck_id}")
    print(f"   Overall Score: {analysis.overall_score}/100")
    print(f"   Mana Curve Score: {analysis.mana_curve.curve_score}/100")
    print(f"   Suggestions Generated: {len(suggestions) if 'suggestions' in locals() else 0}")
    print("="*70)
    print()

    # Cleanup
    await sql_service.close()


async def track_performance_example(deck_id: int):
    """Example of tracking deck performance over time."""
    print("\n" + "="*70)
    print("  Performance Tracking Example")
    print("="*70)
    print()

    sql_service = SmartSQLService()
    await sql_service.init_db()

    # Record some example matches
    example_matches = [
        {
            "opponent_archetype": "Atraxa Superfriends",
            "result": "win",
            "games_won": 2,
            "games_lost": 1,
            "notes": "Token strategy overwhelmed planeswalkers"
        },
        {
            "opponent_archetype": "Muldrotha Control",
            "result": "loss",
            "games_won": 1,
            "games_lost": 2,
            "notes": "Board wipes difficult to recover from"
        },
        {
            "opponent_archetype": "Krenko Goblins",
            "result": "win",
            "games_won": 2,
            "games_lost": 0,
            "notes": "Faster token generation secured win"
        }
    ]

    print("📝 Recording example matches...")
    for match in example_matches:
        await sql_service.record_performance(
            deck_id=deck_id,
            opponent_archetype=match["opponent_archetype"],
            result=match["result"],
            games_won=match["games_won"],
            games_lost=match["games_lost"],
            notes=match["notes"]
        )
        result_symbol = "✓" if match["result"] == "win" else "✗"
        print(f"  {result_symbol} vs {match['opponent_archetype']}: {match['result'].upper()}")

    print()
    print("✅ Performance data recorded!")
    print(f"   Use MCP tool 'get_deck_stats' with deck_id={deck_id} to view statistics")
    print()

    await sql_service.close()


def main():
    """Main entry point."""
    print("\n" + "🎮"*35)
    print("  Arena Improver - Vawlrath the Small'n Analysis")
    print("  MCP-1st-Birthday Hackathon Demonstration")
    print("🎮"*35 + "\n")

    # Run analysis
    asyncio.run(analyze_vawlrath_deck())

    # Note: Performance tracking would use the deck_id from above
    print("💡 To track performance:")
    print("   1. Note the deck_id from the analysis above")
    print("   2. Use the MCP 'record_match' tool after each game")
    print("   3. View statistics with 'get_deck_stats' tool")
    print()

    print("📖 Documentation: docs/HACKATHON_SUBMISSION.md")
    print("⭐ Star the repo: github.com/clduab11/arena-improver")
    print()


if __name__ == "__main__":
    main()
