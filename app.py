"""Hugging Face Space wrapper for Vawlrathh.

This module provides a combined Gradio + FastAPI application for deployment
on Hugging Face Spaces. Both services run on port 7860 (HF Space default)
using Gradio's mount_gradio_app to consolidate the servers.

The Gradio UI is mounted at /gradio subpath for clean separation from FastAPI routes.
FastAPI endpoints are available at /api/v1/*, /docs, /health, etc.

"Your deck's terrible. Let me show you how to fix it."
— Vawlrathh, The Small'n
"""

# pylint: disable=no-member

import json
import logging
import os
import sys
import textwrap
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import gradio as gr
from gradio import mount_gradio_app
import httpx
import uvicorn
import websockets
from PIL import Image
import io

import traceback

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# GPU / Spaces Configuration
# -----------------------------------------------------------------------------
try:
    import spaces
    HF_SPACE_ENVIRONMENT = True
except ImportError:
    # Create a dummy decorator for local development
    class spaces:
        @staticmethod
        def GPU(duration=60):
            def decorator(func):
                return func
            return decorator
    HF_SPACE_ENVIRONMENT = False


@spaces.GPU(duration=10)
def initialize_gpu():
    """Initialize GPU runtime for HF Spaces ZERO.
    
    This function exists primarily to satisfy the ZeroGPU requirement that
    at least one function must be decorated with @spaces.GPU.
    """
    import torch
    if torch.cuda.is_available():
        device = torch.cuda.get_device_name(0)
        logger.info(f"GPU initialized: {device}")
        return {"gpu": device, "cuda_available": True}
    return {"gpu": None, "cuda_available": False}


# Try to import the main FastAPI app
try:
    from src.main import app as fastapi_app
    logger.info("Successfully imported FastAPI app from src.main")
except Exception as e:
    logger.error(f"Failed to import FastAPI app: {e}")
    logger.error(traceback.format_exc())
    
    # Capture error details for the closure
    error_msg = str(e)
    error_traceback = traceback.format_exc()
    
    # Create a minimal FastAPI app as fallback
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    fastapi_app = FastAPI(title="Vawlrathh - Recovery Mode")
    
    @fastapi_app.get("/")
    def read_root():
        return {
            "status": "error",
            "message": "Main application failed to load",
            "error": error_msg,
            "details": error_traceback.splitlines()
        }
        
    @fastapi_app.get("/health")
    def health_check():
        return {"status": "recovery_mode", "error": error_msg}

    logger.warning("Running in Recovery Mode due to import failure")

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
REPO_URL = "https://github.com/clduab11/vawlrathh"
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


# -----------------------------------------------------------------------------
# Dynamic Color Extraction Engine
# -----------------------------------------------------------------------------

