# Arena Improver

**MCP for Magic: The Gathering Arena** - AI-powered deck analysis and optimization platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

## 🎯 Overview

Arena Improver is a comprehensive Model Context Protocol (MCP) server for Magic: The Gathering Arena deck analysis. It combines AI-powered recommendations, historical performance tracking, and semantic card similarity to help players optimize their decks and improve win rates.

### Key Features

- **📊 CSV Import**: Accepts deck exports from Steam MTG Arena in CSV format
- **🔍 Deck Analysis**: 
  - Mana curve optimization
  - Card synergy detection
  - Meta matchup predictions
  - Color distribution analysis
- **🧠 AI Integration**:
  - **SmartSQL**: Persistent deck storage with SQLite/SQLAlchemy
  - **SmartInference**: OpenAI-powered deck optimization suggestions
  - **SmartMemory**: Historical performance tracking and trend analysis
- **🚀 Vultr GPU**: Card similarity embeddings using sentence transformers
- **🌐 FastAPI**: RESTful API endpoints for deck upload and analysis
- **📈 Win-Rate Predictions**: ML-based performance predictions
- **🔌 MCP Protocol**: Full Model Context Protocol implementation

## 🚀 Quick Start

### Prerequisites

- Python 3.9 or higher
- Docker (optional, for containerized deployment)
- OpenAI API key (optional, for AI recommendations)
- Vultr API key (optional, for cloud GPU embeddings)

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

4. Initialize the database:
```bash
python -c "import asyncio; from src.services.smart_sql import SmartSQLService; asyncio.run(SmartSQLService().init_db())"
```

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

## 🏗️ Architecture

```
arena-improver/
├── src/
│   ├── models/          # Pydantic models and database schemas
│   │   ├── deck.py      # Deck, Card, Analysis models
│   │   └── database.py  # SQLAlchemy models
│   ├── services/        # Core business logic
│   │   ├── deck_analyzer.py      # Deck analysis engine
│   │   ├── smart_sql.py          # Database operations
│   │   ├── smart_inference.py    # AI recommendations
│   │   ├── smart_memory.py       # Performance tracking
│   │   └── embeddings.py         # Card similarity
│   ├── api/             # FastAPI routes
│   │   └── routes.py
│   ├── utils/           # Utility functions
│   │   ├── csv_parser.py
│   │   └── mana_calculator.py
│   ├── main.py          # FastAPI application
│   └── mcp_server.py    # MCP protocol server
├── tests/
│   ├── unit/            # Unit tests
│   └── integration/     # Integration tests
├── data/                # SQLite database storage
├── requirements.txt
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml
```

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

### Meta Matchup Analysis
- Win rate predictions vs. meta archetypes
- Favorable/unfavorable matchup identification
- Sideboard suggestions per matchup
- Key cards for each matchup

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

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

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
