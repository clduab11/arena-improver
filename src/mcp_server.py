"""MCP Server implementation for Arena Improver."""

import asyncio
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .services.deck_analyzer import DeckAnalyzer
from .services.smart_sql import SmartSQLService
from .services.smart_inference import SmartInferenceService
from .services.smart_memory import SmartMemoryService
from .services.embeddings import EmbeddingsService
from .utils.csv_parser import parse_deck_string, parse_arena_csv


# Initialize services
sql_service = SmartSQLService()
analyzer = DeckAnalyzer()
inference_service = SmartInferenceService()
embeddings_service = EmbeddingsService()

# Create MCP server
mcp_server = Server("arena-improver")


# Tool handler functions
async def handle_parse_deck_csv(arguments: dict) -> list[TextContent]:
    """Handle parse_deck_csv tool call."""
    csv_content = arguments["csv_content"]
    deck = parse_arena_csv(csv_content)
    deck_id = await sql_service.store_deck(deck)
    
    return [TextContent(
        type="text",
        text=f"Deck parsed and stored successfully. Deck ID: {deck_id}\n"
             f"Name: {deck.name}\n"
             f"Format: {deck.format}\n"
             f"Mainboard: {len(deck.mainboard)} unique cards\n"
             f"Sideboard: {len(deck.sideboard)} unique cards"
    )]


async def handle_parse_deck_text(arguments: dict) -> list[TextContent]:
    """Handle parse_deck_text tool call."""
    deck_string = arguments["deck_string"]
    format_str = arguments.get("format", "Standard")
    deck = parse_deck_string(deck_string)
    deck.format = format_str
    deck_id = await sql_service.store_deck(deck)
    
    return [TextContent(
        type="text",
        text=f"Deck parsed and stored successfully. Deck ID: {deck_id}\n"
             f"Format: {deck.format}\n"
             f"Mainboard: {len(deck.mainboard)} unique cards"
    )]


async def handle_analyze_deck(arguments: dict) -> list[TextContent]:
    """Handle analyze_deck tool call."""
    deck_id = arguments["deck_id"]
    deck = await sql_service.get_deck(deck_id)
    
    if not deck:
        return [TextContent(type="text", text=f"Deck {deck_id} not found")]
    
    analysis = analyzer.analyze_deck(deck)
    
    result = f"""Deck Analysis for '{deck.name}'
==========================================

Mana Curve:
- Average CMC: {analysis.mana_curve.average_cmc}
- Median CMC: {analysis.mana_curve.median_cmc}
- Curve Score: {analysis.mana_curve.curve_score}/100
- Distribution: {analysis.mana_curve.distribution}

Colors: {', '.join(analysis.color_distribution.keys())}

Card Types:
{chr(10).join(f"- {k}: {v}" for k, v in analysis.card_types.items())}

Strengths:
{chr(10).join(f"- {s}" for s in analysis.strengths)}

Weaknesses:
{chr(10).join(f"- {w}" for w in analysis.weaknesses)}

Meta Matchups:
{chr(10).join(f"- {m.archetype}: {m.win_rate}% ({('Favorable' if m.favorable else 'Unfavorable')})" for m in analysis.meta_matchups)}

Overall Score: {analysis.overall_score}/100
"""
    
    return [TextContent(type="text", text=result)]


async def handle_optimize_deck(arguments: dict) -> list[TextContent]:
    """Handle optimize_deck tool call."""
    deck_id = arguments["deck_id"]
    deck = await sql_service.get_deck(deck_id)
    
    if not deck:
        return [TextContent(type="text", text=f"Deck {deck_id} not found")]
    
    analysis = analyzer.analyze_deck(deck)
    suggestions = await inference_service.generate_suggestions(deck, analysis)
    prediction = await inference_service.predict_win_rate(deck, suggestions)
    
    result = f"""Deck Optimization for '{deck.name}'
==========================================

Current Overall Score: {analysis.overall_score}/100

Suggestions:
"""
    for i, sugg in enumerate(suggestions, 1):
        result += f"\n{i}. {sugg.type.upper()}: {sugg.card_name}"
        if sugg.replacement_for:
            result += f" (replaces {sugg.replacement_for})"
        result += f"\n   Reason: {sugg.reason}"
        result += f"\n   Impact Score: {sugg.impact_score}/100\n"
    
    result += f"\nPredicted Win Rate: {prediction.get('predicted_win_rate', 'N/A')}%"
    result += f"\nConfidence: {prediction.get('confidence', 'N/A')}"
    
    return [TextContent(type="text", text=result)]


async def handle_get_deck_stats(arguments: dict) -> list[TextContent]:
    """Handle get_deck_stats tool call."""
    deck_id = arguments["deck_id"]
    memory_service = SmartMemoryService(sql_service)
    stats = await memory_service.get_deck_statistics(deck_id)
    insights = await memory_service.get_learning_insights(deck_id)
    
    result = f"""Performance Statistics
======================

Total Matches: {stats['total_matches']}
Win Rate: {stats['win_rate']}%
Games Won: {stats['games_won']}
Games Lost: {stats['games_lost']}

Recent Form: {' '.join(stats.get('recent_form', []))}

Matchup Statistics:
"""
    for archetype, matchup_stats in stats.get('matchup_stats', {}).items():
        result += f"- {archetype}: {matchup_stats['win_rate']}% ({matchup_stats['matches_played']} matches)\n"
    
    result += "\nInsights:\n"
    for insight in insights:
        result += f"- {insight}\n"
    
    return [TextContent(type="text", text=result)]


