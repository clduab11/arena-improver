# Arena Improver

**MCP for Magic: The Gathering Arena** - AI-powered deck analysis and optimization platform

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0.html)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

## 🎯 Overview

Arena Improver is a comprehensive Model Context Protocol (MCP) server for Magic: The Gathering Arena deck analysis and **strategic optimization**. It leverages cutting-edge MCP integrations (Tavily, Exa, Mem0, Sequential Thinking) to provide **real-time meta intelligence**, AI-powered deck recommendations, and historical performance tracking tailored specifically for MTG Arena on Steam.

**Strategic Focus:** This tool goes beyond basic deck analysis to provide actionable strategic insights based on current meta trends, tournament data, and professional play patterns.

### Key Features

#### 🎮 Steam Arena Integration
- **📊 CSV Import**: Native support for Steam MTG Arena deck exports
- **🖥️ Platform Optimization**: Steam-specific strategy adjustments and matchmaking awareness
- **📝 Flexible Formats**: Support for both CSV and Arena text format imports

#### 🧠 Advanced MCP-Powered Strategy
- **🔍 Real-Time Meta Intelligence** (via Tavily/Exa):
  - Live meta share data from MTGGoldfish, AetherHub
  - Current tournament results and professional decklists
  - Ban list updates and format changes
  - Emerging archetype detection

- **💭 Sequential Thinking** (via MCP):
  - Multi-step deck building decision analysis
  - Complex sideboard strategy reasoning
  - Metagame positioning evaluation

- **🧠 Memory Integration** (via Mem0):
  - Long-term performance pattern learning
  - Player-specific strategy preferences
  - Meta evolution tracking
  - Successful tech choice memory

#### 📊 Comprehensive Deck Analysis
- **Mana Curve Optimization**: Ideal CMC distribution analysis
- **Meta Matchup Predictions**: Win rates vs. current meta archetypes
- **Card Synergy Detection**: AI-powered combination identification
- **Color Distribution Analysis**: Mana consistency evaluation
- **Strategy Type Identification**: Aggro/Midrange/Control classification

#### 🤖 AI-Powered Intelligence
- **SmartInference**: OpenAI GPT-4 deck optimization with reasoning
- **SmartMemory**: Historical performance tracking and trend analysis
- **SmartSQL**: Persistent deck storage with SQLAlchemy
- **Embeddings**: Card similarity using sentence transformers

#### 🌐 Multiple Interfaces
- **MCP Protocol**: Full Model Context Protocol implementation
- **FastAPI**: RESTful API endpoints for web integration
- **Docker Support**: Containerized deployment ready

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- Node.js 18+ (for MCP servers via npx)
- Docker (optional, for containerized deployment)

