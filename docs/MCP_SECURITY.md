# MCP Configuration Security Guide

## Environment Variable Handling

The `mcp_config.json` file uses environment variable substitution with the `${VAR}` pattern. This guide explains how to securely handle API keys and sensitive configuration.

## Security Best Practices

### 1. API Key Storage

**DO:**
- Store API keys in `.env` file (never commit this file)
- Use environment variables in `mcp_config.json` with `${VAR}` syntax
- Verify that `.env` is in your `.gitignore`

**DON'T:**
- Never hardcode API keys directly in `mcp_config.json`
- Never commit API keys to version control
- Never share API keys in logs or error messages

### 2. Environment Variable Substitution

The MCP server implementations should:
- Read environment variables at runtime
- Not log the actual API key values
- Handle missing environment variables gracefully

Example from `mcp_config.json`:
```json
{
  "cld-omnisearch": {
    "env": {
      "TAVILY_API_KEY": "${TAVILY_API_KEY}",
      "EXA_API_KEY": "${EXA_API_KEY}"
    }
  }
}
```

### 3. Verification Steps

Before running your MCP server:

1. **Check that `.env` exists and contains your keys:**
   ```bash
   cat .env | grep API_KEY
   ```

2. **Verify environment variables are loaded:**
   ```bash
   echo $TAVILY_API_KEY
   ```

3. **Test MCP server without exposing keys:**
   - Use debug mode that masks sensitive values
   - Check logs for any leaked credentials

### 4. Key Rotation

If you suspect your API keys have been compromised:

1. Immediately revoke the old keys in the provider's dashboard
2. Generate new API keys
3. Update your `.env` file
4. Restart the MCP server

### 5. Optional vs Required Keys

Not all API keys are required. Check `.env.example` for guidance:

**Required:**
- `TAVILY_API_KEY` - Primary search for meta data
- `EXA_API_KEY` - Neural search for strategies

**Optional:**
- `BRAVE_API_KEY` - Alternative search provider
- `PERPLEXITY_API_KEY` - AI-powered research
- `JINA_AI_API_KEY` - Content processing
- `KAGI_API_KEY` - High-quality search
- `GITHUB_API_KEY` - GitHub repo search (no scopes needed)

If an optional key is missing, the service should:
- Log a warning (without exposing the key)
- Fall back to other available providers
- Continue operation with reduced functionality

## Troubleshooting

### MCP Server Can't Read Environment Variables

If the MCP server reports missing API keys:

1. **Check MCP implementation supports `${VAR}` syntax:**
   - Not all MCP implementations automatically substitute environment variables
   - You may need to manually export variables before starting the server

2. **Manually export before starting:**
   ```bash
   export TAVILY_API_KEY=$(grep TAVILY_API_KEY .env | cut -d '=' -f2)
   export EXA_API_KEY=$(grep EXA_API_KEY .env | cut -d '=' -f2)
   npx cld-omnisearch
   ```

3. **Use a wrapper script:**
   ```bash
   #!/bin/bash
   set -a
   source .env
   set +a
   npx cld-omnisearch
   ```

## Reporting Security Issues

If you discover a security vulnerability in how API keys are handled:

1. **DO NOT** open a public GitHub issue
2. Report privately to the repository maintainers
3. Include steps to reproduce (without exposing actual keys)

## References

- [MCP Server Configuration](https://modelcontextprotocol.io/docs/configuration)
- [Environment Variable Best Practices](https://12factor.net/config)
- [OWASP API Security](https://owasp.org/www-project-api-security/)
