# Hugging Face Space Setup - Quick Reference

This document provides a quick reference for setting up and using the Arena Improver Hugging Face Space.

## 🎯 Quick Start

### For Users

Simply visit: **[https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath](https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath)**

No installation required! The Space provides:
- Interactive API documentation
- Live demo of all endpoints
- Real-time health monitoring
- Easy-to-use interface

### For Maintainers

See the full [HF Deployment Guide](docs/HF_DEPLOYMENT.md) for detailed setup instructions.

## 🔧 What Was Implemented

This PR adds complete Hugging Face Space integration with the following components:

### 1. GitHub Actions Workflow (`.github/workflows/sync-to-hf.yml`)

Automatically syncs code from GitHub to HF Space on every push to `main`:

```yaml
- Triggers: Push to main, manual workflow_dispatch
- Security: Explicit permissions (contents: read)
- Action: Force pushes to HF Space repository
```

### 2. Space Wrapper (`app.py`)

Production-ready wrapper that:

- ✅ Starts FastAPI server on port 7860 (HF default)
- ✅ Launches Gradio interface on port 7861
- ✅ Handles graceful startup with health checks (60s timeout)
- ✅ Kills existing uvicorn processes to avoid conflicts
- ✅ Embeds FastAPI docs using HF proxy pattern (`/proxy/7860/docs`)
- ✅ Provides 4 tabs:
  - **API Documentation**: Interactive FastAPI docs in iframe
  - **About**: Project description with Vawlrath's personality
  - **Quick Start**: Usage instructions and examples
  - **Status**: Environment configuration check
- ✅ Maintains Vawlrath's sarcastic character throughout
- ✅ Displays helpful error messages for missing API keys

### 3. Updated Dependencies (`requirements.txt`)

Added: `gradio>=4.0.0`

All existing dependencies maintained.

### 4. Documentation (`docs/HF_DEPLOYMENT.md`)

Comprehensive 295-line guide covering:

- Getting HF token with write permissions
- Adding `HF_TOKEN` to GitHub secrets
- Configuring API keys in HF Space
- Architecture explanation
- Troubleshooting guide
- Security best practices
- Development workflow

### 5. Updated README

Changes made:

- ✅ Replaced LiquidMetal hackathon → MCP 1st Birthday
- ✅ Added HF Space badge and link
- ✅ Added "Try It Now" section
- ✅ Updated documentation links
- ✅ Added live demo reference

### 6. Integration Tests (`tests/integration/test_hf_space.py`)

5 comprehensive tests (all passing):

1. `test_app_imports` - Verifies all functions exist
2. `test_gradio_interface_creation` - Tests Gradio UI creation
3. `test_environment_check` - Tests environment variable checking
4. `test_fastapi_server_can_start` - Tests server startup and health checks
5. `test_kill_existing_uvicorn` - Tests process cleanup

### 7. Bug Fix (`src/main.py`)

Fixed missing import: Added `from .api.websocket_routes import router as ws_router`

## 🔒 Security

✅ **CodeQL Scan: 0 Alerts**

- Explicit permissions in GitHub Actions
- No SQL injection risks
- No command injection risks
- API keys properly managed as secrets
- No hardcoded credentials

## 📋 Required Configuration (One-Time Setup)

### GitHub Secret

Add to: `https://github.com/clduab11/arena-improver/settings/secrets/actions`

| Secret | Value |
|--------|-------|
| `HF_TOKEN` | Your HF token with write permissions |

### HF Space Secrets

Add to: `https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath/settings`

| Secret | Required | Description |
|--------|----------|-------------|
| `OPENAI_API_KEY` | ✅ Yes | OpenAI API for GPT-4 and embeddings |
| `ANTHROPIC_API_KEY` | ✅ Yes | Anthropic API for Claude consensus |
| `TAVILY_API_KEY` | ⚠️ Recommended | Tavily API for meta intelligence |
| `EXA_API_KEY` | ⚠️ Recommended | Exa API for semantic search |

## 🚀 How It Works

### Automatic Deployment

```
Developer pushes to main
    ↓
GitHub Actions triggered
    ↓
Code synced to HF Space
    ↓
HF Space restarts automatically
    ↓
app.py launches:
    1. Kills old uvicorn processes
    2. Starts FastAPI on port 7860
    3. Waits for health check (max 60s)
    4. Launches Gradio on port 7861
    ↓
Users access Space via Gradio interface
```

### Runtime Architecture

```
User Browser
    ↓
Gradio UI (Port 7861)
    ├─ API Documentation Tab (iframe → /proxy/7860/docs)
    ├─ About Tab (HTML content)
    ├─ Quick Start Tab (HTML content)
    └─ Status Tab (Environment check)
    ↓
FastAPI Server (Port 7860)
    ├─ /health - Health check
    ├─ /docs - Interactive API docs
    ├─ /api/v1/* - All endpoints
    └─ /api/v1/ws/chat/{user_id} - WebSocket chat
```

## 🧪 Testing Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"

# Run the Space wrapper
python app.py
```

Access:
- Gradio UI: http://localhost:7861
- FastAPI Docs: http://localhost:7860/docs

## 📊 Metrics

### Code Changes

- Files created: 4
- Files modified: 3
- Lines added: 756
- Tests added: 5 (all passing)
- Security alerts: 0

### Test Results

```
tests/integration/test_hf_space.py::test_app_imports ........................ PASSED
tests/integration/test_hf_space.py::test_gradio_interface_creation .......... PASSED
tests/integration/test_hf_space.py::test_environment_check .................. PASSED
tests/integration/test_hf_space.py::test_fastapi_server_can_start ........... PASSED
tests/integration/test_hf_space.py::test_kill_existing_uvicorn .............. PASSED

5 passed in 14.34s
```

## 🎯 MCP 1st Birthday Hackathon Features

This implementation showcases:

1. **Full MCP Integration**: Memory, sequential thinking, omnisearch
2. **Dual AI System**: Primary agent + consensus checker
3. **Character-Driven UX**: Vawlrath's personality throughout
4. **Real-Time Chat**: WebSocket endpoints for live interaction
5. **Physical Card Integration**: Real-world pricing data
6. **Production Ready**: Comprehensive error handling and health checks
7. **Auto-Deployment**: GitHub → HF Space synchronization

## 🔗 Important Links

- **Live Space**: https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath
- **GitHub Repo**: https://github.com/clduab11/arena-improver
- **Hackathon**: https://huggingface.co/MCP-1st-Birthday
- **Full Documentation**: [docs/HF_DEPLOYMENT.md](docs/HF_DEPLOYMENT.md)

## 🐛 Troubleshooting

### Space Won't Start
1. Check HF Space logs
2. Verify API keys are set
3. Restart the Space manually

### Sync Failed
1. Verify `HF_TOKEN` is set in GitHub secrets
2. Check token has write permissions
3. View GitHub Actions logs

### API Errors
1. Check "Status" tab in Space
2. Verify API keys are valid
3. Check API quota limits

## 💬 Vawlrath Says...

*"If your Space deployment breaks, it's probably your API keys. Check them."*

*"The logs are there for a reason. Read them before asking questions."*

*"This setup is production-ready. Don't mess it up with 'improvements'."*

---

**Status**: ✅ All requirements met | 🔒 Security verified | ✅ Tests passing

*Last updated: 2025-11-14*
