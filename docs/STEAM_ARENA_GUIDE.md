# Steam Arena Platform Guide

This guide covers Steam-specific considerations and optimizations for MTG Arena Improver.

## Steam Platform Overview

Magic: The Gathering Arena on Steam provides a unique environment with specific behaviors, export formats, and platform-specific quirks that this tool is designed to handle.

## Deck Export from Steam Arena

### CSV Export Format

Steam Arena allows exporting decks in CSV format. The expected format is:

```csv
Quantity,Name,Set,Collector Number
4,Lightning Bolt,M11,146
4,Monastery Swiftspear,KTK,118
20,Mountain,ZNR,381
```

### Using the Export Feature

1. **In Arena:** Open your deck in the deck builder
2. **Export:** Click the "Export" button
3. **Format:** Choose "CSV" format
4. **Save:** Save the file to your local machine
5. **Upload:** Use the Arena Improver API or MCP tools to upload

### Example Upload via API

```bash
curl -X POST "http://localhost:8000/api/v1/upload/csv" \
  -F "file=@my_deck.csv"
```

### Example Upload via MCP

```python
# Using the MCP tool with async file I/O
# Note: Install aiofiles first: pip install aiofiles
import aiofiles

async with aiofiles.open("my_deck.csv", mode='r') as f:
    csv_content = await f.read()
    result = await mcp_tool("parse_deck_csv", {
        "csv_content": csv_content
    })
```

## Steam-Specific Considerations

### 1. Platform Performance

**Issue:** Steam overlay and platform integration can affect game performance.

**Strategy Impact:**
- Favor consistent, reliable strategies over high-risk plays
- Account for potential connection issues in Bo3 matches
- Consider sideboards with flexible answers rather than specific counters

### 2. Matchmaking Behavior

**Observation:** Steam Arena matchmaking may have slightly different patterns than standalone client.

**Recommendations:**
- Track your matchup data specifically on Steam
- Use the performance tracking features to identify platform-specific trends
- Report discrepancies between expected and actual matchup frequencies

### 3. Collection Management

**Sync Considerations:**
- Arena Improver can help track which cards you own
- Consider budget constraints when evaluating suggestions
- Wildcard efficiency is tracked in optimization recommendations

### 4. Tournament Practice vs. Ladder Play

**Steam Arena Ladder:**
- Best-of-1 (Bo1) is more common on Steam
- Deck lists should be optimized for Bo1 when not playing events
- Sideboard suggestions adapt based on format

**Event Play:**
- Best-of-3 (Bo3) in traditional events
- Full sideboard strategies recommended
- Meta positioning becomes more important

## Strategy Recommendations for Steam Players

### For Bo1 (Ladder)

```python
# Configure for Bo1 optimization
{
    "format": "Standard",
    "best_of": 1,
    "optimize_for": "consistency",
    "sideboard": False
}
```

**Key Focus:**
- Mainboard versatility
- Consistent mana base
- Game 1 powerhouse cards
- Proactive strategies over reactive

### For Bo3 (Events)

```python
# Configure for Bo3 optimization
{
    "format": "Standard",
    "best_of": 3,
    "optimize_for": "matchups",
    "sideboard": True
}
```

**Key Focus:**
- Transformational sideboards
- Meta-specific hate cards
- Matchup win-rate optimization
- Strategic flexibility

## Integration with Arena Improver Features

### Prerequisites

Before running the code examples below, ensure you have the necessary services initialized. The following code uses async/await and should be placed inside an async function or executed using `asyncio.run()` (see `examples/example_workflow.py` for a complete example):

```python
import asyncio
from src.services.meta_intelligence import MetaIntelligenceService
from src.services.smart_sql import SmartSQLService

async def main():
    # Initialize services
    meta_service = MetaIntelligenceService()
    sql_service = SmartSQLService()
    
    # Initialize the database (creates tables if they don't exist)
    await sql_service.init_db()
    
    # Your code using the services goes here
    # ...

if __name__ == "__main__":
    asyncio.run(main())
```

### Error Handling Best Practices

When working with Arena Improver services, proper error handling is essential for robust applications:

```python
import asyncio
import logging
from src.services.meta_intelligence import MetaIntelligenceService
from src.services.smart_sql import SmartSQLService
from src.exceptions import MetaDataUnavailableError

logger = logging.getLogger(__name__)

async def main():
    meta_service = MetaIntelligenceService()
    sql_service = SmartSQLService()
    
    try:
        # Initialize database with error handling
        await sql_service.init_db()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return
    
    try:
        # Fetch meta data with fallback handling
        snapshot = await meta_service.get_current_meta("Standard")
        print(f"Top archetype: {snapshot.archetypes[0].name}")
    except MetaDataUnavailableError as e:
        logger.warning(f"Meta data unavailable: {e}")
        # Handle gracefully - use cached data or continue without meta analysis
        print("Proceeding without current meta data")
    except Exception as e:
        logger.error(f"Unexpected error fetching meta data: {e}")
    finally:
        # Always cleanup resources
        await sql_service.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Real-Time Meta Analysis

Arena Improver uses MCP tools to fetch current meta data specific to Arena:

```python
# Assuming meta_service is initialized (see Prerequisites above)
snapshot = await meta_service.get_current_meta("Standard")

