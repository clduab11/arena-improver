# Arena Improver - Complete Deployment Guide

*"Follow these instructions exactly. Don't improvise."*
— **Vawlrathh, The Small'n**

## 📋 Table of Contents

1. [Quick Start (5 Minutes)](#quick-start-5-minutes)
2. [Local Development Setup](#local-development-setup)
3. [HuggingFace Space Deployment](#huggingface-space-deployment)
4. [Production Deployment](#production-deployment)
5. [Environment Variables Reference](#environment-variables-reference)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start (5 Minutes)

### Try the Live Demo

**No installation needed!**

Visit: **https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath**

The HuggingFace Space provides:
- Interactive API documentation
- Real-time chat with Vawlrathh
- All features ready to use
- Auto-synced from the main branch

### For Developers

```bash
# Clone the repository
git clone https://github.com/clduab11/arena-improver.git
cd arena-improver

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Install dependencies
pip install -r requirements.txt

# Run the application
python src/main.py
```

Visit `http://localhost:8000/docs` for API documentation.

---

## Local Development Setup

### Prerequisites

- **Python 3.9+** (3.11+ recommended)
- **Node.js 18+** (for MCP servers)
- **Git**
- **SQLite** (included with Python)

### Step 1: Clone and Install

```bash
git clone https://github.com/clduab11/arena-improver.git
cd arena-improver

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```bash
# Required
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Recommended
TAVILY_API_KEY=tvly-...
EXA_API_KEY=...

# Optional
DATABASE_URL=sqlite:///./data/arena_improver.db
API_HOST=127.0.0.1
```

See [Environment Variables Reference](#environment-variables-reference) for details.

### Step 3: Initialize Database

```bash
python -c "import asyncio; from src.services.smart_sql import SmartSQLService; asyncio.run(SmartSQLService().init_db())"
```

### Step 4: Run the Application

#### Option A: FastAPI Only (Recommended for Development)

```bash
# Run on port 8000
python src/main.py

# Or use uvicorn directly for auto-reload
uvicorn src.main:app --reload --port 8000
```

Access:
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- WebSocket Chat Endpoint: ws://localhost:8000/api/v1/ws/chat/{client_id}

#### Option B: Full HF Space Setup (Gradio + FastAPI)

```bash
# Run the HuggingFace Space wrapper
python app.py
```

Access:
- Gradio UI: http://localhost:7861
- FastAPI Docs: http://localhost:7860/docs

### Step 5: Test the Installation

```bash
# Run all tests
pytest

# Run specific test suites
pytest tests/unit/
pytest tests/integration/

# Run with coverage
pytest --cov=src tests/
```

---

## HuggingFace Space Deployment

> **📖 Complete Guide**: See [docs/HF_DEPLOYMENT.md](docs/HF_DEPLOYMENT.md) for detailed HuggingFace Space deployment instructions, including token setup, manual sync procedures, troubleshooting, and monitoring.

### Quick Overview

Arena Improver can be deployed to HuggingFace Spaces for public access.

**Live Space**: https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath

### Key Features

- **Dual-Port Architecture**: FastAPI (7860) + Gradio UI (7861)
- **Auto-Restart**: HuggingFace automatically restarts on crashes
- **Environment Secrets**: Configure API keys via Space settings
- **Manual Sync**: Use `hf upload --create-pr` for deployments

### Essential Steps

1. **Get HF Token**: Visit [HuggingFace Tokens](https://huggingface.co/settings/tokens) and create a write token
2. **Configure Secrets**: Add required API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.) in Space settings
3. **Deploy**: Use `hf upload --create-pr` to sync code changes

**For complete instructions, troubleshooting, and monitoring**, see [docs/HF_DEPLOYMENT.md](docs/HF_DEPLOYMENT.md).

---

## Production Deployment

### Docker Deployment

#### Build Image

```bash
# Build Docker image
docker build -t arena-improver:latest .

# Run container
docker run -d \
  -p 8000:8000 \
  -e OPENAI_API_KEY=your-key \
  -e ANTHROPIC_API_KEY=your-key \
  --name arena-improver \
  arena-improver:latest
```

#### Docker Compose

```yaml
version: '3.8'

services:
  arena-improver:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - TAVILY_API_KEY=${TAVILY_API_KEY}
      - EXA_API_KEY=${EXA_API_KEY}
      - API_HOST=0.0.0.0
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

Run:
```bash
docker compose up -d
```

### Cloud Platform Deployment

#### Render.com

1. Connect your GitHub repository
2. Create a new Web Service
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `uvicorn src.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables from `.env.example`

#### Railway.app

1. Click "New Project" → "Deploy from GitHub"
2. Select `arena-improver` repository
3. Railway auto-detects FastAPI
4. Add environment variables
5. Deploy!

#### Fly.io

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login and launch
fly auth login
fly launch

# Set environment variables
fly secrets set OPENAI_API_KEY=your-key
fly secrets set ANTHROPIC_API_KEY=your-key

# Deploy
fly deploy
```

---

## Environment Variables Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4 and embeddings | `sk-proj-...` |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude consensus checking | `sk-ant-...` |

### Recommended Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `TAVILY_API_KEY` | Tavily API for real-time meta intelligence | `tvly-...` |
| `EXA_API_KEY` | Exa API for semantic search | `...` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | SQLite database path | `sqlite:///./data/arena_improver.db` |
| `API_HOST` | API host binding | `127.0.0.1` |
| `STEAM_PLATFORM_ENABLED` | Enable Steam-specific optimizations | `true` |
| `META_UPDATE_FREQUENCY` | Hours between meta updates | `24` |

### API Key Sources

- **OpenAI**: https://platform.openai.com/api-keys
- **Anthropic**: https://console.anthropic.com/
- **Tavily**: https://tavily.com/
- **Exa**: https://exa.ai/
- **Brave Search**: https://brave.com/search/api/
- **Perplexity**: https://www.perplexity.ai/settings/api

---

## Troubleshooting

### Common Issues

#### "API Key Not Found" Error

**Problem**: Missing API keys

**Solution**:
```bash
# Check your .env file
cat .env

# Verify environment variables are loaded
python -c "import os; print(os.getenv('OPENAI_API_KEY'))"

# If None, restart your terminal to reload environment variables
# The application loads .env automatically on startup
```

#### "Database Not Initialized" Error

**Problem**: SQLite database not created

**Solution**:
```bash
# Initialize database
python -c "import asyncio; from src.services.smart_sql import SmartSQLService; asyncio.run(SmartSQLService().init_db())"

# Verify database exists
ls -la data/arena_improver.db
```

#### Port Already in Use

**Problem**: Port 8000 or 7860 already occupied

**Solution**:
```bash
# Find and kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or use a different port
uvicorn src.main:app --port 8001
```

#### HF Space Won't Start

**Problem**: HuggingFace Space shows error

**Solutions**:
1. Check HF Space logs (click "View logs")
2. Verify all required API keys are set
3. Check GitHub Actions for sync errors
4. Restart the Space manually

#### WebSocket Connection Failed

**Problem**: Cannot connect to API endpoint

**Solutions**:
```bash
# Check if FastAPI is running
curl http://localhost:8000/health

# Test API endpoint
curl http://localhost:8000/status

# Check CORS settings in src/main.py
```

### Getting Help

1. **Check Logs**: Always check application logs first
2. **Read Docs**: See [HF Deployment Guide](docs/HF_DEPLOYMENT.md) for detailed guides
3. **GitHub Issues**: https://github.com/clduab11/arena-improver/issues
4. **Test Suite**: Run `pytest -v` to identify broken components

### Health Checks

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed status
curl http://localhost:8000/status

# Metrics
curl http://localhost:8000/metrics

# Readiness (for k8s)
curl http://localhost:8000/health/ready
```

---

## Security Best Practices

### API Key Management

- ✅ **DO**: Store API keys in environment variables
- ✅ **DO**: Use `.env` file for local development
- ✅ **DO**: Add `.env` to `.gitignore`
- ✅ **DO**: Rotate keys periodically
- ❌ **DON'T**: Commit API keys to Git
- ❌ **DON'T**: Share API keys in public forums
- ❌ **DON'T**: Use production keys for testing

### Production Security

- Use HTTPS in production
- Enable CORS only for trusted origins
- Set up rate limiting
- Monitor API usage
- Use read-only database users where possible
- Keep dependencies updated: `pip install --upgrade -r requirements.txt`

---

## Performance Optimization

### Caching

Arena Improver uses intelligent caching:

- **Meta data**: 24-hour cache
- **Scryfall data**: 24-hour cache
- **Deck analysis**: 1-hour cache

Monitor cache performance:
```bash
curl http://localhost:8000/metrics
```

### Database Optimization

```bash
# Vacuum database periodically
sqlite3 data/arena_improver.db "VACUUM;"

# Analyze for query optimization
sqlite3 data/arena_improver.db "ANALYZE;"
```

### Rate Limiting

Scryfall API is rate-limited to 100ms between requests. This is handled automatically.

---

## Monitoring and Logging

### Logging

Logs are written to stdout/stderr. Configure logging level:

```python
# In src/main.py
import logging
logging.basicConfig(level=logging.INFO)  # Change to DEBUG for verbose logs
```

### Metrics

Access Prometheus-compatible metrics:

```bash
curl http://localhost:8000/metrics
```

Metrics include:
- CPU and memory usage
- Cache hit rates
- Request counts
- Response times

---

## Additional Resources

- **Full HF Guide**: [docs/HF_DEPLOYMENT.md](docs/HF_DEPLOYMENT.md)
- **HF Quick Reference**: [HUGGINGFACE_SPACE_SETUP.md](HUGGINGFACE_SPACE_SETUP.md)
- **GitHub Repository**: https://github.com/clduab11/arena-improver
- **Live HF Space**: https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath
- **MCP Hackathon**: https://huggingface.co/MCP-1st-Birthday

---

*"If you followed these instructions and it still doesn't work, check your API keys. It's always the API keys."*
— **Vawlrathh, The Small'n**

**Last Updated**: 2025-11-14
**Version**: 1.0.0