def extract_palette_from_image(image_file) -> Tuple[str, str, str]:
    """Extract 3 dominant colors from an uploaded image for dynamic theming.

    Args:
        image_file: Gradio file upload object or PIL Image

    Returns:
        Tuple of 3 hex color strings (primary, secondary, tertiary)
    """
    try:
        # Handle different input types
        if image_file is None:
            return ("#00ff88", "#b744ff", "#ff4466")  # Default Phyrexian colors

        # If it's a file path string
        if isinstance(image_file, str):
            img = Image.open(image_file)
        # If it's a Gradio file object
        elif hasattr(image_file, 'name'):
            img = Image.open(image_file.name)
        # If it's already a PIL Image
        elif isinstance(image_file, Image.Image):
            img = image_file
        else:
            return ("#00ff88", "#b744ff", "#ff4466")

        # Resize for faster processing
        img = img.resize((150, 150))
        img = img.convert('RGB')

        # Get pixel data
        pixels = list(img.getdata())

        # Simple color quantization - group similar colors
        color_buckets = {}
        for r, g, b in pixels:
            # Reduce to 32 color levels per channel (5-bit)
            key = (r // 32 * 32, g // 32 * 32, b // 32 * 32)
            color_buckets[key] = color_buckets.get(key, 0) + 1

        # Get top 3 most common colors
        sorted_colors = sorted(color_buckets.items(), key=lambda x: x[1], reverse=True)

        # Convert to hex and filter out very dark/light colors for better UI
        dominant_colors = []
        for (r, g, b), count in sorted_colors:
            # Skip very dark (near black) and very light (near white) colors
            brightness = (r + g + b) / 3
            if 30 < brightness < 225:  # Mid-range colors only
                hex_color = f"#{r:02x}{g:02x}{b:02x}"
                dominant_colors.append(hex_color)

            if len(dominant_colors) == 3:
                break

        # Ensure we have 3 colors
        while len(dominant_colors) < 3:
            dominant_colors.append("#00ff88")

        logger.info(f"Extracted palette: {dominant_colors}")
        return tuple(dominant_colors[:3])

    except Exception as exc:
        logger.error(f"Color extraction failed: {exc}")
        return ("#00ff88", "#b744ff", "#ff4466")  # Fallback to default


# -----------------------------------------------------------------------------
# Custom Dark Theme CSS
# -----------------------------------------------------------------------------

VILLAIN_CSS = """
/* Phyrexian Villain Command Center Theme */
:root {
    --bg-primary: #0a0a0f;
    --bg-secondary: #1a1a2e;
    --bg-tertiary: #16213e;
    --accent-primary: #00ff88;
    --accent-secondary: #b744ff;
    --accent-tertiary: #ff4466;
    --text-primary: #e0e0e0;
    --text-secondary: #888899;
    --border-color: #2a2a3e;
    --glow-color: rgba(0, 255, 136, 0.6);
}

/* Global dark mode enforcement */
body, .gradio-container {
    background: var(--bg-primary) !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Glitch text animation for header */
@keyframes glitch {
    0% { transform: translate(0) }
    20% { transform: translate(-2px, 2px) }
    40% { transform: translate(-2px, -2px) }
    60% { transform: translate(2px, 2px) }
    80% { transform: translate(2px, -2px) }
    100% { transform: translate(0) }
}

.villain-header {
    background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--bg-tertiary) 100%);
    border: 2px solid var(--accent-primary);
    border-radius: 8px;
    padding: 30px;
    margin-bottom: 20px;
    box-shadow: 0 0 30px var(--glow-color);
    position: relative;
    overflow: hidden;
}

.villain-header::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle, rgba(0,255,136,0.1) 0%, transparent 70%);
    animation: pulse 4s ease-in-out infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 0.3; }
    50% { opacity: 0.8; }
}

.villain-title {
    font-size: 3em;
    font-weight: 900;
    color: var(--accent-primary);
    text-shadow: 0 0 20px var(--glow-color);
    margin: 0;
    letter-spacing: 2px;
    animation: glitch 3s infinite;
}

.villain-subtitle {
    font-size: 1.2em;
    color: var(--text-secondary);
    font-style: italic;
    margin-top: 10px;
    font-family: 'Courier New', monospace;
}

/* Pulsing glow button (CTA) */
@keyframes button-glow {
    0%, 100% {
        box-shadow: 0 0 10px var(--accent-primary), 0 0 20px var(--accent-primary);
    }
    50% {
        box-shadow: 0 0 20px var(--accent-primary), 0 0 40px var(--accent-primary), 0 0 60px var(--accent-primary);
    }
}

.primary-action-btn {
    background: linear-gradient(135deg, var(--accent-primary) 0%, #00dd77 100%) !important;
    color: var(--bg-primary) !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 4px !important;
    padding: 12px 24px !important;
    font-size: 1.1em !important;
    animation: button-glow 2s ease-in-out infinite !important;
    cursor: pointer !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
}

/* All buttons dark theme */
button {
    background: var(--bg-tertiary) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--accent-secondary) !important;
    border-radius: 4px !important;
    padding: 10px 20px !important;
    transition: all 0.3s ease !important;
}

button:hover {
    background: var(--accent-secondary) !important;
    color: white !important;
    box-shadow: 0 0 15px rgba(183, 68, 255, 0.5) !important;
}

/* Input fields dark theme */
input, textarea, select {
    background: var(--bg-secondary) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 4px !important;
    padding: 10px !important;
}

input:focus, textarea:focus, select:focus {
    border-color: var(--accent-primary) !important;
    box-shadow: 0 0 10px var(--glow-color) !important;
    outline: none !important;
}

/* Monospace font for analysis outputs */
.analysis-output, .chat-output, .deck-data {
    font-family: 'Courier New', 'Monaco', monospace !important;
    background: var(--bg-secondary) !important;
    border: 1px solid var(--accent-primary) !important;
    border-radius: 4px !important;
    padding: 15px !important;
    color: var(--accent-primary) !important;
    line-height: 1.6 !important;
}

/* Tabs dark theme */
.tab-nav button {
    background: var(--bg-secondary) !important;
    border-bottom: 2px solid transparent !important;
}

.tab-nav button.selected {
    border-bottom-color: var(--accent-primary) !important;
    color: var(--accent-primary) !important;
}

/* Cards and containers */
.control-panel {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--accent-secondary) !important;
    border-radius: 8px !important;
    padding: 20px !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5) !important;
}

.output-panel {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--accent-primary) !important;
    border-radius: 8px !important;
    padding: 20px !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5) !important;
}

/* Chat interface terminal style */
.chatbot {
    background: var(--bg-primary) !important;
    border: 1px solid var(--accent-primary) !important;
    border-radius: 4px !important;
    font-family: 'Courier New', monospace !important;
}

.chatbot .message {
    background: var(--bg-secondary) !important;
    border-left: 3px solid var(--accent-primary) !important;
    padding: 10px !important;
    margin: 5px 0 !important;
}

/* JSON outputs */
.json-output {
    background: var(--bg-primary) !important;
    border: 1px solid var(--accent-secondary) !important;
    border-radius: 4px !important;
    padding: 15px !important;
    font-family: 'Courier New', monospace !important;
    font-size: 0.9em !important;
    color: var(--accent-secondary) !important;
}

/* Footer */
footer {
    background: var(--bg-primary) !important;
    border-top: 1px solid var(--border-color) !important;
    color: var(--text-secondary) !important;
}

/* Scrollbars */
::-webkit-scrollbar {
    width: 10px;
    height: 10px;
}

::-webkit-scrollbar-track {
    background: var(--bg-primary);
}

::-webkit-scrollbar-thumb {
    background: var(--accent-secondary);
    border-radius: 5px;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--accent-primary);
}

/* Label styling */
label {
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    margin-bottom: 8px !important;
    display: block !important;
}

/* File upload area */
.file-upload {
    background: var(--bg-secondary) !important;
    border: 2px dashed var(--accent-primary) !important;
    border-radius: 8px !important;
    padding: 20px !important;
    text-align: center !important;
    transition: all 0.3s ease !important;
}

.file-upload:hover {
    border-color: var(--accent-secondary) !important;
    background: var(--bg-tertiary) !important;
}
"""


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


def build_gpu_status_tab():
    """GPU status and initialization tab."""
    gr.Markdown("## GPU Status")
    
    gpu_status = gr.JSON(label="GPU Information", value={})
    init_btn = gr.Button("Initialize GPU", variant="primary")
    
    init_btn.click(
        fn=initialize_gpu,  # Call GPU function only on button click
        outputs=gpu_status
    )
    
    gr.Markdown(
        "Click 'Initialize GPU' to test GPU availability. "
        "This is optional - the app works on CPU if GPU is not available."
    )


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


@builder_registry(
    name="theme_designer",
    description="Dynamic color theme extraction",
    endpoints=[],
)
def build_theme_designer_tab():
    """Theme designer tab for dynamic color extraction from card art."""

    gr.Markdown("## 🎨 Design Interface")
    gr.Markdown(
        "Upload an MTG card or any image to extract its dominant colors "
        "and apply them to the interface theme."
    )

    theme_image = gr.Image(
        label="Submit Visual Data",
        type="filepath",
        sources=["upload"],
    )
    extract_btn = gr.Button("Extract Color Palette", variant="primary", elem_classes=["primary-action-btn"])
    palette_output = gr.JSON(label="Extracted Palette", value={})
    theme_preview = gr.HTML(label="Theme Preview")

    def handle_palette_extraction(image):
        """Extract colors and generate preview HTML."""
        color1, color2, color3 = extract_palette_from_image(image)

        palette_data = {
            "primary_accent": color1,
            "secondary_accent": color2,
            "tertiary_accent": color3,
            "status": "Colors extracted successfully",
            "note": "Colors will be applied to the interface dynamically (future enhancement)"
        }

        # Generate preview HTML
        preview_html = f"""
        <div style="padding: 20px; background: #1a1a2e; border-radius: 8px;">
            <h3 style="color: #e0e0e0; margin-bottom: 15px;">Color Palette Preview</h3>
            <div style="display: flex; gap: 20px; justify-content: center;">
                <div style="text-align: center;">
                    <div style="width: 120px; height: 120px; background: {color1};
                         border-radius: 8px; box-shadow: 0 0 20px {color1};"></div>
                    <p style="color: #888; margin-top: 10px; font-family: monospace;">PRIMARY<br/>{color1}</p>
                </div>
                <div style="text-align: center;">
                    <div style="width: 120px; height: 120px; background: {color2};
                         border-radius: 8px; box-shadow: 0 0 20px {color2};"></div>
                    <p style="color: #888; margin-top: 10px; font-family: monospace;">SECONDARY<br/>{color2}</p>
                </div>
                <div style="text-align: center;">
                    <div style="width: 120px; height: 120px; background: {color3};
                         border-radius: 8px; box-shadow: 0 0 20px {color3};"></div>
                    <p style="color: #888; margin-top: 10px; font-family: monospace;">TERTIARY<br/>{color3}</p>
                </div>
            </div>
        </div>
        """

        return palette_data, preview_html

    extract_btn.click(
        fn=handle_palette_extraction,
        inputs=theme_image,
        outputs=[palette_output, theme_preview],
    )

    gr.Markdown(
        "*Note: Dynamic theme application requires JavaScript injection and will be "
        "enhanced in future versions. Current implementation extracts and displays colors.*"
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
    """Create the gamified Gradio interface with villain theme."""

    # Custom villain header with glitch effect
    villain_header_html = """
    <div class="villain-header">
        <div style="position: relative; z-index: 1;">
            <h1 class="villain-title">⚡ VAWLRATHH ⚡</h1>
            <p class="villain-subtitle">
                &gt;&gt; Your deck's terrible. Let me show you how to fix it. &lt;&lt;
            </p>
            <p style="color: #888899; font-size: 0.9em; margin-top: 15px; font-family: monospace;">
                [ SYSTEM STATUS: OPERATIONAL | AI CORES: ONLINE | THREAT LEVEL: MAXIMUM ]
            </p>
        </div>
    </div>
    """

    # About content with enhanced dark theme
    about_html = textwrap.dedent(
        f"""
<div style="padding: 20px; background: #1a1a2e; border-radius: 8px; color: #e0e0e0;">
    <h2 style="color: #00ff88;">🎯 MISSION BRIEFING</h2>
    <p style="font-style: italic; color: #888899; border-left: 3px solid #00ff88; padding-left: 15px;">
        "Your deck's terrible. Let me show you how to fix it."<br/>
        — <strong style="color: #b744ff;">Vawlrathh, The Small'n</strong>
    </p>

    <p>
        Listen up. I'm <strong style="color: #00ff88;">Vawlrathh, The Small'n</strong>—a pint-sized,
        sharp-tongued version of Volrath, The Fallen. Despite my stature, I
        know MTG Arena better than you know your own deck (which, frankly,
        isn't saying much).
    </p>

    <p>
        <strong>Vawlrathh</strong> is an MCP-powered deck analysis tool
        that actually works. It analyzes your janky brews, tells you what's
        wrong (plenty), and helps you build something that won't embarrass
        you at FNM.
    </p>

    <h3 style="color: #b744ff;">⚡ CORE CAPABILITIES</h3>
    <ul style="list-style-type: none; padding-left: 0;">
        <li style="padding: 8px 0; border-bottom: 1px solid #2a2a3e;">
            <strong style="color: #00ff88;">▸ Physical Card Prices:</strong>
            Shows you what your Arena deck costs in real cardboard
        </li>
        <li style="padding: 8px 0; border-bottom: 1px solid #2a2a3e;">
            <strong style="color: #00ff88;">▸ Real-Time Strategy Chat:</strong>
            Talk to me via WebSocket. I'll tell you the truth
        </li>
        <li style="padding: 8px 0; border-bottom: 1px solid #2a2a3e;">
            <strong style="color: #00ff88;">▸ AI Consensus Checking:</strong>
            Two AI brains so you don't get bad advice
        </li>
        <li style="padding: 8px 0; border-bottom: 1px solid #2a2a3e;">
            <strong style="color: #00ff88;">▸ Sequential Reasoning:</strong>
            Breaks down complex decisions into steps you can follow
        </li>
        <li style="padding: 8px 0;">
            <strong style="color: #00ff88;">▸ Full MCP Integration:</strong>
            Memory, sequential thinking, omnisearch—the works
        </li>
    </ul>

    <h3 style="color: #b744ff; margin-top: 30px;">🎖️ MCP 1st Birthday Hackathon</h3>
    <p>
        This project is submitted for the
        <strong>MCP 1st Birthday Hackathon</strong>. Visit the
        <a href="{HACKATHON_URL}" target="_blank" style="color: #00ff88;">
            hackathon page
        </a>
        to see more MCP-powered projects.
    </p>

    <p style="margin-top: 30px; color: #888899; font-family: monospace;">
        <strong>REPOSITORY:</strong>
        <a href="{REPO_URL}" target="_blank" style="color: #b744ff;">
            github.com/clduab11/vawlrathh
        </a>
    </p>
 </div>
        """
    )

    # Quick Start with dark theme
    quick_start_html = textwrap.dedent(
        f"""
<div style="padding: 20px; background: #1a1a2e; border-radius: 8px; color: #e0e0e0;">
    <h2 style="color: #00ff88;">🚀 INITIALIZATION PROTOCOL</h2>

    <h3 style="color: #b744ff;">Using the API</h3>
    <p>
        The FastAPI server is running and accessible through the
        <strong>API Documentation</strong> tab. You can explore all available
        endpoints, try them out directly, and see example responses.
    </p>

    <h3 style="color: #b744ff;">Key Endpoints</h3>
    <ul style="font-family: 'Courier New', monospace; font-size: 0.9em;">
        <li style="padding: 5px 0;">
            <strong style="color: #00ff88;">POST /api/v1/upload/csv</strong> - Upload deck from Steam Arena CSV
        </li>
        <li style="padding: 5px 0;">
            <strong style="color: #00ff88;">POST /api/v1/upload/text</strong> - Upload deck from Arena text format
        </li>
        <li style="padding: 5px 0;">
            <strong style="color: #00ff88;">POST /api/v1/analyze/{{deck_id}}</strong> - Analyze deck composition
        </li>
        <li style="padding: 5px 0;">
            <strong style="color: #00ff88;">POST /api/v1/optimize/{{deck_id}}</strong> - Get AI-powered suggestions
        </li>
        <li style="padding: 5px 0;">
            <strong style="color: #00ff88;">GET /api/v1/purchase/{{deck_id}}</strong> - Physical card pricing
        </li>
        <li style="padding: 5px 0;">
            <strong style="color: #00ff88;">WebSocket /api/v1/ws/chat/{{user_id}}</strong> - Real-time strategy chat
        </li>
    </ul>

    <h3 style="color: #b744ff; margin-top: 20px;">Example Workflow</h3>
    <ol style="line-height: 1.8;">
        <li>Export your deck from Arena as CSV or text</li>
        <li>Upload it using <code style="background: #0a0a0f; padding: 2px 6px; border-radius: 3px; color: #00ff88;">/api/v1/upload/csv</code></li>
        <li>Retrieve the returned <code style="background: #0a0a0f; padding: 2px 6px; border-radius: 3px; color: #00ff88;">deck_id</code></li>
        <li>Analyze with <code style="background: #0a0a0f; padding: 2px 6px; border-radius: 3px; color: #00ff88;">/api/v1/analyze/{{deck_id}}</code></li>
        <li>Get optimization suggestions</li>
        <li>Check physical card prices</li>
    </ol>

    <p style="margin-top: 30px; font-style: italic; color: #888899; border-left: 3px solid #b744ff; padding-left: 15px;">
        "If you have to ask, your deck probably needs more removal."<br/>
        — Vawlrathh
    </p>
</div>
        """
    )

    # Environment status
    env_status_html = check_environment()

    # Create the interface with dark theme and custom CSS
    with gr.Blocks(
        title="Vawlrathh - Command Center",
        css=VILLAIN_CSS,
        theme=gr.themes.Base(
            primary_hue="emerald",
            secondary_hue="purple",
            neutral_hue="slate",
        ).set(
            body_background_fill="#0a0a0f",
            body_background_fill_dark="#0a0a0f",
            background_fill_primary="#1a1a2e",
            background_fill_primary_dark="#1a1a2e",
            background_fill_secondary="#16213e",
            background_fill_secondary_dark="#16213e",
            border_color_primary="#00ff88",
            border_color_primary_dark="#00ff88",
        ),
    ) as interface:
        # Custom villain header
        gr.HTML(villain_header_html)

        with gr.Tabs():
            # Dashboard Tab - 2 Column Layout
            with gr.Tab("⚡ Command Center"):
                gr.Markdown("## Deck Analysis Command Center")

                with gr.Row():
                    # LEFT COLUMN - Control Panel (30%)
                    with gr.Column(scale=3, elem_classes=["control-panel"]):
                        gr.Markdown("### 🎮 CONTROL PANEL")

                        # Deck upload section
                        gr.Markdown("#### Submit Deck Data")
                        deck_id_state = gr.State(value=None)
                        deck_id_display = gr.Number(
                            label="Active Deck ID",
                            interactive=False,
                            elem_classes=["deck-data"]
                        )

                        csv_input = gr.File(
                            file_types=[".csv"],
                            label="CSV Upload",
                            elem_classes=["file-upload"]
                        )
                        csv_upload_btn = gr.Button(
                            "📤 Upload CSV",
                            variant="primary",
                            elem_classes=["primary-action-btn"]
                        )

                        gr.Markdown("---")

                        deck_text_input = gr.Textbox(
                            lines=8,
                            label="Arena Text Export",
                            placeholder="4 Lightning Bolt\\n2 Counterspell\\n...",
                            elem_classes=["analysis-output"]
                        )
                        format_dropdown = gr.Dropdown(
                            choices=["Standard", "Pioneer", "Modern"],
                            value="Standard",
                            label="Game Format",
                        )
                        text_upload_btn = gr.Button(
                            "📤 Upload Text",
                            variant="secondary"
                        )

                        upload_status = gr.JSON(
                            label="Upload Status",
                            value={},
                            elem_classes=["json-output"]
                        )

                        # CSV upload handler
                        async def handle_csv_upload(uploaded_file, previous_id):
                            file_path = getattr(uploaded_file, "name", None)
                            payload = await _upload_csv_to_api(file_path)
                            deck_id = payload.get("deck_id") or previous_id
                            return payload, deck_id, deck_id

                        csv_upload_btn.click(
                            fn=handle_csv_upload,
                            inputs=[csv_input, deck_id_state],
                            outputs=[upload_status, deck_id_state, deck_id_display],
                        )

                        # Text upload handler
                        async def handle_text_upload(deck_text, fmt, previous_id):
                            payload = await _upload_text_to_api(deck_text, fmt)
                            deck_id = payload.get("deck_id") or previous_id
                            return payload, deck_id, deck_id

                        text_upload_btn.click(
                            fn=handle_text_upload,
                            inputs=[deck_text_input, format_dropdown, deck_id_state],
                            outputs=[upload_status, deck_id_state, deck_id_display],
                        )

                    # RIGHT COLUMN - Output Panel (70%)
                    with gr.Column(scale=7, elem_classes=["output-panel"]):
                        gr.Markdown("### 📊 ANALYSIS OUTPUT")

                        # Chat interface
                        gr.Markdown("#### Strategic Consultation")
                        connection_status = gr.JSON(
                            label="WebSocket Status",
                            value={},
                            elem_classes=["json-output"]
                        )
                        chatbot = gr.Chatbot(
                            label="Vawlrathh's Analysis",
                            elem_classes=["chatbot", "chat-output"],
                            height=400
                        )
                        chat_history_state = gr.State(value=[])

                        with gr.Row():
                            message_box = gr.Textbox(
                                label="Query",
                                lines=2,
                                placeholder="Ask Vawlrathh how to optimize your deck...",
                                scale=4,
                                elem_classes=["analysis-output"]
                            )
                            send_btn = gr.Button(
                                "⚡ ANALYZE",
                                variant="primary",
                                elem_classes=["primary-action-btn"],
                                scale=1
                            )

                        connect_btn = gr.Button("🔌 Test WebSocket", variant="secondary")

                        connect_btn.click(
                            fn=_check_chat_websocket,
                            outputs=connection_status,
                        )

                        def queue_message(history, message, deck_id):
                            history = history or []
                            if not message or not message.strip():
                                return history, "", history

                            context_note = (
                                f"Deck ID {int(deck_id)} loaded" if deck_id
                                else "No deck context provided"
                            )
                            summary = f"[QUEUED] {context_note}"
                            history.append((message.strip(), summary))
                            return history, "", history

                        send_btn.click(
                            fn=queue_message,
                            inputs=[chat_history_state, message_box, deck_id_state],
                            outputs=[chatbot, message_box, chat_history_state],
                        )

            # Design Interface Tab
            with gr.Tab("🎨 Theme Designer"):
                build_theme_designer_tab()

            # Meta Intelligence Tab
            with gr.Tab("📈 Meta Intelligence"):
                build_meta_dashboard_tab()

            # API Documentation Tab
            with gr.Tab("📡 API Docs"):
                docs_markdown = textwrap.dedent(
                    """
                    ### Interactive API Documentation
                    Use the embedded Swagger UI below to explore and test the
                    available API endpoints. Expand any route and select
                    "Try it out" to make test requests directly from the browser.
                    """
                )
                gr.Markdown(docs_markdown)

                iframe_html = textwrap.dedent(
                    """
                    <iframe
                        src="/docs"
                        width="100%"
                        height="800px"
                        style="border: 1px solid #00ff88; border-radius: 8px; background: #1a1a2e;">
                    </iframe>
                    """
                )
                gr.HTML(iframe_html)

            # About Tab
            with gr.Tab("ℹ️ About"):
                gr.HTML(about_html)

            # Quick Start Tab
            with gr.Tab("🚀 Quick Start"):
                gr.HTML(quick_start_html)

            # Status Tab
            with gr.Tab("⚙️ System Status"):
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

            # GPU Status Tab
            with gr.Tab("🎮 GPU Status"):
                build_gpu_status_tab()

        # Footer
        footer_md = textwrap.dedent(
            f"""
            ---
            <p style="text-align: center; color: #888899; font-size: 0.9em; font-family: monospace;">
                [ DIMINUTIVE IN SIZE, NOT IN STRATEGIC PROWESS ] |
                <a href="{REPO_URL}" target="_blank" style="color: #00ff88;">
                    GitHub Repository
                </a>
                |
                <a href="{HACKATHON_URL}" target="_blank" style="color: #b744ff;">
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
        FastAPI: The combined application with Gradio mounted at root path.
    """
    # Create Gradio interface
    logger.info("Creating Gradio interface...")
    gradio_interface = create_gradio_interface()

    # Mount Gradio onto FastAPI at root path
    # FastAPI routes remain at /api/v1/*, /docs, /health, etc.
    # Gradio UI is accessible at root path for HF Spaces compatibility
    combined_app = mount_gradio_app(fastapi_app, gradio_interface, path="/")

    logger.info("Gradio mounted on FastAPI at root path")
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
    logger.info("Vawlrathh - Hugging Face Space")
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
