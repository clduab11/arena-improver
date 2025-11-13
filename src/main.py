"""Main FastAPI application."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import psutil
import os

from .api.routes import router, sql_service
from .utils.cache import get_meta_cache, get_deck_cache
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
    """
    Return service metadata for the API root.
    
    Provides the service name, package version, a short description, the docs path, and a note about MCP server usage.
    
    Returns:
        dict: Metadata with keys:
            - "service": service name string
            - "version": package version string
            - "description": short service description string
            - "docs": path to interactive documentation string
            - "mcp_server": note about MCP protocol access string
    """
    return {
        "service": "Arena Improver",
        "version": __version__,
        "description": "MCP for MTG Arena deck analysis",
        "docs": "/docs",
        "mcp_server": "Use mcp_server.py for MCP protocol access"
    }


@app.get("/health")
async def health_check():
    """
    Return a minimal service health payload.
    
    Returns:
        dict: A JSON-serializable mapping with keys:
            - "status": the service health state, always set to "healthy".
            - "timestamp": current UTC time as an ISO 8601 string.
            - "version": the service version string.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": __version__
    }


@app.get("/health/ready")
async def readiness_check():
    """
    Perform a readiness probe that verifies database connectivity.
    
    Returns:
        dict: On success, a JSON-serializable mapping with keys:
            - `status`: "ready"
            - `timestamp`: ISO 8601 UTC timestamp string
            - `checks`: mapping of individual check results (e.g., `{"database": "connected"}`).
        fastapi.Response: On failure, an HTTP 503 Response with a JSON body containing:
            - `status`: "not_ready"
            - `error`: error message describing the failure.
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
    except Exception as e:
        return Response(
            content=f'{{"status": "not_ready", "error": "{str(e)}"}}',
            status_code=503,
            media_type="application/json"
        )


@app.get("/health/live")
async def liveness_check():
    """
    Return liveness status with current UTC timestamp.
    
    Returns:
        dict: A mapping containing:
            - status (str): "alive".
            - timestamp (str): ISO 8601-formatted UTC timestamp.
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/metrics")
async def metrics():
    """
    Return Prometheus-compatible application metrics for monitoring.
    
    Returns:
        dict: A JSON-serializable mapping with the following keys:
            timestamp (str): UTC ISO-8601 timestamp of metric sample.
            version (str): Service version string.
            system (dict): Runtime system metrics:
                cpu_percent (float): CPU usage percent for the current process.
                memory_mb (float): Resident memory in megabytes.
                memory_percent (float): Memory usage percent for the current process.
                num_threads (int): Number of threads used by the process.
                open_files (int): Count of open file descriptors.
            cache (dict): Cache statistics for meta and deck caches:
                meta (dict) and deck (dict) each contain:
                    size (int): Current number of entries.
                    max_size (int|None): Maximum configured entries (if available).
                    hit_rate (float): Hit rate rounded to 3 decimal places.
                    hits (int): Number of cache hits.
                    misses (int): Number of cache misses.
                    utilization (float): Cache utilization rounded to 3 decimal places.
    """
    # Get cache statistics
    meta_cache = get_meta_cache()
    deck_cache = get_deck_cache()
    meta_stats = meta_cache.stats()
    deck_stats = deck_cache.stats()

    # Get system metrics
    process = psutil.Process()
    memory_info = process.memory_info()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
        "system": {
            "cpu_percent": process.cpu_percent(),
            "memory_mb": memory_info.rss / 1024 / 1024,
            "memory_percent": process.memory_percent(),
            "num_threads": process.num_threads(),
            "open_files": len(process.open_files()),
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
    """
    Provide detailed service status intended for monitoring dashboards.
    
    Includes UTC timestamp, service name and version, environment variable presence for external APIs, dependency summaries (database and cache sizes), and feature-flag booleans derived from environment configuration.
    
    Returns:
        dict: A mapping with the following keys:
            - service (str): Service name.
            - version (str): Service version.
            - status (str): High-level operational state.
            - timestamp (str): ISO8601 UTC timestamp.
            - environment (dict): Presence state for keys "OPENAI_API_KEY", "TAVILY_API_KEY", and "EXA_API_KEY" with values "configured" or "missing".
            - dependencies (dict): Dependency info containing:
                - database (str): Database connectivity state.
                - cache (dict): Cache summaries with "meta" and "deck" values formatted as "<size>/<max_size> entries".
            - features (dict): Feature flags:
                - deck_analysis (bool)
                - ai_optimization (bool)
                - meta_intelligence (bool)
                - semantic_search (bool)
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