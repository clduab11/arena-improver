# Hugging Face Space Deployment Guide

This guide explains how to deploy and configure Arena Improver on Hugging Face Spaces now that synchronization is handled manually instead of through GitHub Actions.

## 🎯 Overview

Arena Improver targets the Hugging Face Space at [MCP-1st-Birthday/vawlrathh](https://huggingface.co/spaces/MCP-1st-Birthday/vawlrathh). Direct pushes from GitHub-hosted runners are currently blocked for this Space, so we rely on `hf upload --create-pr` to keep it in sync.

## 🔧 Setup Instructions

### Step 1: Get a Hugging Face Token

1. Go to [Hugging Face Settings](https://huggingface.co/settings/tokens)
2. Click "New token"
3. Name it something like `arena-improver-sync`
4. Select **Write** permissions (required to push to the Space)
5. Click "Generate token"
6. **Copy the token immediately** (you won't see it again)

### Step 2: Add HF_TOKEN to Your Local Environment

1. Copy `.env.example` to `.env` if it does not exist
2. Add `HF_TOKEN=<your token>` to the file (never commit this value)
3. Source the file whenever you plan to sync so the `hf` CLI can read the token:

```bash
set -a && source .env && set +a
```

> Still have a GitHub repository secret named `HF_TOKEN`? Leaving it in place is fine, but it is no longer required now that the workflow has been removed.

### Step 3: Configure Environment Variables in Hugging Face Space

The Space requires several API keys to function properly. Configure them in your HF Space settings:

1. Go to your Space settings: `https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath/settings`
2. Scroll to "Repository secrets"
3. Add the following secrets:

| Secret Name | Required? | Purpose | How to Get |
|-------------|-----------|---------|------------|
| `OPENAI_API_KEY` | ✅ Required | Primary inference (SmartInference, embeddings, fallback chat) | [OpenAI API Keys](https://platform.openai.com/api-keys) |
| `ANTHROPIC_API_KEY` | ✅ Required | Claude consensus + PR reviews | [Anthropic Console](https://console.anthropic.com/) |
| `HF_TOKEN` | ✅ Required | `hf upload --create-pr` pushes + GitHub workflow dispatch | [Hugging Face Settings → Tokens](https://huggingface.co/settings/tokens) |
| `TAVILY_API_KEY` | ⚠️ Recommended | Real-time meta intelligence searches | [Tavily](https://tavily.com/) |
| `EXA_API_KEY` | ⚠️ Recommended | Semantic search + similarity lookups | [Exa](https://exa.ai/) |
| `VULTR_API_KEY` | Optional | GPU embeddings fallback for SmartInference | [Vultr Control Panel](https://my.vultr.com/settings/#settingsapi) |
| `BRAVE_API_KEY` | Optional | Privacy-focused search fallback | [Brave Search](https://brave.com/search/api/) |
| `PERPLEXITY_API_KEY` | Optional | Research agent + follow-up sources | [Perplexity](https://www.perplexity.ai/) |
| `JINA_AI_API_KEY` | Optional | Content processing + rerankers | [Jina AI](https://jina.ai/) |
| `KAGI_API_KEY` | Optional | High-precision search & FastGPT | [Kagi](https://kagi.com/settings?p=api) |
| `GITHUB_API_KEY` | Optional | PAT with `public_repo` for repo-wide search | [GitHub Tokens](https://github.com/settings/tokens) |

### Step 4: Verify the Deployment

After adding the secrets:

1. Go to the Space URL: `https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath`
2. Check the "Status" tab to see which API keys are configured
3. Try the "API Documentation" tab to explore available endpoints
4. Test a simple request (e.g., GET `/health`)

## 🔄 Manual Sync Workflow (CLI First)

### Why the GitHub Action Was Removed

Attempts to push directly from GitHub-hosted runners now receive a `403` advising us to "pass create_pr=1". Rather than keep a flaky workflow around, we deleted `.github/workflows/sync-to-hf.yml` and standardised on the CLI command below. This keeps us fully compliant with Hugging Face limitations and prevents accidental overwrites of Space-local state such as `.cache/`.

### Prerequisites

- `huggingface_hub` 0.36.x installed (last v0 release that keeps `--create-pr` stable while satisfying Gradio/Transformers)
- `HF_TOKEN` exported in your shell (see Setup Step 2)
- `hf` CLI authenticated via the token

### Canonical Command

```bash
set -a && source .env && set +a && source .venv/bin/activate && \
hf upload MCP-1st-Birthday/vawlrathh . \
  --repo-type space \
  --token "$HF_TOKEN" \
  --create-pr \
  --commit-message "HF Sync | <summary + tests>" \
  --exclude ".git/*" --exclude ".venv/*" --exclude "__pycache__/*" \
  --exclude ".pytest_cache/*" --exclude ".mypy_cache/*" --exclude ".ruff_cache/*" \
  --exclude "node_modules/*" --exclude "dist/*" --exclude "build/*" \
  --exclude "data/*" --exclude "*.log"
```

### Commit Message Guidance for Agentic Assistants

Hugging Face treats `hf upload --create-pr` commits as PRs, so give reviewers (human or AI) the full context:

1. **Intent** – e.g., `hf sync | add deck heuristics`
2. **Testing** – cite the key commands (`pytest tests/unit/test_chat_agent.py`)
3. **Dependencies/Secrets** – call out additions or state "no dependency changes"
4. **Follow-up Actions** – note if the Space needs a restart or cache clear

Example: `HF Sync | refresh docs + remove GH workflow (pytest tests/integration/test_api.py)`

### Reviewing and Merging the Space PR

1. Visit `https://huggingface.co/spaces/MCP-1st-Birthday/vawlrathh/pulls`
2. Filter by **Pull Requests** and open the latest entry
3. Review the diff, confirm ignores behaved, and click **Merge**
4. Optionally delete the auto-created branch inside the Space UI

### Optional: Inspect the PR Locally

```bash
hf download MCP-1st-Birthday/vawlrathh /tmp/hf_pr_latest \
  --repo-type space \
  --revision refs/pr/<id> \
  --token "$HF_TOKEN" \
  --exclude ".git/*"

diff -qr /tmp/local_snapshot /tmp/hf_pr_latest
```

This mirrors our Codespace verification flow and is helpful when you want to double-check the generated PR before merging.

### Manual GitHub Workflow Trigger (Optional)

If you prefer to reuse the self-hosted GitHub workflow for syncing (e.g., when the CLI is unavailable), run the helper script which wraps `gh workflow run sync-to-hf.yml`:

```bash
./scripts/run_hf_sync.sh            # defaults to main
./scripts/run_hf_sync.sh feature-x  # target a different ref
```

The script queues the workflow, watches the logs, and prints the actions URL if GitHub does not return a run ID. You will need the GitHub CLI (`gh auth login`) with `workflow` scope for this command to succeed.

### Verifying the Hugging Face Restart

After either the CLI sync or the manual GitHub workflow finishes:

1. Open the **Status** tab on your Space and confirm the latest commit hash and secret checklist are green: `https://huggingface.co/spaces/MCP-1st-Birthday/vawlrathh?logs=1#status`
2. Hit the proxied FastAPI health endpoint to make sure port 7860 came back:  
  `curl https://huggingface.co/spaces/MCP-1st-Birthday/vawlrathh/+/proxy/7860/health`
3. Optionally check the Gradio surface via the dedicated port (should return HTML):  
  `curl -I https://huggingface.co/spaces/MCP-1st-Birthday/vawlrathh/+/proxy/7861/`
4. If either check fails, restart the Space from the **Settings → Runtime** section and rerun the health curls.

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

**Problem**: `hf upload --create-pr` exited with a non-zero status

**Solutions**:
 
1. Re-run the command with `HF_HUB_ENABLE_HF_TRANSFER=1` for large files
2. Make sure `HF_TOKEN` is exported in your shell and has **Write** permissions
3. Confirm the Space slug `MCP-1st-Birthday/vawlrathh` is spelled correctly
4. Check the CLI output for the generated PR URL; open it to review Hugging Face-side validation errors
5. If uploads keep failing, run `hf whoami -t "$HF_TOKEN"` to confirm the token is still active

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

### Track Hugging Face PRs

Monitor manual sync status:

1. Visit `https://huggingface.co/spaces/MCP-1st-Birthday/vawlrathh/discussions`
2. Filter for pull requests and open the one created by your CLI run
3. Review diffs, merge when satisfied, then optionally delete the temporary branch

## 🎯 Development Workflow

### Making Changes

1. Develop and test locally
2. Commit changes to a feature branch
3. Open a Pull Request and land it on `main`
4. Run the canonical `hf upload --create-pr` command from this guide
5. Review and merge the generated Hugging Face PR, then verify the deployment on the Space

### Testing Changes Before Deployment

```bash
# Test the app.py wrapper locally
python app.py

# Test individual components
python -m pytest tests/

# Test FastAPI directly
uvicorn src.main:app --port 8000
```

## 🔧 Troubleshooting

### HuggingFace CLI Issues

#### Problem: `hf upload` fails with authentication error
**Solution:**
```bash
# Check if token is set
echo $HF_TOKEN | head -c 10  # Should show first 10 chars

# Re-authenticate
huggingface-cli login --token $HF_TOKEN

# Verify authentication
huggingface-cli whoami
```

#### Problem: "Direct push blocked" error
**Solution:**
The Space security settings prevent direct pushes. Always use `--create-pr`:
```bash
hf upload MCP-1st-Birthday/vawlrathh . --repo-type=space --create-pr
```

#### Problem: CLI not found or not installed
**Solution:**
```bash
# Install/upgrade huggingface_hub
pip install --upgrade huggingface_hub[cli]

# Verify installation
hf --version
```

### Space Runtime Issues

#### Problem: Space shows "Building..." indefinitely
**Solutions:**
1. Check build logs in Space settings
2. Verify `requirements.txt` is valid
3. Check for conflicting dependencies
4. Review `app.py` for syntax errors

#### Problem: FastAPI server not starting
**Solutions:**
1. Check logs: Go to Space → Logs tab
2. Verify port 7860 is used (HF Spaces default)
3. Check environment variables are set
4. Review src/main.py for startup errors

#### Problem: Gradio UI shows "Connection Error"
**Solutions:**
1. Ensure FastAPI is running on port 7860
2. Check `wait_for_fastapi_ready()` timeout
3. Verify health endpoint returns 200: `/health`
4. Check Space logs for FastAPI errors

### API Key Issues

#### Problem: "OPENAI_API_KEY not found" error
**Solution:**
1. Go to Space settings → Repository secrets
2. Add `OPENAI_API_KEY` with your key
3. Restart the Space (Settings → Factory reboot)
4. Verify in Status tab that key shows "✓ Configured"

#### Problem: API calls fail with 401/403 errors
**Solutions:**
1. Verify API keys are valid and not expired
2. Check API key permissions (some keys are read-only)
3. Review Space logs for specific API error messages
4. Test keys locally first before deploying

### Connection Pooling Issues

#### Problem: "Too many connections" error
**Solution:**
The shared HTTP client limits connections to 100. If you see this:
1. Check for connection leaks in code
2. Verify async context managers are used properly
3. Review `src/services/http_client.py` limits
4. Consider increasing `max_connections` if needed

#### Problem: Slow API responses
**Solutions:**
1. Connection pooling should improve performance by 20%+
2. Check rate limiting is working (Scryfall: 100ms delay)
3. Verify shared client is initialized in lifespan
4. Monitor logs for "HTTPClientManager" initialization messages

## 📊 Monitoring

### Accessing Logs

**Real-time logs:**
1. Go to your Space: https://huggingface.co/spaces/MCP-1st-Birthday/vawlrathh
2. Click "Logs" tab
3. View stdout/stderr in real-time

**Search logs:**
```bash
# Filter for errors
grep -i "error" logs.txt

# Filter for specific service
grep "ScryfallService" logs.txt

# Check HTTP client initialization
grep "HTTPClientManager" logs.txt
```

### Auto-Restart Behavior

HuggingFace Spaces automatically restart on:
- Crashes or unhandled exceptions
- Out of memory errors
- Network failures
- Build failures (after code updates)

**Restart indicators:**
- Space status shows "Building..." then "Running"
- Logs show "Application startup complete"
- Health endpoint returns 200

**Manual restart:**
1. Go to Space settings
2. Click "Factory reboot"
3. Wait for rebuild (~2-5 minutes)

### Health Monitoring

**Endpoints to monitor:**

```bash
# Basic health check
curl https://huggingface.co/proxy/7860/health

# Readiness check (database + dependencies)
curl https://huggingface.co/proxy/7860/health/ready

# Liveness check (process status)
curl https://huggingface.co/proxy/7860/health/live
```

**Expected responses:**
```json
{
  "status": "healthy",
  "timestamp": "2024-11-18T...",
  "version": "0.1.0"
}
```

### Performance Metrics

**Monitor these in logs:**
- HTTP connection pool usage: Look for "max_connections" warnings
- Rate limiting delays: Scryfall calls should wait 100ms
- Response times: API calls should complete in <5s
- Memory usage: Should stay under Space limits

**Log patterns to watch:**
```
✅ Good: "HTTPClientManager: Shared client initialized"
✅ Good: "Application startup complete"
❌ Bad: "RuntimeError: HTTPClientManager not initialized"
❌ Bad: "Too many connections"
❌ Bad: "Rate limit exceeded"
```

## 🔄 Rollback Procedures

### Rollback to Previous Version

If a deployment breaks the Space:

**Method 1: Revert Git Commit**
```bash
# Find the last working commit
git log --oneline -10

# Revert to that commit
git revert <commit-sha>

# Push revert
git push origin main

# Sync to HF
hf upload MCP-1st-Birthday/vawlrathh . --repo-type=space --create-pr
```

**Method 2: Manual File Restore**
```bash
# Checkout specific file from previous commit
git checkout <commit-sha> -- path/to/file.py

# Commit and deploy
git commit -m "Rollback file to working version"
hf upload MCP-1st-Birthday/vawlrathh . --repo-type=space --create-pr
```

**Method 3: HuggingFace Git History**
1. Go to Space → Files and versions
2. Click "History"
3. Find last working commit
4. Click "Restore this version"
5. Confirm restoration

## 📐 Architecture Diagram

The HF Space runs a dual-server architecture:

```
┌────────────────────────────────────────────────────────┐
│  Hugging Face Space (Public)                           │
│  https://huggingface.co/spaces/.../vawlrathh           │
└────────────────┬───────────────────────────────────────┘
                 │
    ┌────────────┴───────────────┐
    │                            │
    ▼                            ▼
┌─────────────────────┐   ┌─────────────────────┐
│ FastAPI (Port 7860) │   │ Gradio (Port 7861)  │
│ ─────────────────── │   │ ───────────────────  │
│ • REST API          │◄──┤ • UI Tabs           │
│ • WebSocket Chat    │   │ • Button Handlers   │
│ • Database          │   │ • File Uploads      │
│ • Services          │   │ • Status Display    │
│ • HTTP Client Pool  │   │                     │
└──────┬──────────────┘   └─────────────────────┘
       │
       │ Lifespan Events
       ▼
┌─────────────────────┐
│  HTTPClientManager  │
│  ─────────────────  │
│  • Connection Pool  │
│  • 100 max conns    │
│  • 20 keepalive     │
│  • Shared across    │
│    all services     │
└──────┬──────────────┘
       │
       │ Uses shared client
       ▼
┌─────────────────────┐
│  Service Layer      │
│  ─────────────────  │
│  • ScryfallService  │
│  • CardMarketSvc    │
│  • SmartSQLService  │
│  • ChatAgent        │
└─────────────────────┘
```

**Port Configuration:**
- **7860**: FastAPI backend (HF Spaces default)
- **7861**: Gradio frontend (custom)

**Connection Flow:**
1. User accesses Gradio UI (port 7861)
2. UI makes HTTP calls to FastAPI (port 7860)
3. FastAPI uses shared HTTP client for external APIs
4. Connection pooling reuses TCP connections
5. Rate limiting coordinates API calls

## 📚 Additional Resources

- [Hugging Face Spaces Documentation](https://huggingface.co/docs/hub/spaces)
- [Gradio Documentation](https://gradio.app/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [MCP Protocol Documentation](https://modelcontextprotocol.io/)
- [Arena Improver GitHub Repo](https://github.com/clduab11/arena-improver)
- [Async Patterns Guide](async_patterns.md)

## 🎖️ MCP 1st Birthday Hackathon

This project is part of the [MCP 1st Birthday Hackathon](https://huggingface.co/MCP-1st-Birthday). The Hugging Face Space deployment showcases:

- Full MCP protocol integration
- Real-time chat with AI agent (Vawlrathh)
- Dual AI system with consensus checking
- Physical card purchase integration
- Sequential reasoning capabilities
- Async HTTP client with connection pooling

---

*"If your deployment breaks, it's probably a configuration issue. Check the logs."*  
— **Vawlrathh, The Small'n**
