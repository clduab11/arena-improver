"""Example workflow demonstrating Arena Improver functionality."""

import asyncio
from src.services.deck_analyzer import DeckAnalyzer
from src.services.smart_sql import SmartSQLService
from src.services.smart_inference import SmartInferenceService
from src.services.smart_memory import SmartMemoryService
from src.utils.csv_parser import parse_deck_string


async def main():
    """Run example workflow."""
    print("=" * 60)
    print("Arena Improver - Example Workflow")
    print("=" * 60)
    
    # Initialize services
    sql_service = SmartSQLService()
    await sql_service.init_db()
    
    analyzer = DeckAnalyzer()
    inference_service = SmartInferenceService()
    memory_service = SmartMemoryService(sql_service)
    
    # Step 1: Parse a deck
    print("\n1. Parsing deck from text format...")
    deck_string = """
4 Lightning Bolt (M11) 146
4 Monastery Swiftspear (KTK) 118
4 Bonecrusher Giant (ELD) 115
4 Embercleave (ELD) 120
20 Mountain (ZNR) 381
    """
    
    deck = parse_deck_string(deck_string)
    deck.name = "Mono-Red Aggro"
    print(f"✓ Deck parsed: {deck.name}")
    print(f"  Mainboard: {len(deck.mainboard)} unique cards")
    
    # Step 2: Store deck
    print("\n2. Storing deck in database...")
    deck_id = await sql_service.store_deck(deck)
    print(f"✓ Deck stored with ID: {deck_id}")
    
    # Step 3: Analyze deck
    print("\n3. Analyzing deck...")
    analysis = analyzer.analyze_deck(deck)
    print(f"✓ Analysis complete!")
    print(f"\n  Overall Score: {analysis.overall_score}/100")
    print(f"  Curve Score: {analysis.mana_curve.curve_score:.1f}/100")
    
    print("\n  Strengths:")
    for strength in analysis.strengths:
        print(f"    • {strength}")
    
    print("\n  Weaknesses:")
    for weakness in analysis.weaknesses:
        print(f"    • {weakness}")
    
    # Step 4: Get AI suggestions
    print("\n4. Getting suggestions (fallback mode)...")
    suggestions = await inference_service.generate_suggestions(deck, analysis)
    print(f"✓ Generated {len(suggestions)} suggestions")
    
    # Step 5: Record some matches
    print("\n5. Recording match history...")
    await sql_service.record_performance(
        deck_id=deck_id,
        opponent_archetype="Azorius Control",
        result="win",
        games_won=2,
        games_lost=1,
        notes="Aggressive curve won the day"
    )
    print("✓ Recorded match")
    
    # Step 6: Get performance stats
    print("\n6. Analyzing performance...")
    stats = await memory_service.get_deck_statistics(deck_id)
    print(f"✓ Win Rate: {stats['win_rate']}%")
    
    print("\n" + "=" * 60)
    print("Workflow complete! ✨")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
