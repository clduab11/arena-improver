"""Main FastAPI application."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .api.routes import router, sql_service
from . import __version__


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup/shutdown."""
    # Startup
    await sql_service.init_db()
    yield
    # Shutdown
    # Clean up resources if needed


app = FastAPI(
    title="Arena Improver",
    description="MCP for Magic: The Gathering Arena deck analysis and optimization",
    version=__version__,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1", tags=["decks"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Arena Improver",
        "version": __version__,
        "description": "MCP for MTG Arena deck analysis",
        "docs": "/docs",
        "mcp_server": "Use mcp_server.py for MCP protocol access"
    }


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
