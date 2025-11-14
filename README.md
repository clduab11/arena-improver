# Arena Improver

*"Your deck's terrible. Let me show you how to fix it."*
— **Vawlrathh, The Small'n**

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0.html)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Hackathon: MCP 1st Birthday](https://img.shields.io/badge/Hackathon-MCP%201st%20Birthday-purple.svg)](https://huggingface.co/MCP-1st-Birthday)
[![HF Space](https://img.shields.io/badge/🤗-Hugging%20Face%20Space-yellow.svg)](https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath)

## 🎯 What This Is

Listen up. I'm **Vawlrathh, The Small'n**—a pint-sized, sharp-tongued version of Volrath, The Fallen. Despite my stature, I know MTG Arena better than you know your own deck (which, frankly, isn't saying much).

**Arena Improver** is an MCP-powered deck analysis tool that actually works. It analyzes your janky brews, tells you what's wrong (plenty), and helps you build something that won't embarrass you at FNM.

Designed for **Steam Arena players** who want to win games, not just collect pretty digital cards.

### What Makes This Not-Garbage

- **Physical Card Prices**: Shows you what your Arena deck costs in real cardboard (excludes Arena-only nonsense)
- **Real-Time Strategy Chat**: Talk to me via WebSocket. I'll tell you the truth, even if you don't want to hear it
- **AI Consensus Checking**: Two AI brains (mine and a validator) so you don't get bad advice
- **Sequential Reasoning**: Breaks down complex decisions into steps even you can follow
- **Full MCP Integration**: Memory, sequential thinking, omnisearch—the works

---

## 🚀 Quick Start

### What You Need

Don't skip this part. I hate repeating myself.

- Python 3.9+ (If you're still on 2.7, we have bigger problems)
- Node.js 18+ (For MCP servers)
- Docker (Optional, for the lazy)

**API Keys** (Get these or nothing works):
- **OpenAI**: For the smart stuff
- **Anthropic**: For consensus checking
- **Tavily/Exa**: For meta intelligence (highly recommended)

### Installation

```bash
# Clone it
git clone https://github.com/clduab11/arena-improver.git
cd arena-improver

# Install dependencies
pip install -r requirements.txt

# Set up your keys
cp .env.example .env
# Edit .env with your API keys. All of them.

# Initialize database
python -c "import asyncio; from src.services.smart_sql import SmartSQLService; asyncio.run(SmartSQLService().init_db())"
```

Done? Good. Moving on.

---

## 🚀 Try It Now

Want to see it in action without installing anything? Check out the **[Hugging Face Space](https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath)**!

The Space provides:
- **Interactive API Documentation**: Test all endpoints directly in your browser
- **Live Demo**: See Vawlrathh in action
- **No Setup Required**: Just visit and start using
- **Auto-Synced**: Always running the latest code from the main branch

---

## 💬 Meet Vawlrathh (That's Me)

I'm not your friend. I'm your strategic advisor. Here's how I work:

### Personality Traits

- **Dry-Witted**: Sarcasm is my first language
- **Brusque**: No fluff, no sugar-coating
- **Pragmatic**: If it works, it's good. If it doesn't, it's trash
- **Knowledgeable**: Volrath's cunning, just... shorter

### Example Interactions

**You**: "Rate my deck"
**Me**: "Your mana curve's a disaster. Fix it."

**You**: "Should I play best-of-one or best-of-three?"
**Me**: "If you have to ask, stick to Bo1. Less time to screw up."

**You**: "What do you think of my sideboard?"
**Me**: "I've seen better sideboards from goblins. Try again."

---

## 🛠️ Core Features

### 1. Physical Card Purchase Integration

**Problem**: You want to build your Arena deck in paper, but half the cards don't exist.

**Solution**: I check every card, filter out Arena-only garbage, and show you prices from TCGPlayer, CardMarket, and Cardhoarder.

```bash
# Get purchase info for deck ID 1
curl -X GET "http://localhost:8000/api/v1/purchase/1"
```

**Response includes**:
- Total deck cost (only real cards)
- Per-card pricing
- Vendor comparisons
- Arena-only card warnings

### 2. Real-Time Chat (Talk to Me)

WebSocket endpoint: `ws://localhost:8000/api/v1/ws/chat/{your_id}`

**Message Format**:
```json
{
  "type": "chat",
  "message": "How do I beat control decks?",
  "context": {
    "deck_id": 1
  }
}
```

**Response**:
```json
{
  "type": "response",
  "response": "Pack hand disruption. Duress is cheap. Use it.",
  "consensus_checked": true,
  "consensus_passed": true
}
```

If I say something wrong (rare), you'll get a `ConsensusBreaker` warning. Pay attention to those.

### 3. Deck Analysis That Doesn't Lie

```bash
POST /api/v1/analyze/1
```

Gets you:
- Mana curve (yours is probably bad)
- Meta matchups (real tournament data)
- Card synergies
- Weaknesses (plenty to choose from)
- **Physical card purchase info** (automatically included)

### 4. AI-Powered Optimization

```bash
POST /api/v1/optimize/1
```

I'll suggest:
- Cards to add
- Cards to cut
- Why each change matters
- Predicted win rate improvement
- Purchase links for suggested cards

### 5. Sequential Reasoning

For complex decisions (like "should I build this deck?"), I break it down:

1. What's the win condition?
2. What are the mana requirements?
3. Which meta decks do you need to beat?
4. What are the critical early plays?
5. What sideboard cards are essential?
6. What's the optimal curve?

Each step gets analyzed. You get conclusions you can actually use.

---

## 📊 MCP Integration

### Available Tools

I come with 9 MCP tools. Use them.

1. **parse_deck_csv**: Import from Steam Arena
2. **parse_deck_text**: Import from Arena text format
3. **analyze_deck**: Full deck analysis
4. **optimize_deck**: AI-powered suggestions
5. **get_deck_stats**: Performance history
6. **record_match**: Track your games
7. **find_similar_cards**: Embeddings-based search
8. **list_decks**: See what you've stored
9. **find_card_market_links**: Get purchase info (NEW!)

### External MCP Servers

Configured in `mcp_config.json`:

- **Memory**: I remember your past mistakes
- **Sequential Thinking**: For complex reasoning
- **cld-omnisearch**: Real-time meta data (Tavily/Exa)

---

## 🎮 Steam Arena Focus

This tool is built for Steam Arena. Here's why that matters:

- **CSV Import**: Native Steam export support
- **Platform-Specific Meta**: Steam ladder is different from Magic Online
- **Bo1 vs Bo3**: Strategy adjusts based on queue type
- **Collection Integration**: Coming soon—sync your Steam collection

### Quick Steam Export

1. Open your deck in Arena (Steam version)
2. Click "Export" → Choose "CSV"
3. Upload to Arena Improver:

```bash
curl -X POST "http://localhost:8000/api/v1/upload/csv" \
  -F "file=@my_deck.csv"
```

Done. Moving on.

---

## 🏗️ Architecture

Not boring you with flowcharts. Here's what matters:

```
Your Request
    ↓
FastAPI (async, fast)
    ↓
├─ Deck Analyzer (mana curves, synergies)
├─ Card Market Service (Scryfall + pricing)
├─ Vawlrathh Chat Agent (GPT-4/Haiku + Sonnet consensus)
├─ Sequential Reasoning (chain-of-thought)
└─ Event Logger (tracks everything)
    ↓
Results (useful ones)
```

**Key Tech**:
- Async/await everywhere
- WebSocket for chat
- SQLite for storage
- MCP protocol compliance
- Full test coverage

---

## 🧪 Testing

Run the tests. Seriously.

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Just unit tests
pytest tests/unit/

# Just integration tests
pytest tests/integration/
```

If tests fail, fix your environment before complaining.

---

## 📦 Running the Services

### FastAPI Server

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

API docs at: `http://localhost:8000/docs`

### MCP Server

```bash
python -m src.mcp_server
```

### Docker (For the Lazy)

```bash
docker-compose up --build
```

Everything runs. Ports 8000 (API) and 8001 (MCP).

---

## 🎯 Example Workflow

### Complete Demo

Want to see it all work? Run this:

```bash
python examples/hackathon_demo.py
```

Shows you:
1. Physical card purchase lookup
2. Chat with me (consensus checked)
3. Sequential reasoning analysis
4. Event logging summary

Takes 2 minutes. Worth it.

### Manual Workflow

```bash
# 1. Upload deck
curl -X POST "http://localhost:8000/api/v1/upload/csv" \
  -F "file=@mono_red_aggro.csv"
# Returns: {"deck_id": 1}

# 2. Analyze it
curl -X POST "http://localhost:8000/api/v1/analyze/1"
# Gets: analysis + purchase info

# 3. Optimize it
curl -X POST "http://localhost:8000/api/v1/optimize/1"
# Gets: suggestions + win rate prediction + purchase links

# 4. Get purchase details
curl -X GET "http://localhost:8000/api/v1/purchase/1"
# Gets: Full vendor breakdown
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# Recommended (for real meta data)
TAVILY_API_KEY=your_tavily_key
EXA_API_KEY=your_exa_key

# Optional
BRAVE_API_KEY=your_brave_key
PERPLEXITY_API_KEY=your_perplexity_key

# Database
DATABASE_URL=sqlite:///./data/arena_improver.db
```

### MCP Config

Already set up in `mcp_config.json`. Don't touch it unless you know what you're doing.

---

## 📚 Documentation

- **[HF Deployment Guide](docs/HF_DEPLOYMENT.md)**: Hugging Face Space setup and configuration
- **[Hackathon Features](docs/HACKATHON_FEATURES.md)**: Complete feature breakdown
- **[Steam Arena Guide](docs/STEAM_ARENA_GUIDE.md)**: Platform-specific help
- **[MCP Security](docs/MCP_SECURITY.md)**: Security best practices
- **[API Docs](http://localhost:8000/docs)**: Interactive API documentation (when running locally)
- **[Live API Docs](https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath)**: Try the API in the HF Space

---

## 🤝 Contributing

Want to improve this? Fine. Here's how:

1. Fork it
2. Create a feature branch: `git checkout -b feature/YourFeature`
3. Write tests (or I'll reject it)
4. Make sure tests pass: `pytest`
5. Commit: `git commit -m 'Add YourFeature'`
6. Push: `git push origin feature/YourFeature`
7. Open a Pull Request

### What I Want

- Meta intelligence improvements
- More purchase vendor integrations
- Better matchup prediction models
- MCP tool enhancements
- Bug fixes (obviously)

### What I Don't Want

- Unnecessary complexity
- Features without tests
- Breaking changes without discussion
- Bad code (you know what I mean)

---

## 🎖️ Hackathon Submission

**Event**: MCP 1st Birthday Hackathon
**Submission**: Arena Improver with Vawlrathh Integration
**Live Demo**: [Hugging Face Space](https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath)

### Key Differentiators

1. **Dual AI Agent System**: Primary chat + consensus validation
2. **Physical Card Integration**: Arena-only filtering + vendor pricing
3. **Character-Driven UX**: Vawlrathh's personality (me)
4. **Sequential Reasoning**: Multi-step decision analysis
5. **Event Logging**: Complete audit trail
6. **Full MCP Depth**: Memory, sequential thinking, omnisearch
7. **Hugging Face Space**: Live demo with auto-sync from GitHub

### Metrics

Run `examples/hackathon_demo.py` to generate:
- Event logs (`data/events/hackathon_demo_export.json`)
- Performance statistics
- Feature demonstrations

---

## 📝 License

AGPL-3.0. Don't steal it. Contribute instead.

---

## 🙏 Acknowledgments

- **Magic: The Gathering Arena**: For existing (and being on Steam)
- **OpenAI**: For GPT models
- **Anthropic**: For Claude (consensus checking)
- **Scryfall**: For card data API
- **FastAPI**: For not being garbage
- **Model Context Protocol**: For making MCP integration possible

---

## 📧 Contact

**GitHub**: [https://github.com/clduab11/arena-improver](https://github.com/clduab11/arena-improver)
**Issues**: Use GitHub Issues. Be specific.
**Email**: Don't. Use GitHub Issues.

---

## 💭 Final Thoughts from Vawlrathh

Look, your deck's probably still bad. But with this tool, at least you'll know *why* it's bad and *how* to fix it.

I don't do participation trophies. I do win rates.

Use the sequential reasoning for complex decisions. Talk to me via WebSocket for quick advice. Check purchase prices before you waste money on paper cards you don't need.

And for the love of Phyrexia, **read the error messages** before asking for help.

Now go build something decent.

— **Vawlrathh, The Small'n**
*Diminutive in size, not in strategic prowess*

---

**P.S.** If you're reading this far down, you might actually care about winning. Good. The demo's at `examples/hackathon_demo.py`. Run it. Learn something.

**P.P.S.** Your mana curve still needs work.
