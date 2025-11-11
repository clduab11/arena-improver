# Claude AI Integration Setup Guide

This guide explains how to set up Claude AI integration for automated code reviews and issue assistance.

## Prerequisites

- GitHub repository with admin access
- Anthropic API key for Claude
- GitHub Actions enabled

## Step 1: Get an Anthropic API Key

1. Visit [Anthropic Console](https://console.anthropic.com/)
2. Sign up or log in to your account
3. Navigate to API Keys section
4. Create a new API key
5. Copy the API key (you won't be able to see it again)

## Step 2: Configure Repository Secrets

Add the Anthropic API key as a repository secret:

### Via GitHub Web Interface

1. Go to your repository on GitHub
2. Click on **Settings**
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Name: `ANTHROPIC_API_KEY`
6. Value: Paste your Anthropic API key
7. Click **Add secret**

### Via GitHub CLI

```bash
gh secret set ANTHROPIC_API_KEY --body "your-api-key-here"
```

## Step 3: Verify GitHub Actions Permissions

Ensure GitHub Actions has the necessary permissions:

1. Go to repository **Settings**
2. Click **Actions** → **General**
3. Under "Workflow permissions", select:
   - ✅ **Read and write permissions**
   - ✅ **Allow GitHub Actions to create and approve pull requests**
4. Click **Save**

## Step 4: Enable Workflows

The following workflow files should be present in `.github/workflows/`:

- `claude-pr-review.yml` - Automated PR reviews
- `claude-issue-assistant.yml` - Issue assistance

These workflows will activate automatically when:
- A pull request is created or updated
- Someone comments `@claude` on a PR or issue
- An issue is labeled with `claude-review`

## Step 5: Test the Integration

### Test PR Review

1. Create a test pull request
2. Add a comment: `@claude please review`
3. Wait for Claude to analyze and respond
4. Check the Actions tab for workflow status

### Test Issue Assistance

1. Create a test issue with label `claude-review`
2. Or add a comment: `@claude can you help?`
3. Wait for Claude's analysis
4. Check the Actions tab for workflow status

## Troubleshooting

### Workflow Not Triggering

**Problem**: Claude doesn't respond to tags or labels

**Solutions**:
1. Check that workflows are enabled in Settings → Actions
2. Verify `ANTHROPIC_API_KEY` secret is set correctly
3. Check Actions tab for workflow failures
4. Ensure permissions are set correctly (Step 3)

### Authentication Errors

**Problem**: Workflow fails with API authentication error

**Solutions**:
1. Verify your Anthropic API key is valid
2. Check API key hasn't expired
3. Ensure secret name is exactly `ANTHROPIC_API_KEY`
4. Try regenerating and updating the API key

### Rate Limiting

**Problem**: "Rate limit exceeded" errors

**Solutions**:
1. Check `.github/CLAUDE_CONFIG.yml` rate limits
2. Wait before retrying
3. Consider upgrading Anthropic API tier
4. Reduce frequency of reviews

### Permission Errors

**Problem**: Workflow can't post comments

**Solutions**:
1. Verify GitHub Actions has write permissions (Step 3)
2. Check GITHUB_TOKEN is available in workflow
3. Ensure workflows have `pull-requests: write` permission

## Configuration

Customize Claude's behavior by editing `.github/CLAUDE_CONFIG.yml`:

```yaml
review:
  auto_review: true          # Auto-review all PRs
  severity_threshold: medium # Report medium+ issues
  min_coverage: 80          # Minimum test coverage

issues:
  auto_respond: false       # Only respond when tagged
  provide_examples: true    # Include code examples
```

## Security Best Practices

### Protecting API Keys

- ✅ **DO**: Store API keys in GitHub Secrets
- ✅ **DO**: Use repository secrets, not environment variables
- ✅ **DO**: Rotate API keys periodically
- ❌ **DON'T**: Commit API keys to the repository
- ❌ **DON'T**: Share API keys in issues or PRs
- ❌ **DON'T**: Use the same key across multiple projects

### Workflow Security

- ✅ **DO**: Review workflow changes carefully
- ✅ **DO**: Use specific action versions (not `@main`)
- ✅ **DO**: Limit workflow permissions to minimum required
- ❌ **DON'T**: Allow workflows from forks to access secrets
- ❌ **DON'T**: Use pull_request_target without careful review

## Cost Management

Claude API usage incurs costs. To manage:

### Monitor Usage

1. Check Anthropic Console for usage statistics
2. Set up billing alerts
3. Review workflow run frequency

### Optimize Costs

1. Set `auto_review: false` to review only when tagged
2. Reduce `max_detailed_files` in config
3. Increase `review_cooldown` between reviews
4. Use Sonnet model (cheaper than Opus)

### Rate Limiting

Configure in `.github/CLAUDE_CONFIG.yml`:

```yaml
rate_limits:
  reviews_per_hour: 10      # Max reviews per hour
  issues_per_hour: 20       # Max issue responses per hour
  review_cooldown: 60       # Seconds between reviews
```

## Advanced Configuration

### Custom Review Focus

Edit `.github/CLAUDE_CONFIG.yml`:

```yaml
review:
  focus_areas:
    - security        # Security vulnerabilities
    - performance     # Performance issues
    - testing         # Test coverage
```

### File Exclusions

Exclude files from review:

```yaml
review:
  exclude_patterns:
    - "**/test_*.py"          # Test files
    - "**/migrations/**"      # Database migrations
    - "**/*.min.js"          # Minified files
```

### Custom Prompts

Modify the review prompts in:
- `.github/scripts/claude_reviewer.py`
- `.github/scripts/claude_issue_assistant.py`

## Updating

To update Claude integration:

1. Pull latest changes from repository
2. Review changes to workflow files
3. Update configuration if needed
4. Test with a sample PR/issue

## Support

### Documentation

- [CLAUDE.md](../CLAUDE.md) - Usage guide
- [README.md](../README.md) - Project documentation
- [Anthropic Documentation](https://docs.anthropic.com/)
- [GitHub Actions Documentation](https://docs.github.com/actions)

### Getting Help

1. Check [existing issues](https://github.com/clduab11/arena-improver/issues)
2. Review [GitHub Actions logs](https://github.com/clduab11/arena-improver/actions)
3. Create an issue with `[Claude]` prefix
4. Tag maintainers for assistance

## Uninstalling

To disable Claude integration:

1. Delete workflow files:
   - `.github/workflows/claude-pr-review.yml`
   - `.github/workflows/claude-issue-assistant.yml`

2. Delete scripts:
   - `.github/scripts/claude_reviewer.py`
   - `.github/scripts/claude_issue_assistant.py`

3. Remove repository secret:
   - Go to Settings → Secrets and variables → Actions
   - Delete `ANTHROPIC_API_KEY`

4. Optional: Remove configuration:
   - `.github/CLAUDE_CONFIG.yml`
   - `CLAUDE.md`

---

**Last Updated**: 2025-11-11
**Maintained by**: Arena Improver Team