**API Keys (obtain from respective providers):**
- **OpenAI API key** (required for AI recommendations)
- **Tavily API key** (recommended for meta intelligence) - [Get here](https://tavily.com/)
- **Exa API key** (recommended for semantic search) - [Get here](https://exa.ai/)
- Vultr API key (optional, for cloud GPU embeddings)
- Perplexity, Jina AI, Kagi (optional, for enhanced search)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/clduab11/arena-improver.git
cd arena-improver
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys
```

**Required Configuration:**
- `OPENAI_API_KEY`: For AI-powered deck optimization
- `TAVILY_API_KEY`: For real-time meta data (highly recommended)
- `EXA_API_KEY`: For semantic card search (highly recommended)

**Optional Configuration:**
- `BRAVE_API_KEY`, `PERPLEXITY_API_KEY`, `JINA_AI_API_KEY`: Enhanced search
- `META_UPDATE_FREQUENCY`: How often to refresh meta data (default: 24 hours)
- `STEAM_PLATFORM_ENABLED`: Enable Steam-specific optimizations (default: true)

4. Initialize the database:
```bash
python -c "import asyncio; from src.services.smart_sql import SmartSQLService; asyncio.run(SmartSQLService().init_db())"
```

5. **(Recommended)** Set up MCP servers for enhanced strategy features:

The `mcp_config.json` file at the root contains configuration for:
- **Memory MCP**: Long-term learning and pattern recognition
- **Sequential Thinking MCP**: Complex decision analysis
- **cld-omnisearch MCP**: Real-time meta intelligence via Tavily/Exa

These will be automatically available when using Claude Desktop or other MCP-compatible clients.

### Running the Services

#### FastAPI Server

Start the REST API server:
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Access the API documentation at: `http://localhost:8000/docs`

#### MCP Server

Run the MCP protocol server:
```bash
python -m src.mcp_server
```

#### Docker Deployment

Build and run with Docker Compose:
```bash
docker-compose up --build
```

## 📖 Usage

### FastAPI Endpoints

#### Upload a Deck (CSV)
```bash
curl -X POST "http://localhost:8000/api/v1/upload/csv" \
  -F "file=@my_deck.csv"
```

#### Upload a Deck (Text Format)
```bash
curl -X POST "http://localhost:8000/api/v1/upload/text" \
  -H "Content-Type: application/json" \
  -d '{
    "deck_string": "4 Lightning Bolt (M11) 146\n20 Mountain (ZNR) 381",
    "format": "Standard"
  }'
```

#### Analyze a Deck
```bash
curl -X POST "http://localhost:8000/api/v1/analyze/1"
```

#### Optimize a Deck
```bash
curl -X POST "http://localhost:8000/api/v1/optimize/1"
```

#### Get Deck Statistics
```bash
curl -X GET "http://localhost:8000/api/v1/stats/1"
```

#### Record Match Performance
```bash
curl -X POST "http://localhost:8000/api/v1/performance/1" \
  -H "Content-Type: application/json" \
  -d '{
    "opponent_archetype": "Mono-Red Aggro",
    "result": "win",
    "games_won": 2,
    "games_lost": 1,
    "notes": "Sideboard strategy worked well"
  }'
```

### MCP Tools

The MCP server provides the following tools:

- `parse_deck_csv` - Parse deck from CSV export
- `parse_deck_text` - Parse deck from Arena text format
- `analyze_deck` - Analyze deck composition
- `optimize_deck` - Get AI-powered optimization suggestions
- `get_deck_stats` - Retrieve historical performance
- `record_match` - Log match results
- `find_similar_cards` - Find cards using embeddings
- `list_decks` - List all stored decks

### Example Workflow

```python
import asyncio
from src.services.deck_analyzer import DeckAnalyzer
from src.services.smart_sql import SmartSQLService
from src.utils.csv_parser import parse_deck_string

async def analyze_my_deck():
    # Parse a deck
    deck_string = """
    4 Lightning Bolt (M11) 146
    4 Monastery Swiftspear (KTK) 118
    20 Mountain (ZNR) 381
    """
    
    deck = parse_deck_string(deck_string)
    
    # Store in database
    sql_service = SmartSQLService()
    await sql_service.init_db()
    deck_id = await sql_service.store_deck(deck)
    
    # Analyze
    analyzer = DeckAnalyzer()
    analysis = analyzer.analyze_deck(deck)
    
    print(f"Overall Score: {analysis.overall_score}/100")
    print(f"Strengths: {analysis.strengths}")
    print(f"Weaknesses: {analysis.weaknesses}")

asyncio.run(analyze_my_deck())
```

### Strategic Analysis with Meta Intelligence

```python
import asyncio
from src.services.meta_intelligence import MetaIntelligenceService
from src.services.deck_analyzer import DeckAnalyzer
from src.services.smart_sql import SmartSQLService

async def meta_aware_analysis():
    # Get current meta snapshot
    meta_service = MetaIntelligenceService()
    meta = await meta_service.get_current_meta("Standard")

    print(f"Current Meta:")
    print(f"- Top Archetype: {meta.archetypes[0].name} ({meta.archetypes[0].meta_share}%)")
    print(f"- Win Rate: {meta.archetypes[0].win_rate}%")
    print(f"- Meta Health: {meta.meta_trends['meta_health']}")

    # Analyze deck against current meta
    analyzer = DeckAnalyzer(meta_service=meta_service)
    sql_service = SmartSQLService()
    await sql_service.init_db()
    deck = await sql_service.get_deck(1)
    analysis = await analyzer.analyze_deck(deck)

    print(f"\nYour Deck vs. Meta:")
    for matchup in analysis.meta_matchups:
        status = "✓ Favorable" if matchup.favorable else "✗ Unfavorable"
        print(f"{status} vs {matchup.archetype}: {matchup.win_rate}%")

asyncio.run(meta_aware_analysis())
```

## 🎮 Steam Arena Integration

Arena Improver is **optimized for MTG Arena on Steam** with platform-specific features:

- **Native CSV Import**: Direct support for Steam Arena deck exports
- **Platform Awareness**: Matchmaking and performance tracking specific to Steam
- **Bo1/Bo3 Optimization**: Automatic strategy adjustment for ladder vs. events
- **Collection Integration**: Future support for Steam inventory tracking

**See the complete guide:** [Steam Arena Platform Guide](docs/STEAM_ARENA_GUIDE.md)

### Quick Steam Export Guide

1. **In Arena:** Open your deck in the deck builder
2. **Export:** Click "Export" → Choose "CSV" format
3. **Upload to Arena Improver:**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/upload/csv" \
     -F "file=@my_deck.csv"
   ```

## 🧠 MCP-Powered Strategy Features

### Real-Time Meta Intelligence

Arena Improver uses **Tavily and Exa MCPs** to fetch live meta data:

```python
import asyncio
from src.services.meta_intelligence import MetaIntelligenceService

async def main():
    # Automatic meta data fetching
    meta_service = MetaIntelligenceService()
    snapshot = await meta_service.get_current_meta("Standard")

    # Access live data:
    # - Current meta shares from MTGGoldfish
    # - Tournament results and winning decklists
    # - Ban list updates
    # - Emerging archetypes

asyncio.run(main())
```

### Sequential Thinking for Complex Decisions

When building or optimizing decks, the **Sequential Thinking MCP** helps break down complex strategy decisions:

- Multi-step deck building reasoning
- Sideboard strategy planning
- Meta positioning analysis
- Archetype selection logic

### Memory-Enhanced Learning

The **Mem0 MCP** provides long-term learning capabilities:

- Remembers your successful strategies
- Tracks meta evolution over time
- Learns your playstyle preferences
- Identifies platform-specific patterns

## 🏗️ Architecture

```
arena-improver/
├── src/
│   ├── models/          # Pydantic models and database schemas
│   │   ├── deck.py      # Deck, Card, Analysis models
│   │   └── database.py  # SQLAlchemy models
│   ├── services/        # Core business logic
│   │   ├── deck_analyzer.py         # Deck analysis engine
│   │   ├── meta_intelligence.py     # ⭐ Real-time meta data service
│   │   ├── smart_sql.py             # Database operations
│   │   ├── smart_inference.py       # AI recommendations
│   │   ├── smart_memory.py          # Performance tracking
│   │   └── embeddings.py            # Card similarity
│   ├── api/             # FastAPI routes
│   │   └── routes.py
│   ├── utils/           # Utility functions
│   │   ├── csv_parser.py
│   │   └── mana_calculator.py
│   ├── main.py          # FastAPI application
│   └── mcp_server.py    # MCP protocol server
├── docs/                # ⭐ Documentation
│   └── STEAM_ARENA_GUIDE.md  # Steam platform guide
├── tests/
│   ├── unit/            # Unit tests
│   └── integration/     # Integration tests
├── data/                # SQLite database storage
├── mcp_config.json      # ⭐ MCP server configuration
├── requirements.txt
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml
```

**⭐ = New strategic enhancements**

## 🧪 Testing

Run the test suite:

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# With coverage
pytest --cov=src --cov-report=html
```

## 📊 Analysis Features

### Mana Curve Analysis
- Distribution visualization
- Average and median CMC
- Curve scoring (0-100)
- Recommendations for optimization

### Card Synergies
- Automatic synergy detection
- Combo identification
- Support relationships
- Anti-synergy warnings

### Meta Matchup Analysis (Real-Time)
- **Live meta data** from MTGGoldfish, AetherHub via Tavily/Exa MCPs
- Win rate predictions vs. **current** meta archetypes (not hardcoded!)
- Favorable/unfavorable matchup identification based on **real tournament data**
- Dynamic sideboard suggestions per matchup
- Key cards for each matchup from professional lists
- Meta health assessment and diversity tracking

### Performance Tracking
- Match-by-match history
- Win rate statistics
- Matchup-specific performance
- Trend analysis over time
- Learning insights

## 🤖 AI Features

### SmartInference
Uses OpenAI GPT-4 to:
- Generate specific card suggestions
- Explain reasoning for each suggestion
- Predict impact of changes
- Estimate win rate improvements

### SmartMemory
Tracks and learns from:
- Historical match results
- Performance trends
- Archetype-specific outcomes
- Deck evolution over time

### Embeddings
Semantic card similarity using:
- Sentence transformers
- Vector embeddings
- Cosine similarity
- Replacement card suggestions

## 🔧 Configuration

### Environment Variables

```bash
# OpenAI API (for AI recommendations)
OPENAI_API_KEY=your_key_here

# Vultr API (for GPU embeddings)
VULTR_API_KEY=your_key_here

# Database
DATABASE_URL=sqlite:///./data/arena_improver.db
```

## 📦 Docker

### Build and Run

```bash
docker build -t arena-improver .
docker run -p 8000:8000 -p 8001:8001 \
  -e OPENAI_API_KEY=your_key \
  -v $(pwd)/data:/app/data \
  arena-improver
```

### Docker Compose

```bash
docker-compose up -d
```

## 📚 Documentation

- **[Steam Arena Platform Guide](docs/STEAM_ARENA_GUIDE.md)**: Complete guide for Steam users
- **[MCP Configuration](mcp_config.json)**: MCP server setup for Claude Desktop
- **[API Documentation](http://localhost:8000/docs)**: Interactive API docs (when server running)

## 🎯 Strategy Philosophy

Arena Improver focuses on **actionable strategic insights** rather than just deck statistics:

1. **Meta-Aware**: All recommendations consider the current metagame
2. **Platform-Specific**: Optimized for Steam Arena's unique environment
3. **Data-Driven**: Uses real tournament results and professional play data
4. **Adaptive**: Learns from your playstyle and performance history
5. **Transparent**: Explains reasoning behind all suggestions

## 🤝 Contributing

Contributions are welcome! Especially:

- **Meta Intelligence**: Enhance web scraping and meta data sources
- **Strategy Algorithms**: Improve matchup prediction models
- **MCP Integrations**: Add new MCP capabilities
- **Steam Features**: Platform-specific enhancements
- **Testing**: Add test coverage for strategy services

### Development Setup

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Install dev dependencies: `pip install -r requirements.txt`
4. Run tests: `pytest`
5. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
6. Push to the branch (`git push origin feature/AmazingFeature`)
7. Open a Pull Request

## 📝 License

This project is licensed under the AGPL-3.0 License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Magic: The Gathering Arena by Wizards of the Coast
- OpenAI for GPT models
- Sentence Transformers for embeddings
- FastAPI framework
- Model Context Protocol (MCP) specification

## 📧 Contact

Project Link: [https://github.com/clduab11/arena-improver](https://github.com/clduab11/arena-improver)

---

**Hackathon Submission**: LiquidMetal/Raindrop
