#!/bin/bash
# Check for async pattern anti-patterns
# This script is used by pre-commit and CI/CD

set -e

echo "🔍 Checking async patterns..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Check 1: No new AsyncClient instantiations (except in http_client.py)
echo "Checking for httpx.AsyncClient() anti-pattern..."
VIOLATIONS=$(grep -rn "httpx\.AsyncClient()" \
  --include="*.py" \
  --exclude-dir=tests \
  --exclude="http_client.py" \
  src/ app.py 2>/dev/null || true)

if [ -n "$VIOLATIONS" ]; then
  echo -e "${RED}❌ Found httpx.AsyncClient() instantiations:${NC}"
  echo "$VIOLATIONS"
  echo ""
  echo "Use the shared HTTP client instead:"
  echo "  from src.services.http_client import get_http_client"
  echo "  client = await get_http_client()"
  echo ""
  echo "See docs/async_patterns.md for details."
  ERRORS=$((ERRORS + 1))
else
  echo -e "${GREEN}✅ No AsyncClient instantiation anti-patterns${NC}"
fi

# Check 2: No time.sleep in async functions
echo ""
echo "Checking for blocking sleep calls in async functions..."
FILES_WITH_ASYNC=$(grep -rl "async def" --include="*.py" src/ app.py 2>/dev/null || true)

if [ -n "$FILES_WITH_ASYNC" ]; then
  for file in $FILES_WITH_ASYNC; do
    BLOCKING_SLEEP=$(grep -n "time\.sleep" "$file" 2>/dev/null || true)
    if [ -n "$BLOCKING_SLEEP" ]; then
      echo -e "${YELLOW}⚠️  Warning: Found time.sleep() in file with async functions:${NC}"
      echo "File: $file"
      echo "$BLOCKING_SLEEP"
      echo "Use 'await asyncio.sleep()' in async functions instead"
      echo ""
    fi
  done
fi

# Check 3: Verify get_http_client usage
echo "Checking for shared HTTP client usage..."
SHARED_CLIENT_COUNT=$(grep -r "get_http_client" --include="*.py" src/ 2>/dev/null | wc -l)

echo "Found $SHARED_CLIENT_COUNT references to shared HTTP client"

if [ "$SHARED_CLIENT_COUNT" -lt 1 ]; then
  echo -e "${YELLOW}⚠️  No usage of shared HTTP client found${NC}"
  echo "Consider using get_http_client() for HTTP requests"
else
  echo -e "${GREEN}✅ Shared HTTP client is being used${NC}"
fi

# Check 4: Run ruff async checks
echo ""
echo "Running ruff async checks..."
if ruff check --select ASYNC src/ app.py 2>/dev/null; then
  echo -e "${GREEN}✅ No ruff async violations${NC}"
else
  echo -e "${RED}❌ Ruff found async violations${NC}"
  echo "See docs/async_patterns.md for best practices"
  ERRORS=$((ERRORS + 1))
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $ERRORS -eq 0 ]; then
  echo -e "${GREEN}✅ All async pattern checks passed!${NC}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  exit 0
else
  echo -e "${RED}❌ Found $ERRORS async pattern violation(s)${NC}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "To fix these issues:"
  echo "1. Read docs/async_patterns.md"
  echo "2. Use 'await get_http_client()' instead of 'httpx.AsyncClient()'"
  echo "3. Use 'await asyncio.sleep()' instead of 'time.sleep()'"
  echo "4. Ensure all async functions properly use 'await'"
  echo ""
  exit 1
fi
