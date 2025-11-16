# Secrets & Environment Variables Checklist

## Local Development (.env)

### Required (Core AI Features)

- [x] `OPENAI_API_KEY` - OpenAI API for GPT-4 and embeddings
- [x] `ANTHROPIC_API_KEY` - Anthropic API for Claude consensus checking
- [x] `DATABASE_URL` - SQLite database path (default: `sqlite:///./data/arena_improver.db`)
- [x] `API_HOST` - API host binding (use `127.0.0.1` for local, `0.0.0.0` for Docker)

### Recommended (Enhanced Features)

- [ ] `TAVILY_API_KEY` - Real-time web search for MTG meta intelligence
- [ ] `EXA_API_KEY` - Neural semantic search for MTG strategies

### Optional (Additional Capabilities)

- [ ] `VULTR_API_KEY` - GPU embeddings hosting
- [ ] `BRAVE_API_KEY` - Privacy-focused search
- [ ] `PERPLEXITY_API_KEY` - AI-powered research
- [ ] `JINA_AI_API_KEY` - Content processing and grounding
- [ ] `KAGI_API_KEY` - High-quality search and FastGPT
- [ ] `GITHUB_API_KEY` - GitHub repository search (no scopes needed)

### Configuration

- [ ] `META_SOURCES` - Comma-separated MTG meta URLs
- [ ] `META_UPDATE_FREQUENCY` - Update frequency in hours (default: 24)
- [ ] `STEAM_PLATFORM_ENABLED` - Enable Steam-specific optimizations (true/false)

---

## GitHub Actions Secrets

### Repository Secrets (clduab11/vawlrathh)

- [x] `HF_TOKEN` - Hugging Face token with write permissions (for sync-to-hf workflow)
- [x] `ANTHROPIC_API_KEY` - For Claude PR/issue review workflows
- [ ] `GITHUB_TOKEN` - Auto-injected by GitHub Actions (no manual setup needed)

### Claude PR Review Workflow Behavior

**Concurrency Control**: The workflow uses GitHub Actions concurrency groups (`concurrency.group: claude-pr-review-${{ github.event.pull_request.number || github.run_id }}`), ensuring only one workflow run is active per PR at any time. The `|| github.run_id` fallback ensures the workflow can run in edge cases where the PR number is not available. If you trigger a new run while one is in progress, the old run is canceled automatically via `cancel-in-progress: true`.

**Duplicate Detection**: Before executing the review, the workflow scans existing PR comments for the marker `<!-- claude-review:{headSHA} -->`. If a comment with the current head SHA already exists (posted by `github-actions[bot]`), the workflow skips all subsequent steps. This prevents redundant reviews when the workflow is re-triggered for the same commit.

**Skip Logic**: When a duplicate is detected, the workflow logs "Claude already reviewed this commit. Skipping duplicate run." and exits early. No API calls are made, no review is posted, and the workflow completes successfully with minimal resource usage.

**Cost Savings**: This mechanism prevents unnecessary Anthropic API charges by ensuring each commit SHA is reviewed exactly once, even if the workflow is triggered multiple times (e.g., via label removal/re-application, workflow re-runs, or synchronize events on the same commit).

**Label Trigger**: The workflow only runs when the `claude-review` label is present on the PR. Apply it to request a review; remove it to prevent future automatic reviews. Combined with the duplicate guard, this gives you precise control over when reviews occur.

**Troubleshooting**: If you're not seeing a review, check: (1) Is the `claude-review` label applied? (2) Did a previous run already post a review for this SHA? (3) Check the Actions tab for workflow logs. (4) Verify `ANTHROPIC_API_KEY` is set correctly in repository secrets.

**Validation**: See `tests/unit/test_workflow_yaml.py` for automated tests verifying the duplicate guard structure, concurrency configuration, and YAML parsing of all workflow files.

---

## Hugging Face Space Secrets

### Space: MCP-1st-Birthday/vawlrath

#### Required (Core Functionality)

- [ ] `OPENAI_API_KEY` - OpenAI API for deck analysis and chat
- [ ] `ANTHROPIC_API_KEY` - Anthropic API for consensus checking

#### Recommended (Full Feature Set)

- [ ] `TAVILY_API_KEY` - Meta intelligence and real-time search
- [ ] `EXA_API_KEY` - Semantic search capabilities

#### Optional (MCP Omnisearch Tools)