print(f"Current top archetype: {snapshot.archetypes[0].name}")
print(f"Meta share: {snapshot.archetypes[0].meta_share}%")
```

### Steam Platform Optimization

Enable Steam-specific features in your `.env`:

```bash
STEAM_PLATFORM_ENABLED=true
```

This enables:
- Steam CSV format recognition
- Platform-specific heuristics
- Matchmaking trend analysis
- Collection synchronization (future feature)

### Performance Tracking

Track your performance specifically on Steam:

```python
# Assuming sql_service is initialized (see Prerequisites above)
await sql_service.record_performance(
    deck_id=1,
    opponent_archetype="Boros Convoke",
    result="win",
    games_won=2,
    games_lost=1,
    notes="Steam platform - good matchup"
)
```

### Meta-Aware Deck Building

Use the MetaIntelligenceService for strategy decisions:

```python
# Assuming meta_service is initialized (see Prerequisites above)
# Get matchup data for your deck
matchups = await meta_service.get_archetype_matchup_data(
    deck_archetype="Dimir Midrange",
    format="Standard"
)

# Review favorable matchups
for opponent, win_rate in matchups.items():
    if win_rate >= 55:
        print(f"Good matchup: {opponent} ({win_rate}%)")
```

## Common Issues and Solutions

### Issue: Deck Import Fails

**Solution:**
1. Verify CSV format matches Steam Arena export
2. Check for special characters in card names
3. Ensure set codes are valid
4. Try the text format as alternative:

```bash
curl -X POST "http://localhost:8000/api/v1/upload/text" \
  -H "Content-Type: application/json" \
  -d '{
    "deck_string": "4 Lightning Bolt\n20 Mountain",
    "format": "Standard"
  }'
```

### Issue: Meta Data Seems Outdated

**Solution:**
1. Check `META_UPDATE_FREQUENCY` in `.env`
2. Clear cache manually if needed
3. Verify API keys for Tavily/Exa are set
4. Check service logs for fetch errors

### Issue: Win Rate Predictions Inaccurate

**Solution:**
1. Record more match data for better predictions
2. Ensure opponent archetypes are correctly identified
3. Update meta snapshot to reflect current environment
4. Check if playing Bo1 vs Bo3 (affects predictions)

## Advanced Features

### MCP-Powered Strategy Research

Use Sequential Thinking MCP for complex deck building:

```python
# Multi-step deck optimization reasoning
# This uses the Sequential Thinking MCP to break down
# complex deck building decisions into manageable steps
```

### Memory-Enhanced Performance Tracking

Use Mem0 MCP for long-term strategy memory:

```python
# Mem0 remembers:
# - Your playstyle preferences
# - Successful tech choices
# - Meta evolution over time
# - Platform-specific patterns
```

### Real-Time Meta Intelligence

Use Tavily/Exa MCPs for current strategy data:

```python
# Fetches:
# - Current tournament results
# - Pro player deck lists
# - Format ban updates
# - Emerging archetypes
```

## Best Practices

1. **Regular Data Updates**
   - Export and analyze decks weekly
   - Track performance after each session
   - Update meta data before events

2. **Leverage MCP Tools**
   - Use Tavily for meta research
   - Use Exa for card synergy discovery
   - Use Sequential Thinking for complex decisions
   - Use Mem0 for learning from history

3. **Platform-Specific Optimization**
   - Enable Steam platform mode
   - Track Steam-specific matchup data
   - Adjust for Bo1/Bo3 appropriately

4. **Continuous Improvement**
   - Review analysis suggestions
   - Test optimizations in practice
   - Iterate based on results
   - Share successful strategies

## Contributing

Found a Steam-specific issue or have a strategy tip? Contribute to the project:

1. Open an issue on GitHub
2. Share your deck data and performance
3. Suggest platform-specific features
4. Help improve meta analysis

## Resources

- [MTG Arena on Steam](https://store.steampowered.com/app/2141910/)
- [MTGGoldfish Metagame](https://www.mtggoldfish.com/metagame/)
- [AetherHub Meta](https://aetherhub.com/Metagame/)
- [Arena Improver GitHub](https://github.com/clduab11/arena-improver)

---

**Need Help?** Open an issue on GitHub or check the main README for setup instructions.
