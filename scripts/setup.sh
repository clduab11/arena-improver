#!/bin/bash

# Arena Improver - Automated Setup Script
# MCP-1st-Birthday Hackathon
# ==========================================

set -e  # Exit on error

echo "🎮 Arena Improver: MCP-Powered MTG Arena Intelligence"
echo "======================================================"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "📋 Checking prerequisites..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.9"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}❌ Python $REQUIRED_VERSION+ required, found $PYTHON_VERSION${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python $PYTHON_VERSION detected${NC}"

# Check Node.js for MCP servers
if ! command -v node &> /dev/null; then
    echo -e "${YELLOW}⚠️  Node.js not found - MCP servers won't be available${NC}"
    echo "   Install from: https://nodejs.org/"
else
    NODE_VERSION=$(node -v)
    echo -e "${GREEN}✓ Node.js $NODE_VERSION detected${NC}"
fi

# Create virtual environment
echo ""
echo "🔧 Setting up virtual environment..."
if [ -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment already exists, skipping...${NC}"
else
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Upgrade pip
echo ""
echo "📦 Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo -e "${GREEN}✓ Pip upgraded${NC}"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install -r requirements.txt
if [ -f "requirements-dev.txt" ]; then
    pip install -r requirements-dev.txt
fi
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Setup environment variables
echo ""
echo "🔐 Setting up environment variables..."
if [ -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file already exists${NC}"
else
    cp .env.example .env
    echo -e "${GREEN}✓ .env file created from template${NC}"
    echo -e "${YELLOW}⚠️  IMPORTANT: Edit .env file with your API keys:${NC}"
    echo "   - OPENAI_API_KEY (required for AI optimization)"
    echo "   - TAVILY_API_KEY (recommended for meta intelligence)"
    echo "   - EXA_API_KEY (recommended for semantic search)"
fi

# Create data directory
echo ""
echo "📁 Creating data directory..."
mkdir -p data
echo -e "${GREEN}✓ Data directory created${NC}"

# Initialize database
echo ""
echo "💾 Initializing database..."
python3 -c "
import asyncio
import sys
sys.path.insert(0, 'src')
from services.smart_sql import SmartSQLService
async def init():
    sql_service = SmartSQLService()
    await sql_service.init_db()
    print('${GREEN}✓ Database initialized${NC}')
asyncio.run(init())
" 2>/dev/null || echo -e "${YELLOW}⚠️  Database initialization skipped (might already exist)${NC}"

# Run tests
echo ""
echo "🧪 Running tests..."
if pytest tests/ -v --tb=short 2>/dev/null; then
    echo -e "${GREEN}✓ All tests passed${NC}"
else
    echo -e "${YELLOW}⚠️  Some tests failed - check test output above${NC}"
fi

# Check MCP configuration
echo ""
echo "🔌 Checking MCP configuration..."
if [ -f "mcp_config.json" ]; then
    echo -e "${GREEN}✓ mcp_config.json found${NC}"
    if command -v jq &> /dev/null; then
        echo "   MCP Servers configured:"
        jq -r '.mcpServers | keys[]' mcp_config.json | while read -r server; do
            echo "   - $server"
        done
    fi
else
    echo -e "${RED}❌ mcp_config.json not found${NC}"
fi

# Print next steps
echo ""
echo "=========================================="
echo -e "${GREEN}🎉 Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Configure API keys in .env:"
echo "   nano .env"
echo ""
echo "2. Start the FastAPI server:"
echo "   uvicorn src.main:app --reload"
echo ""
echo "3. (Optional) Start MCP server:"
echo "   python -m src.mcp_server"
echo ""
echo "4. Access API documentation:"
echo "   http://localhost:8000/docs"
echo ""
echo "5. Or use Docker:"
echo "   docker-compose up --build"
echo ""
echo "📚 Documentation: README.md"
echo "🐛 Issues: https://github.com/clduab11/arena-improver/issues"
echo ""
echo "Good luck with the MCP-1st-Birthday Hackathon! 🏆"
echo ""
