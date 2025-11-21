"""Hugging Face Space wrapper for Arena Improver.

This module provides a combined Gradio + FastAPI application for deployment
on Hugging Face Spaces. Both services run on port 7860 (HF Space default)
using Gradio's mount_gradio_app to consolidate the servers.

The Gradio UI is mounted at /gradio subpath for clean separation from FastAPI routes.
FastAPI endpoints are available at /api/v1/*, /docs, /health, etc.

"Your deck's terrible. Let me show you how to fix it."
— Vawlrathh, The Small'n
"""

# pylint: disable=no-member

import asyncio
import json
import logging
import os
import subprocess
import sys
import textwrap
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import gradio as gr
from gradio import mount_gradio_app
import httpx
import uvicorn
import websockets

from src.main import app as fastapi_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Module-level shared HTTP client for async handlers with connection pooling
client: Optional[httpx.AsyncClient] = None


async def get_shared_client() -> httpx.AsyncClient:
    """Get or create shared HTTP client with connection pooling.
    
    Returns:
        httpx.AsyncClient: Shared client instance with connection pooling
    """
    global client
    if not client:
        client = httpx.AsyncClient(
            timeout=60.0,
            limits=httpx.Limits(max_keepalive_connections=10)
        )
    return client

# HF Space configuration - single port for both FastAPI and Gradio
FASTAPI_PORT = 7860  # HF Spaces only exposes port 7860
REPO_URL = "https://github.com/clduab11/arena-improver"
HACKATHON_URL = "https://huggingface.co/MCP-1st-Birthday"
HF_DEPLOYMENT_GUIDE_URL = f"{REPO_URL}/blob/main/docs/HF_DEPLOYMENT.md"
# Both services run on the same port now - these URLs point to localhost
# for internal communication between Gradio frontend and FastAPI backend
API_BASE_URL = os.getenv(
    "FASTAPI_BASE_URL",
    f"http://localhost:{FASTAPI_PORT}",
)  # For REST API calls
WS_BASE_URL = os.getenv(
    "FASTAPI_WS_URL",
    f"ws://localhost:{FASTAPI_PORT}",
)  # For WebSocket connections
HEALTH_CHECK_URL = f"{API_BASE_URL}/health"


@dataclass
class BuilderMetadata:
    """Lightweight descriptor for tab builders used by the tests."""

    name: str
    description: str
    endpoints: List[str]
    handler: Callable[..., Any]
    websocket_path: Optional[str] = None


GRADIO_BUILDERS: Dict[str, BuilderMetadata] = {}


def builder_registry(
    *,
    name: str,
    description: str,
    endpoints: List[str],
    websocket_path: Optional[str] = None,
):
    """Decorator used to register modular Gradio builders."""

    def decorator(func: Callable[..., Any]):
        GRADIO_BUILDERS[name] = BuilderMetadata(
            name=name,
            description=description,
            endpoints=endpoints,
            handler=func,
            websocket_path=websocket_path,
        )
        return func

    return decorator


async def _upload_csv_to_api(file_path: Optional[str]) -> Dict[str, Any]:
    """Upload a CSV file to the FastAPI backend with defensive logging (async)."""

    if not file_path:
        return {"status": "error", "message": "No CSV file selected"}

    try:
        with open(file_path, "rb") as file_handle:
            files = {
                "file": (os.path.basename(file_path), file_handle, "text/csv"),
            }
            shared_client = await get_shared_client()
            response = await shared_client.post(
                f"{API_BASE_URL}/api/v1/upload/csv",
                files=files,
                timeout=60,
            )
            response.raise_for_status()
            return response.json()
    except FileNotFoundError:
        return {"status": "error", "message": "CSV file could not be read"}
    except httpx.HTTPStatusError as exc:
        logger.error("CSV upload failed: %s", exc)
        status_code = exc.response.status_code
        return {
            "status": "error",
            "message": (f"Backend rejected CSV upload ({status_code})"),
        }
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unexpected CSV upload failure")
        return {"status": "error", "message": str(exc)}


