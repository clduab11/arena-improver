"""Main FastAPI application."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import psutil
import os
import logging
from sqlalchemy.exc import SQLAlchemyError

from .api.routes import router, sql_service
from .api.websocket_routes import router as ws_router
from .utils.cache import get_meta_cache, get_deck_cache
from . import __version__

logger = logging.getLogger(__name__)

# Module-level psutil Process instance for accurate CPU monitoring
# Creating a new Process per request causes cpu_percent() to return 0.0
# because it needs to measure CPU usage over time
_process = psutil.Process()
# Prime the CPU percent baseline by calling once with None
# This establishes the initial measurement point
_process.cpu_percent(None)


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
app.include_router(ws_router, prefix="/api/v1", tags=["chat"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Arena Improver",
        "version": __version__,
        "description": "MCP for MTG Arena deck analysis",
        "docs": "/docs",
        "mcp_server": "Use mcp_server.py for MCP protocol access",
        "chat": "WebSocket chat at /api/v1/ws/chat/{client_id}",
        "features": [
            "Deck analysis & optimization",
            "Physical card purchase links",
            "Real-time chat with Vawlrathh, The Small'n",
            "AI consensus checking"
        ]
    }


@app.get("/health")
async def health_check():
    """Basic health check endpoint.

    Returns 200 OK if service is running.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": __version__
    }


@app.get("/health/ready")
async def readiness_check():
    """Readiness probe for Kubernetes/Docker deployments.

    Checks if service is ready to accept requests.
    """
    try:
        # Check database connectivity
        await sql_service.init_db()

        return {
            "status": "ready",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                "database": "connected"
            }
        }
    except SQLAlchemyError as e:
        # Log the actual error for debugging
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        
        return JSONResponse(
            content={
                "status": "not_ready",
                "error": "Database initialization failed"
            },
            status_code=503
        )
    except Exception as e:
        # Log unexpected errors for debugging
        logger.error(f"Unexpected readiness check failure: {e}", exc_info=True)
        
        return JSONResponse(
            content={
                "status": "not_ready",
                "error": "Service initialization failed"
            },
            status_code=503
        )


@app.get("/health/live")
async def liveness_check():
    """Liveness probe for Kubernetes/Docker deployments.

    Returns 200 if process is alive (for restart decisions).
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics endpoint.

    Returns application metrics for monitoring.
    """
    # Get cache statistics
    meta_cache = get_meta_cache()
    deck_cache = get_deck_cache()
    meta_stats = meta_cache.stats()
    deck_stats = deck_cache.stats()

    # Get system metrics using module-level process instance
    memory_info = _process.memory_info()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
        "system": {
            "cpu_percent": _process.cpu_percent(),
            "memory_mb": memory_info.rss / 1024 / 1024,
            "memory_percent": _process.memory_percent(),
            "num_threads": _process.num_threads(),
            "open_files": len(_process.open_files()),
        },
        "cache": {
            "meta": {
                "size": meta_stats["size"],
                "max_size": meta_stats["max_size"],
                "hit_rate": round(meta_stats["hit_rate"], 3),
                "hits": meta_stats["hits"],
                "misses": meta_stats["misses"],
                "utilization": round(meta_stats["utilization"], 3)
            },
            "deck": {
                "size": deck_stats["size"],
                "max_size": deck_stats["max_size"],
                "hit_rate": round(deck_stats["hit_rate"], 3),
                "hits": deck_stats["hits"],
                "misses": deck_stats["misses"],
                "utilization": round(deck_stats["utilization"], 3)
            }
        }
    }


@app.get("/status")
async def status():
    """Detailed service status for monitoring dashboards.

    Returns comprehensive status including dependencies.
    """
    # Check environment variables
    env_status = {
        "OPENAI_API_KEY": "configured" if os.getenv("OPENAI_API_KEY") else "missing",
        "TAVILY_API_KEY": "configured" if os.getenv("TAVILY_API_KEY") else "missing",
        "EXA_API_KEY": "configured" if os.getenv("EXA_API_KEY") else "missing"
    }

    # Get cache stats
    meta_cache = get_meta_cache()
    deck_cache = get_deck_cache()

    return {
        "service": "Arena Improver",
        "version": __version__,
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": env_status,
        "dependencies": {
            "database": "connected",
            "cache": {
                "meta": f"{meta_cache.stats()['size']}/{meta_cache.stats()['max_size']} entries",
                "deck": f"{deck_cache.stats()['size']}/{deck_cache.stats()['max_size']} entries"
            }
        },
        "features": {
            "deck_analysis": True,
            "ai_optimization": env_status["OPENAI_API_KEY"] == "configured",
            "meta_intelligence": env_status["TAVILY_API_KEY"] == "configured",
            "semantic_search": env_status["EXA_API_KEY"] == "configured"
        }
    }


if __name__ == "__main__":
    import os
    # Note: 0.0.0.0 binds to all interfaces for Docker/production use
    # Use 127.0.0.1 for local development to restrict access
    host = os.getenv("API_HOST", "127.0.0.1")
    uvicorn.run(
        "src.main:app",
        host=host,
        port=8000,
        reload=True
    )