async def handle_record_match(arguments: dict) -> list[TextContent]:
    """Handle record_match tool call."""
    deck_id = arguments["deck_id"]
    await sql_service.record_performance(
        deck_id=deck_id,
        opponent_archetype=arguments["opponent_archetype"],
        result=arguments["result"],
        games_won=arguments["games_won"],
        games_lost=arguments["games_lost"],
        notes=arguments.get("notes", "")
    )
    
    return [TextContent(
        type="text",
        text=f"Match result recorded successfully for deck {deck_id}"
    )]


async def handle_find_similar_cards(arguments: dict) -> list[TextContent]:
    """Handle find_similar_cards tool call."""
    deck_id = arguments["deck_id"]
    card_name = arguments["card_name"]
    top_k = arguments.get("top_k", 5)
    
    deck = await sql_service.get_deck(deck_id)
    if not deck:
        return [TextContent(type="text", text=f"Deck {deck_id} not found")]
    
    # Find target card
    target_card = None
    for card in deck.mainboard:
        if card.name.lower() == card_name.lower():
            target_card = card
            break
    
    if not target_card:
        return [TextContent(type="text", text=f"Card '{card_name}' not found in deck")]
    
    # Find similar cards
    similar = embeddings_service.find_similar_cards(
        target_card, deck.mainboard, top_k
    )
    
    result = f"Similar cards to '{card_name}':\n"
    for i, item in enumerate(similar, 1):
        result += f"{i}. {item['card'].name} (similarity: {item['similarity']:.2f})\n"
    
    return [TextContent(type="text", text=result)]


async def handle_list_decks(arguments: dict) -> list[TextContent]:
    """Handle list_decks tool call."""
    format_filter = arguments.get("format")
    decks = await sql_service.list_decks(format=format_filter)
    
    if not decks:
        return [TextContent(type="text", text="No decks found")]
    
    result = "Stored Decks:\n"
    for deck in decks:
        result += f"- ID {deck['id']}: {deck['name']} ({deck['format']}) - {deck['created_at']}\n"
    
    return [TextContent(type="text", text=result)]


@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="parse_deck_csv",
            description="Parse MTG Arena deck from CSV export",
            inputSchema={
                "type": "object",
                "properties": {
                    "csv_content": {
                        "type": "string",
                        "description": "CSV content from Steam MTG Arena export"
                    }
                },
                "required": ["csv_content"]
            }
        ),
        Tool(
            name="parse_deck_text",
            description="Parse MTG Arena deck from text format",
            inputSchema={
                "type": "object",
                "properties": {
                    "deck_string": {
                        "type": "string",
                        "description": "Deck list in Arena format (e.g., '4 Lightning Bolt (M11) 146')"
                    },
                    "format": {
                        "type": "string",
                        "description": "Format (Standard, Historic, etc.)",
                        "default": "Standard"
                    }
                },
                "required": ["deck_string"]
            }
        ),
        Tool(
            name="analyze_deck",
            description="Analyze deck composition, mana curve, and meta matchups",
            inputSchema={
                "type": "object",
                "properties": {
                    "deck_id": {
                        "type": "integer",
                        "description": "Database ID of the deck to analyze"
                    }
                },
                "required": ["deck_id"]
            }
        ),
        Tool(
            name="optimize_deck",
            description="Get AI-powered deck optimization suggestions with win-rate predictions",
            inputSchema={
                "type": "object",
                "properties": {
                    "deck_id": {
                        "type": "integer",
                        "description": "Database ID of the deck to optimize"
                    }
                },
                "required": ["deck_id"]
            }
        ),
        Tool(
            name="get_deck_stats",
            description="Get historical performance statistics for a deck",
            inputSchema={
                "type": "object",
                "properties": {
                    "deck_id": {
                        "type": "integer",
                        "description": "Database ID of the deck"
                    }
                },
                "required": ["deck_id"]
            }
        ),
        Tool(
            name="record_match",
            description="Record a match result for performance tracking",
            inputSchema={
                "type": "object",
                "properties": {
                    "deck_id": {
                        "type": "integer",
                        "description": "Database ID of the deck"
                    },
                    "opponent_archetype": {
                        "type": "string",
                        "description": "Opponent's deck archetype"
                    },
                    "result": {
                        "type": "string",
                        "enum": ["win", "loss", "draw"],
                        "description": "Match result"
                    },
                    "games_won": {
                        "type": "integer",
                        "description": "Number of games won"
                    },
                    "games_lost": {
                        "type": "integer",
                        "description": "Number of games lost"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes about the match",
                        "default": ""
                    }
                },
                "required": ["deck_id", "opponent_archetype", "result", "games_won", "games_lost"]
            }
        ),
        Tool(
            name="find_similar_cards",
            description="Find similar cards using embeddings for deck building",
            inputSchema={
                "type": "object",
                "properties": {
                    "card_name": {
                        "type": "string",
                        "description": "Name of the card to find similar cards for"
                    },
                    "deck_id": {
                        "type": "integer",
                        "description": "Deck ID to search within"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of similar cards to return",
                        "default": 5
                    }
                },
                "required": ["card_name", "deck_id"]
            }
        ),
        Tool(
            name="list_decks",
            description="List all stored decks",
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "description": "Optional format filter (Standard, Historic, etc.)"
                    }
                }
            }
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls by dispatching to appropriate handler."""
    # Tool handler mapping
    handlers = {
        "parse_deck_csv": handle_parse_deck_csv,
        "parse_deck_text": handle_parse_deck_text,
        "analyze_deck": handle_analyze_deck,
        "optimize_deck": handle_optimize_deck,
        "get_deck_stats": handle_get_deck_stats,
        "record_match": handle_record_match,
        "find_similar_cards": handle_find_similar_cards,
        "list_decks": handle_list_decks,
    }
    
    try:
        handler = handlers.get(name)
        if handler:
            return await handler(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Run the MCP server."""
    # Initialize database
    await sql_service.init_db()
    
    # Run server
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