- [ ] `BRAVE_API_KEY` - Brave search integration
- [ ] `PERPLEXITY_API_KEY` - Perplexity AI integration
- [ ] `JINA_AI_API_KEY` - Jina AI content processing
- [ ] `KAGI_API_KEY` - Kagi search and FastGPT
- [ ] `GITHUB_API_KEY` - GitHub repository search
- [ ] `VULTR_API_KEY` - GPU embeddings (if using Vultr hosting)

#### Configuration Variables

- [ ] `META_SOURCES` - Default meta data sources
- [ ] `META_UPDATE_FREQUENCY` - Meta update frequency (hours)
- [ ] `STEAM_PLATFORM_ENABLED` - Steam-specific features (true/false)

---

## Setup Instructions

### Local Development

1. Copy `.env.example` to `.env`:

   ```bash
   cp .env.example .env
   ```

2. Fill in required API keys:

   - [OpenAI](https://platform.openai.com/api-keys)
   - [Anthropic](https://console.anthropic.com/settings/keys)

3. Add recommended keys for full functionality:

   - [Tavily](https://tavily.com/)
   - [Exa](https://exa.ai/)

4. Test configuration:

   ```bash
   python -m pytest tests/integration/test_hf_space.py::test_environment_check -v
   ```

### GitHub Repository

1. Navigate to: <https://github.com/clduab11/vawlrathh/settings/secrets/actions>

2. Verify/add secrets:

   - `HF_TOKEN` - Generate at <https://huggingface.co/settings/tokens> (write access)
   - `ANTHROPIC_API_KEY` - For Claude review workflows

### Hugging Face Space

1. Navigate to: <https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath/settings>

2. Add secrets under "Repository secrets":

   - Required: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
   - Recommended: `TAVILY_API_KEY`, `EXA_API_KEY`
   - Optional: All MCP omnisearch keys if using those features

3. Restart the Space after adding secrets

4. Verify via Status tab: <https://mcp-1st-birthday-vawlrath.hf.space/>

---

## Feature Matrix

| Feature | Required Keys |
|---------|--------------|
| Deck Analysis | OPENAI_API_KEY |
| AI Optimization | OPENAI_API_KEY |
| Consensus Checking | ANTHROPIC_API_KEY |
| Chat (Vawlrathh) | OPENAI_API_KEY, ANTHROPIC_API_KEY |
| Meta Intelligence | TAVILY_API_KEY |
| Semantic Search | EXA_API_KEY |
| Physical Card Pricing | None (uses Scryfall public API) |
| MCP Omnisearch | BRAVE_API_KEY, PERPLEXITY_API_KEY, JINA_AI_API_KEY, KAGI_API_KEY |
| GitHub Search | GITHUB_API_KEY |

---

## Validation Steps

### Local

```bash
# Check environment variables are loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('OPENAI:', 'SET' if os.getenv('OPENAI_API_KEY') else 'MISSING')"

# Run FastAPI and check status endpoint
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
curl http://localhost:8000/status
```

### GitHub Actions

```bash
# Check workflow runs
gh run list --workflow=claude-pr-review.yml --limit 5
gh run list --workflow=sync-to-hf.yml --limit 5
```

### Hugging Face Space Validation

```bash
# Check Space status via API
curl -s https://huggingface.co/api/spaces/MCP-1st-Birthday/vawlrath | jq '.runtime.stage'

# Check deployed commit
curl -s https://huggingface.co/api/spaces/MCP-1st-Birthday/vawlrath | jq '.sha[0:7]'

# Verify endpoints
curl https://mcp-1st-birthday-vawlrath.hf.space/health
curl https://mcp-1st-birthday-vawlrath.hf.space/status
```

---

## Gaps & Action Items

### Current Gaps

1. ⚠️ HF Space is one commit behind (deployed: 89be7d2, latest: b1aed6d)
   - **Action**: Push to main or manually trigger sync workflow once GH auth is configured

2. ⚠️ Missing optional MCP keys documented but not in HF Space setup guide
   - **Action**: Update `HUGGINGFACE_SPACE_SETUP.md` to include all MCP omnisearch keys

3. ⚠️ No automated test for secret validation in CI
   - **Action**: Add pytest that checks required env vars before running integration tests

### Next Actions

1. Configure GitHub CLI authentication or generate PAT for manual workflow triggers
2. Add all required secrets to HF Space
3. Implement test fixtures that validate secrets before running Gradio workflow tests
4. Update HF deployment docs with complete secret list