async def _upload_text_to_api(deck_text: str, fmt: str) -> Dict[str, Any]:
    """Upload Arena text export to the FastAPI backend (async)."""

    if not deck_text or not deck_text.strip():
        return {"status": "error", "message": "Deck text is empty"}

    payload = {"deck_string": deck_text, "format": fmt}
    try:
        shared_client = await get_shared_client()
        response = await shared_client.post(
            f"{API_BASE_URL}/api/v1/upload/text",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("Text upload failed: %s", exc)
        status_code = exc.response.status_code
        return {
            "status": "error",
            "message": (f"Backend rejected text upload ({status_code})"),
        }
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unexpected text upload failure")
        return {"status": "error", "message": str(exc)}


async def _fetch_meta_snapshot(game_format: str) -> Dict[str, Any]:
    """Fetch meta intelligence for a specific format (async)."""

    try:
        shared_client = await get_shared_client()
        response = await shared_client.get(
            f"{API_BASE_URL}/api/v1/meta/{game_format}",
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("Meta snapshot failed: %s", exc)
        return {
            "status": "error",
            "message": f"Meta endpoint error ({exc.response.status_code})",
        }
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Meta snapshot unexpected failure")
        return {"status": "error", "message": str(exc)}


async def _fetch_memory_summary(deck_id: Optional[float]) -> Dict[str, Any]:
    """Fetch Smart Memory stats for the supplied deck id (async)."""

    if not deck_id:
        return {"status": "error", "message": "Deck ID required"}

    try:
        shared_client = await get_shared_client()
        response = await shared_client.get(
            f"{API_BASE_URL}/api/v1/stats/{int(deck_id)}",
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("Memory summary failed: %s", exc)
        return {
            "status": "error",
            "message": f"Stats endpoint error ({exc.response.status_code})",
        }
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Memory summary unexpected failure")
        return {"status": "error", "message": str(exc)}


async def _check_chat_websocket() -> Dict[str, Any]:
    """Attempt to connect to the chat WebSocket to validate connectivity."""

    ws_url = f"{WS_BASE_URL}/api/v1/ws/chat/{uuid.uuid4()}"
    try:
        async with websockets.connect(ws_url, open_timeout=10) as connection:
            await connection.send(json.dumps({"type": "ping"}))
            await connection.recv()
        return {"status": "connected", "endpoint": ws_url}
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("WebSocket connection failed: %s", exc)
        return {"status": "error", "message": str(exc), "endpoint": ws_url}


@builder_registry(
    name="deck_uploader",
    description="Deck CSV and text imports",
    endpoints=["/api/v1/upload/csv", "/api/v1/upload/text"],
)
def build_deck_uploader_tab():
    """Deck uploader for Gradio 6 that posts to FastAPI endpoints."""

    gr.Markdown("## Deck Uploads")
    deck_id_state = gr.State(value=None)
    deck_id_box = gr.Number(label="Latest Deck ID", interactive=False)
    upload_status = gr.JSON(label="Upload Response", value={})

    with gr.Row():
        csv_input = gr.File(file_types=[".csv"], label="Arena CSV Export")
        upload_btn = gr.Button("Upload CSV", variant="primary")

    async def handle_csv_upload(uploaded_file, previous_id):
        file_path = getattr(uploaded_file, "name", None)
        payload = await _upload_csv_to_api(file_path)
        deck_id = payload.get("deck_id") or previous_id
        return payload, deck_id, deck_id

    upload_btn.click(  # pylint: disable=no-member
        fn=handle_csv_upload,
        inputs=[csv_input, deck_id_state],
        outputs=[upload_status, deck_id_state, deck_id_box],
    )

    gr.Markdown("### Arena Text Export")
    deck_text_input = gr.Textbox(
        lines=10,
        label="Arena Export",  # guidance label
        placeholder="4 Lightning Bolt (M11) 146\\n2 Counterspell (MH2) 267",
    )
    format_dropdown = gr.Dropdown(
        choices=["Standard", "Pioneer", "Modern"],
        value="Standard",
        label="Format",
    )
    text_upload_btn = gr.Button("Upload Text", variant="secondary")

    async def handle_text_upload(deck_text, fmt, previous_id):
        payload = await _upload_text_to_api(deck_text, fmt)
        deck_id = payload.get("deck_id") or previous_id
        return payload, deck_id, deck_id

    text_upload_btn.click(  # pylint: disable=no-member
        fn=handle_text_upload,
        inputs=[deck_text_input, format_dropdown, deck_id_state],
        outputs=[upload_status, deck_id_state, deck_id_box],
    )

    gr.Markdown("### Tips")
    tips_markdown = (
        "* CSV uploads should come from the Steam Arena export.\\n"
        "* Text uploads should be the Arena clipboard format.\\n"
        "* The latest `deck_id` works across the Meta dashboard and chat tabs."
    )
    gr.Markdown(tips_markdown)


@builder_registry(
    name="chat_ui",
    description="WebSocket chat surface",
    endpoints=["/api/v1/ws/chat/{user_id}"],
    websocket_path="/api/v1/ws/chat/{user_id}",
)
def build_chat_ui_tab():
    """WebSocket chat interface hooking into FastAPI chat endpoint."""

    gr.Markdown("## Chat with Vawlrathh")
    connection_status = gr.JSON(label="WebSocket Status", value={})
    chatbot = gr.Chatbot(label="Live Conversation")
    chat_history_state = gr.State(value=[])
    message_box = gr.Textbox(
        label="Message",
        lines=2,
        placeholder="Ask Vawlrathh how to fix your deck…",
    )
    deck_context = gr.Number(label="Deck ID (optional)", precision=0)

    connect_btn = gr.Button("Test WebSocket", variant="primary")
    send_btn = gr.Button("Add Message Locally", variant="secondary")

    connect_btn.click(  # pylint: disable=no-member
        fn=_check_chat_websocket,
        outputs=connection_status,
    )

    def queue_message(history, message, deck_id):
        history = history or []
        if not message or not message.strip():
            return history, "", history

        context_note = (
            f"Deck context: {int(deck_id)}" if deck_id else "No deck context provided"
        )
        summary = f"Message enqueued for WebSocket delivery. {context_note}"
        # Chatbot expects (user, assistant) tuples
        history.append((message.strip(), summary))
        return history, "", history

    send_btn.click(  # pylint: disable=no-member
        fn=queue_message,
        inputs=[chat_history_state, message_box, deck_context],
        outputs=[chatbot, message_box, chat_history_state],
    )

    gr.Markdown(
        "Use the **Test WebSocket** button to ensure the backend connection "
        "works before sending."
    )


@builder_registry(
    name="meta_dashboards",
    description="Meta + memory analytics",
    endpoints=["/api/v1/meta/{format}", "/api/v1/stats/{deck_id}"],
)
def build_meta_dashboard_tab():
    """Meta dashboards for SmartMemory + MetaIntelligence data."""

    gr.Markdown("## Meta Dashboards")
    format_dropdown = gr.Dropdown(
        choices=["Standard", "Pioneer", "Modern"],
        value="Standard",
        label="Format",
    )
    meta_btn = gr.Button("Load Meta Snapshot", variant="primary")
    meta_json = gr.JSON(label="Meta Intelligence", value={})
    meta_btn.click(  # pylint: disable=no-member
        fn=_fetch_meta_snapshot,
        inputs=format_dropdown,
        outputs=meta_json,
    )

    deck_input = gr.Number(label="Deck ID", precision=0)
    memory_btn = gr.Button("Load Smart Memory", variant="secondary")
    memory_json = gr.JSON(label="Memory Summary", value={})
    memory_btn.click(  # pylint: disable=no-member
        fn=_fetch_memory_summary,
        inputs=deck_input,
        outputs=memory_json,
    )

    gr.Markdown(
        "Meta snapshots surface win-rates, while Smart Memory summarizes "
        "past conversations."
    )


def check_environment():
    """Check required environment variables and return HTML summary."""
    env_status = {}
    required_keys = {
        "OPENAI_API_KEY": "Required for AI-powered deck analysis and chat",
        "ANTHROPIC_API_KEY": "Required for consensus checking",
    }
    optional_keys = {
        "HF_TOKEN": "Used for CLI-based syncs and GitHub workflow dispatch",
        "TAVILY_API_KEY": "Recommended for meta intelligence",
        "EXA_API_KEY": "Recommended for semantic search",
        "VULTR_API_KEY": "GPU embeddings fallback",
        "BRAVE_API_KEY": "Privacy-preserving search",
        "PERPLEXITY_API_KEY": "Long-form research fallback",
        "JINA_AI_API_KEY": "Content rerankers",
        "KAGI_API_KEY": "High precision search",
        "GITHUB_API_KEY": "Repository-scope search",
    }

    has_missing_required = False

    for key, description in required_keys.items():
        if os.getenv(key):
            env_status[key] = "✓ Configured"
        else:
            env_status[key] = f"✗ Missing - {description}"
            has_missing_required = True

    for key, description in optional_keys.items():
        if os.getenv(key):
            env_status[key] = "✓ Configured"
        else:
            env_status[key] = f"⚠ Not configured - {description}"

    status_html = "<h3>Environment Configuration</h3><ul>"
    for key, status in env_status.items():
        status_html += f"<li><strong>{key}:</strong> {status}</li>"
    status_html += "</ul>"

    if has_missing_required:
        status_html += (
            "<p style='color: red;'><strong>⚠ Warning:</strong> "
            "Some required API keys are missing. Configure them in the HF Space settings."  # noqa: E501
            "</p>"
        )

    return status_html


def create_gradio_interface():
    """Create the Gradio interface with tabs."""

    # About content with Vawlrath's personality
    about_html = textwrap.dedent(
        f"""
<div style="padding: 20px;">
    <h1>Arena Improver</h1>
    <p style="font-style: italic; color: #666;">
        "Your deck's terrible. Let me show you how to fix it."<br/>
        — <strong>Vawlrathh, The Small'n</strong>
    </p>

    <h2>🎯 What This Is</h2>
    <p>
        Listen up. I'm <strong>Vawlrathh, The Small'n</strong>—a pint-sized,
        sharp-tongued version of Volrath, The Fallen. Despite my stature, I
        know MTG Arena better than you know your own deck (which, frankly,
        isn't saying much).
    </p>

    <p>
        <strong>Arena Improver</strong> is an MCP-powered deck analysis tool
        that actually works. It analyzes your janky brews, tells you what's
        wrong (plenty), and helps you build something that won't embarrass
        you at FNM.
    </p>

    <h3>What Makes This Not-Garbage</h3>
    <ul>
        <li><strong>Physical Card Prices:</strong> Shows you what your Arena
        deck costs in real cardboard</li>
        <li><strong>Real-Time Strategy Chat:</strong> Talk to me via WebSocket.
        I'll tell you the truth</li>
        <li><strong>AI Consensus Checking:</strong> Two AI brains so you don't
        get bad advice</li>
        <li><strong>Sequential Reasoning:</strong> Breaks down complex
        decisions into steps you can follow</li>
        <li><strong>Full MCP Integration:</strong> Memory, sequential thinking,
        omnisearch—the works</li>
    </ul>

    <h3>🎖️ MCP 1st Birthday Hackathon</h3>
    <p>
        This project is submitted for the
        <strong>MCP 1st Birthday Hackathon</strong>. Visit the
        <a href="https://huggingface.co/MCP-1st-Birthday" target="_blank">
            hackathon page
        </a>
        to see more MCP-powered projects.
    </p>

    <p style="margin-top: 30px; color: #666;">
        <strong>Repository:</strong>
        <a href="{REPO_URL}" target="_blank">
            github.com/clduab11/arena-improver
        </a>
    </p>
 </div>
        """
    )

    # Quick Start instructions
    quick_start_html = textwrap.dedent(
        f"""
<div style="padding: 20px;">
    <h2>🚀 Quick Start Guide</h2>

    <h3>Using the API</h3>
    <p>
        The FastAPI server is running and accessible through the
        <strong>API Documentation</strong> tab. You can explore all available
        endpoints, try them out directly, and see example responses.
    </p>

    <h3>Key Endpoints</h3>
    <ul>
        <li>
            <strong>POST /api/v1/upload/csv</strong> - Upload a deck from Steam
            Arena CSV export
        </li>
        <li>
            <strong>POST /api/v1/upload/text</strong> - Upload a deck from
            Arena text format
        </li>
        <li>
            <strong>POST /api/v1/analyze/{{deck_id}}</strong>
            - Analyze a deck's strengths and weaknesses
        </li>
        <li>
            <strong>POST /api/v1/optimize/{{deck_id}}</strong>
            - Get AI-powered optimization suggestions
        </li>
        <li>
            <strong>GET /api/v1/purchase/{{deck_id}}</strong>
            - Get physical card purchase information
        </li>
        <li>
            <strong>WebSocket /api/v1/ws/chat/{{user_id}}</strong>
            - Chat with Vawlrathh in real-time
        </li>
    </ul>

    <h3>Example Workflow</h3>
    <ol>
        <li>Export your deck from Arena as CSV or text</li>
        <li>Upload it using the <code>/api/v1/upload/csv</code> or
        <code>/api/v1/upload/text</code> endpoint</li>
        <li>Get the returned <code>deck_id</code></li>
        <li>Analyze it with <code>/api/v1/analyze/{{deck_id}}</code></li>
        <li>Get optimization suggestions with
        <code>/api/v1/optimize/{{deck_id}}</code></li>
        <li>Check physical card prices with
        <code>/api/v1/purchase/{{deck_id}}</code></li>
    </ol>

    <h3>WebSocket Chat</h3>
    <p>
        Connect to <code>ws://this-space-url/api/v1/ws/chat/your_user_id</code>
        to chat with me in real-time. Send JSON messages like:
    </p>
    <pre><code>{{
    "type": "chat",
    "message": "How do I beat control decks?",
    "context": {{"deck_id": 1}}
}}</code></pre>

    <h3>Need Help?</h3>
    <p>
        Check the full documentation at
        <a href="{REPO_URL}" target="_blank">
            GitHub Repository
        </a>
    </p>

    <p style="margin-top: 30px; font-style: italic; color: #666;">
        "If you have to ask, your deck probably needs more removal."<br/>
        — Vawlrathh
    </p>
</div>
        """
    )

    # Environment status
    env_status_html = check_environment()

    # Create the interface with tabs
    with gr.Blocks(
        title="Arena Improver - Vawlrathh's Deck Analysis",
    ) as interface:
        gr.Markdown("# Arena Improver - Vawlrathh, The Small'n")
        gr.Markdown("*Your deck's terrible. Let me show you how to fix it.*")

        with gr.Tabs():
            with gr.Tab("API Documentation"):
                docs_markdown = textwrap.dedent(
                    """
                    ### Interactive API Documentation
                    Use the embedded Swagger UI below to explore and test the
                    available API endpoints. Expand any route and select
                    "Try it out" to make test requests directly from the
                    browser.

                    **Note:** API documentation is available at `/docs` on the
                    same port as this interface.
                    """
                )
                gr.Markdown(docs_markdown)

                # Use /docs directly since FastAPI and Gradio are on the same port
                iframe_html = textwrap.dedent(
                    """
                    <iframe
                        src="/docs"
                        width="100%"
                        height="800px"
                        style="border: 1px solid #ccc; border-radius: 4px;">
                    </iframe>
                    """
                )
                gr.HTML(iframe_html)

            with gr.Tab("About"):
                gr.HTML(about_html)

            with gr.Tab("Quick Start"):
                gr.HTML(quick_start_html)

            with gr.Tab("Status"):
                gr.HTML(env_status_html)
                troubleshooting_md = textwrap.dedent(
                    f"""
                    ### Troubleshooting
                    If you see missing API keys above:
                    1. Open your Hugging Face Space settings
                    2. Navigate to "Repository secrets"
                    3. Add the required API keys shown in the table
                    4. Restart the Space from the top bar

                    See the [HF Deployment Guide][hf-deployment-guide] for
                    detailed instructions.

                    [hf-deployment-guide]: {HF_DEPLOYMENT_GUIDE_URL}
                    """
                )
                gr.Markdown(troubleshooting_md)

            with gr.Tab("Deck Uploads"):
                build_deck_uploader_tab()

            with gr.Tab("Chat"):
                build_chat_ui_tab()

            with gr.Tab("Meta Intelligence"):
                build_meta_dashboard_tab()

        footer_md = textwrap.dedent(
            f"""
            ---
            <p style="text-align: center; color: #666; font-size: 0.9em;">
                Diminutive in size, not in strategic prowess. |
                <a href="{REPO_URL}" target="_blank">
                    GitHub Repository
                </a>
                |
                <a href="{HACKATHON_URL}" target="_blank">
                    MCP 1st Birthday Hackathon
                </a>
            </p>
            """
        )
        gr.Markdown(footer_md)

    return interface


def create_combined_app():
    """Create a combined FastAPI + Gradio application.

    Returns:
        FastAPI: The combined application with Gradio mounted at /gradio subpath.
    """
    # Create Gradio interface
    logger.info("Creating Gradio interface...")
    gradio_interface = create_gradio_interface()

    # Mount Gradio onto FastAPI at /gradio subpath
    # FastAPI routes remain at /api/v1/*, /docs, /health, etc.
    # Gradio UI is accessible at /gradio for cleaner separation
    combined_app = mount_gradio_app(fastapi_app, gradio_interface, path="/gradio")

    logger.info("Gradio mounted on FastAPI at /gradio subpath")
    return combined_app


# Factory function to create the combined app for uvicorn or testing
def get_app():
    return create_combined_app()


# Create the app at module level for ASGI servers (e.g., uvicorn)
app = get_app()


@fastapi_app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    if client:
        await client.aclose()


def main():
    """Main entry point for the Hugging Face Space."""
    logger.info("=" * 60)
    logger.info("Arena Improver - Hugging Face Space")
    logger.info("=" * 60)
    logger.info("Starting combined FastAPI + Gradio server on port %s", FASTAPI_PORT)
    logger.info("=" * 60)

    # Launch the combined app with uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=FASTAPI_PORT,
        log_level="info",
        loop="asyncio",
    )


if __name__ == "__main__":
    main()
