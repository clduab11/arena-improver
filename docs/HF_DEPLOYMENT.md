# Hugging Face Space Deployment Guide

This guide explains how to deploy and configure Arena Improver on Hugging Face Spaces with automatic synchronization from GitHub.

## 🎯 Overview

Arena Improver is automatically synchronized from the GitHub repository to a Hugging Face Space at [MCP-1st-Birthday/vawlrath](https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath). Every push to the `main` branch triggers an automatic deployment.

## 🔧 Setup Instructions

### Step 1: Get a Hugging Face Token

1. Go to [Hugging Face Settings](https://huggingface.co/settings/tokens)
2. Click "New token"
3. Name it something like `arena-improver-sync`
4. Select **Write** permissions (required to push to the Space)
5. Click "Generate token"
6. **Copy the token immediately** (you won't see it again)

### Step 2: Add HF_TOKEN to GitHub Secrets

1. Go to your GitHub repository settings: `https://github.com/clduab11/arena-improver/settings/secrets/actions`
2. Click "New repository secret"
3. Name: `HF_TOKEN`
4. Value: Paste the token you copied from Hugging Face
5. Click "Add secret"

### Step 3: Configure Environment Variables in Hugging Face Space

The Space requires several API keys to function properly. Configure them in your HF Space settings:

1. Go to your Space settings: `https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath/settings`
2. Scroll to "Repository secrets"
3. Add the following secrets:

#### Required API Keys

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4 and embeddings | [OpenAI API Keys](https://platform.openai.com/api-keys) |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude (consensus checking) | [Anthropic Console](https://console.anthropic.com/) |

#### Optional but Recommended API Keys

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `TAVILY_API_KEY` | Tavily API for real-time meta intelligence | [Tavily](https://tavily.com/) |
| `EXA_API_KEY` | Exa API for semantic search | [Exa](https://exa.ai/) |

#### Less Common API Keys

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `BRAVE_API_KEY` | Brave Search API (optional) | [Brave Search](https://brave.com/search/api/) |
| `PERPLEXITY_API_KEY` | Perplexity API (optional) | [Perplexity](https://www.perplexity.ai/) |

### Step 4: Verify the Deployment

After adding the secrets:

1. Go to the Space URL: `https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath`
2. Check the "Status" tab to see which API keys are configured
3. Try the "API Documentation" tab to explore available endpoints
4. Test a simple request (e.g., GET `/health`)

## 🔄 How Automatic Sync Works

### GitHub Actions Workflow

The `.github/workflows/sync-to-hf.yml` workflow:

1. **Triggers**: Runs on every push to `main` branch, or manually via workflow_dispatch
2. **Checkout**: Fetches the complete git history
3. **Push**: Force pushes to the Hugging Face Space repository

```yaml
name: Sync to Hugging Face Space

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  sync-to-hf:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0
          lfs: true
      
      - name: Push to Hugging Face Space
        env:
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
        run: |
          git remote add hf https://clduab11:$HF_TOKEN@huggingface.co/spaces/MCP-1st-Birthday/vawlrath
          git push hf main --force
```

### Manual Sync

You can trigger a manual sync:

1. Go to `https://github.com/clduab11/arena-improver/actions/workflows/sync-to-hf.yml`
2. Click "Run workflow"
3. Select the `main` branch
4. Click "Run workflow"

## 🏗️ Architecture

### How the Space Works

The Hugging Face Space runs two servers:

1. **FastAPI Server** (Port 7860)
   - Main API server with all deck analysis endpoints
   - WebSocket chat interface
   - Runs from `src.main:app`
   - Started automatically by `app.py`

2. **Gradio Interface** (Port 7861)
   - Web UI for exploring the API
   - Tabs: API Documentation, About, Quick Start, Status
   - Embeds FastAPI docs using HF proxy pattern
   - Provides environment status check

### Startup Process

1. `app.py` is executed by Hugging Face
2. Existing uvicorn processes are killed
3. FastAPI server starts on port 7860
4. Health checks wait for server readiness (max 60s)
5. Gradio interface is created and launched on port 7861
6. Users access the Space through Gradio

### HF Space Proxy Pattern

Hugging Face Spaces use a proxy system for multiple ports. The FastAPI docs are accessed via:

```
/proxy/7860/docs
```

This allows the Gradio interface on port 7861 to embed the FastAPI docs from port 7860.

## 🧪 Testing Locally

Before pushing to GitHub, test the setup locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export TAVILY_API_KEY="your-key"  # optional
export EXA_API_KEY="your-key"      # optional

# Run the Space
python app.py
```

This will:
- Start FastAPI on port 7860
- Start Gradio on port 7861
- Open browser to http://localhost:7861

## 🚨 Troubleshooting

### Space Won't Start

**Problem**: Space shows error or doesn't load

**Solutions**:
1. Check the Space logs (click "View logs" in HF Space interface)
2. Verify all required API keys are set
3. Check if FastAPI server started successfully
4. Restart the Space manually

### API Endpoints Return Errors

**Problem**: API requests fail with 500 errors

**Solutions**:
1. Check the "Status" tab to see which API keys are missing
2. Verify API keys are valid (not expired, have sufficient quota)
3. Check FastAPI server logs for detailed error messages

### Sync Failed

**Problem**: GitHub Action fails to sync

**Solutions**:
1. Verify `HF_TOKEN` is set in GitHub secrets
2. Check token has **Write** permissions
3. Verify Space exists: `https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath`
4. Check GitHub Actions logs for detailed error

### Port Conflicts

**Problem**: "Address already in use" errors

**Solutions**:
1. The `app.py` automatically kills existing uvicorn processes
2. If issues persist, restart the Space
3. Check for other processes using ports 7860-7861

## 🔐 Security Best Practices

### API Key Management

- ✅ **DO**: Store API keys as HF Space secrets
- ✅ **DO**: Use read-only keys when possible
- ✅ **DO**: Rotate keys periodically
- ❌ **DON'T**: Commit API keys to the repository
- ❌ **DON'T**: Share API keys in public forums
- ❌ **DON'T**: Use production keys for testing

### Token Permissions

- GitHub `HF_TOKEN`: Needs **Write** access to push to Space
- OpenAI: Needs **API access** only
- Anthropic: Needs **API access** only
- Tavily/Exa: Needs **API access** only

## 📊 Monitoring

### Check Space Status

Visit the "Status" tab in your Space to see:
- Which API keys are configured
- FastAPI server health
- Environment configuration

### View Logs

Hugging Face provides logs:
1. Go to your Space
2. Click "View logs" (top right)
3. See real-time server output

### GitHub Actions Status

Monitor sync status:
1. Go to `https://github.com/clduab11/arena-improver/actions`
2. Check "Sync to Hugging Face Space" workflow
3. View logs for any failed runs

## 🎯 Development Workflow

### Making Changes

1. Develop and test locally
2. Commit changes to a feature branch
3. Open a Pull Request
4. Once merged to `main`, auto-syncs to HF Space
5. Verify deployment on HF Space

### Testing Changes Before Deployment

```bash
# Test the app.py wrapper locally
python app.py

# Test individual components
python -m pytest tests/

# Test FastAPI directly
uvicorn src.main:app --port 8000
```

## 📚 Additional Resources

- [Hugging Face Spaces Documentation](https://huggingface.co/docs/hub/spaces)
- [Gradio Documentation](https://gradio.app/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [MCP Protocol Documentation](https://modelcontextprotocol.io/)
- [Arena Improver GitHub Repo](https://github.com/clduab11/arena-improver)

## 🎖️ MCP 1st Birthday Hackathon

This project is part of the [MCP 1st Birthday Hackathon](https://huggingface.co/MCP-1st-Birthday). The Hugging Face Space deployment showcases:

- Full MCP protocol integration
- Real-time chat with AI agent (Vawlrathh)
- Dual AI system with consensus checking
- Physical card purchase integration
- Sequential reasoning capabilities

---

*"If your deployment breaks, it's probably a configuration issue. Check the logs."*  
— **Vawlrathh, The Small'n**
