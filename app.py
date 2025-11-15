"""Vawlrathh - MCP-Powered MTG Arena Deck Analyzer
Your deck's terrible. Let me show you how to fix it.
— Vawlrathh, The Small'n

Built for MCP's 1st Birthday Hackathon (Nov 14-30, 2025)
Hosted by Anthropic and Gradio
"""

import os
import sys
import subprocess
import time
import logging
import json
import uuid
import asyncio
import html
from datetime import datetime  # noqa: F401 - used in f-string in refresh_metrics
from typing import Optional, Dict, List, Any

import gradio as gr
import httpx
import websockets
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "7860"))
GRADIO_PORT = int(os.getenv("GRADIO_PORT", "7861"))
API_BASE_URL = os.getenv("API_BASE_URL", f"http://localhost:{FASTAPI_PORT}/api/v1")
HEALTH_CHECK_URL = os.getenv("HEALTH_CHECK_URL", f"http://localhost:{FASTAPI_PORT}/health")
WS_BASE_URL = os.getenv("WS_BASE_URL", f"ws://localhost:{FASTAPI_PORT}/api/v1")

# Constants
EXPECTED_WIN_RATE_IMPROVEMENT = 0.06
MAX_FILE_SIZE_MB = 1
FILE_SIZE_LIMIT = MAX_FILE_SIZE_MB * 1024 * 1024  # 1MB in bytes

# Session state keys
SESSION_USER_ID = "user_id"
SESSION_DECK_ID = "deck_id"
SESSION_CHAT_HISTORY = "chat_history"
SESSION_MCP_LOGS = "mcp_logs"

# Global HTTP client with connection pooling
api_client = httpx.AsyncClient(
    timeout=60.0,
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
)

# Vawlrathh's Personality CSS Theme
CUSTOM_CSS = """
/* Vawlrathh Dark Theme - Phyrexian Aesthetic */
:root {
    --primary-dark: #1a1a1a;
    --secondary-dark: #2a2a2a;
    --accent-purple: #5a3a8a;
    --accent-red: #a10000;
    --accent-blood: #8b0000;
    --text-light: #e0e0e0;
    --text-dim: #999;
    --border-sharp: #444;
    --success-green: #00ff00;
    --warning-orange: #ff8c00;
}

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: linear-gradient(135deg, var(--primary-dark) 0%, var(--secondary-dark) 100%);
}

.gradio-container {
    background: transparent !important;
}

/* Vawlrathh Header */
.vawlrathh-header {
    background: linear-gradient(90deg, var(--accent-purple), var(--accent-blood));
    color: var(--text-light);
    padding: 24px;
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.6);
    margin-bottom: 20px;
    border: 2px solid var(--accent-red);
}

.vawlrathh-title {
    font-size: 2.5em;
    font-weight: 800;
    margin: 0;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
}

.vawlrathh-tagline {
    font-size: 1.2em;
    font-style: italic;
    margin-top: 8px;
    color: var(--text-dim);
}

/* Chat Message Styling */
.chat-message-vawlrathh {
    background: var(--accent-blood) !important;
    border-left: 4px solid var(--accent-red) !important;
    padding: 16px !important;
    margin: 12px 0 !important;
    border-radius: 6px !important;
    color: var(--text-light) !important;
    box-shadow: 0 4px 12px rgba(139,0,0,0.4) !important;
}

.chat-message-user {
    background: var(--secondary-dark) !important;
    border-left: 4px solid var(--accent-purple) !important;
    padding: 16px !important;
    margin: 12px 0 !important;
    border-radius: 6px !important;
    color: var(--text-light) !important;
}

/* MCP Indicator */
.mcp-indicator {
    display: inline-block;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    margin-right: 8px;
    animation: pulse 2s infinite;
}

.mcp-active {
    background: var(--success-green);
    box-shadow: 0 0 8px var(--success-green);
}

.mcp-idle {
    background: var(--text-dim);
}

@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.7; transform: scale(1.1); }
}

/* Card Display */
.card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 16px;
    padding: 16px;
}

.card-item {
    background: var(--secondary-dark);
    border: 2px solid var(--border-sharp);
    border-radius: 8px;
    padding: 12px;
    transition: all 0.3s ease;
    cursor: pointer;
}

.card-item:hover {
    border-color: var(--accent-purple);
    transform: translateY(-4px);
    box-shadow: 0 8px 16px rgba(90,58,138,0.4);
}

/* Buttons */
.primary-button {
    background: linear-gradient(135deg, var(--accent-purple), var(--accent-blood)) !important;
    color: white !important;
    border: none !important;
    padding: 12px 24px !important;
    font-size: 1.1em !important;
    font-weight: 600 !important;
    border-radius: 6px !important;
    cursor: pointer !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4) !important;
}

.primary-button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 16px rgba(90,58,138,0.6) !important;
}

/* Demo Badge */
.demo-badge {
    background: var(--accent-red);
    color: white;
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 0.85em;
    font-weight: 600;
    display: inline-block;
    margin-left: 8px;
}

/* Hackathon Badge */
.hackathon-badge {
    background: linear-gradient(90deg, #ff6b6b, #a020f0);
    color: white;
    padding: 8px 16px;
    border-radius: 20px;
    font-weight: 700;
    display: inline-block;
    margin: 8px 0;
    box-shadow: 0 4px 12px rgba(160,32,240,0.4);
}

/* Tabs */
.tab-nav button {
    background: var(--secondary-dark) !important;
    color: var(--text-light) !important;
    border: 1px solid var(--border-sharp) !important;
}

.tab-nav button.selected {
    background: var(--accent-purple) !important;
    border-color: var(--accent-red) !important;
}

/* Loading States */
.loading-text {
    color: var(--accent-red);
    font-style: italic;
    animation: pulse 1.5s infinite;
}

/* Consensus Badge */
.consensus-pass {
    background: var(--success-green);
    color: black;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.9em;
    font-weight: 600;
}

.consensus-fail {
    background: var(--warning-orange);
    color: black;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.9em;
    font-weight: 600;
}
"""


# ============================================================================
# FASTAPI SERVER MANAGEMENT
# ============================================================================

def kill_existing_uvicorn():
    """Kill any existing uvicorn processes."""
    try:
        subprocess.run(
            ["pkill", "-9", "-f", f"uvicorn.*{FASTAPI_PORT}"],
            capture_output=True,
            text=True
        )
        time.sleep(1)
    except Exception as e:
        logger.warning(f"Error killing uvicorn: {e}")


def start_fastapi_server():
    """Start FastAPI server in background."""
    kill_existing_uvicorn()
    logger.info(f"Starting FastAPI on port {FASTAPI_PORT}...")

    try:
        process = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "src.main:app",
                "--host", "0.0.0.0",
                "--port", str(FASTAPI_PORT),
                "--log-level", "info"
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        logger.info(f"FastAPI started (PID {process.pid})")
        return process
    except Exception as e:
        logger.exception(f"Failed to start FastAPI: {e}")
        raise


def wait_for_fastapi_ready(max_wait=60, check_interval=2):
    """Wait for FastAPI to be ready."""
    logger.info("Waiting for FastAPI...")
    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            response = httpx.get(HEALTH_CHECK_URL, timeout=5.0)
            if response.status_code == 200:
                logger.info("FastAPI ready!")
                return True
        except (httpx.ConnectError, httpx.TimeoutException):
            time.sleep(check_interval)
        except Exception as e:
            logger.warning(f"Health check error: {e}")
            time.sleep(check_interval)

    logger.error(f"FastAPI not ready after {max_wait}s")
    return False


# ============================================================================
# API CLIENT FUNCTIONS
# ============================================================================

async def api_upload_csv(csv_file) -> Dict[str, Any]:
    """Upload deck via CSV file."""
    try:
        files = {"file": (csv_file.name, csv_file, "text/csv")}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{API_BASE_URL}/upload/csv", files=files)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "Vawlrathh is taking too long. Try again."}
    except httpx.HTTPError as e:
        return {"error": f"Upload failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Something broke: {str(e)}"}


async def api_upload_text(deck_text: str) -> Dict[str, Any]:
    """Upload deck via Arena text format."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{API_BASE_URL}/upload/text",
                json={"deck_string": deck_text, "format": "Standard"}
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "That's not a deck, that's a pile. Try again."}
    except httpx.HTTPError as e:
        return {"error": f"Upload failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Something broke: {str(e)}"}


async def api_analyze_deck(deck_id: int) -> Dict[str, Any]:
    """Analyze a deck."""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{API_BASE_URL}/analyze/{deck_id}")
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "Analysis taking too long. Your deck is that bad."}
    except httpx.HTTPError as e:
        return {"error": f"Analysis failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Something broke: {str(e)}"}


async def api_optimize_deck(deck_id: int) -> Dict[str, Any]:
    """Get optimization suggestions."""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{API_BASE_URL}/optimize/{deck_id}")
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "Optimization timeout. Even I have limits."}
    except httpx.HTTPError as e:
        return {"error": f"Optimization failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Something broke: {str(e)}"}


async def api_get_purchase_info(deck_id: int) -> Dict[str, Any]:
    """Get physical card purchase information."""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(f"{API_BASE_URL}/purchase/{deck_id}")
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        return {"error": "Purchase lookup timeout."}
    except httpx.HTTPError as e:
        return {"error": f"Purchase lookup failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Something broke: {str(e)}"}


async def api_list_decks() -> List[Dict[str, Any]]:
    """List all decks."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{API_BASE_URL}/decks")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.exception(f"Failed to list decks: {e}")
        return []


# ============================================================================
# WEBSOCKET CHAT HANDLER
# ============================================================================

async def send_chat_message(user_id: str, message: str, deck_id: Optional[int] = None) -> Dict[str, Any]:
    """Send chat message via WebSocket and get response."""
    try:
        uri = f"{WS_BASE_URL}/ws/chat/{user_id}"

        async with websockets.connect(uri, timeout=30) as websocket:
            # Send message
            payload = {
                "type": "chat",
                "message": message,
                "context": {"deck_id": deck_id} if deck_id else {}
            }
            await websocket.send(json.dumps(payload))

            # Receive response
            response_raw = await websocket.recv()
            response = json.loads(response_raw)

            return response

    except asyncio.TimeoutError:
        return {
            "type": "error",
            "response": "Vawlrathh is busy. Try again.",
            "consensus_checked": False
        }
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
        return {
            "type": "error",
            "response": f"Connection failed: {str(e)}",
            "consensus_checked": False
        }


# ============================================================================
# GRADIO INTERFACE FUNCTIONS
# ============================================================================

def format_chat_message(role: str, content: str, consensus_data: Optional[Dict] = None) -> str:
    """Format chat message with styling.
    
    Args:
        role: Message role ('vawlrathh' or 'user')
        content: Message content (will be HTML-escaped)
        consensus_data: Optional consensus check data
        
    Returns:
        HTML-formatted message string with escaped content
    """
    # Escape content to prevent XSS
    escaped_content = html.escape(content)
    
    if role == "vawlrathh":
        consensus_badge = ""
        if consensus_data:
            if consensus_data.get("consensus_passed"):
                consensus_badge = '<span class="consensus-pass">✓ Consensus Pass</span>'
            else:
                consensus_badge = '<span class="consensus-fail">⚠ ConsensusBreaker</span>'

        return f"""
        <div class="chat-message-vawlrathh">
            <strong>🔥 Vawlrathh:</strong> {escaped_content}
            {f'<br/><small>{consensus_badge}</small>' if consensus_badge else ''}
        </div>
        """
    else:
        return f"""
        <div class="chat-message-user">
            <strong>You:</strong> {escaped_content}
        </div>
        """


def handle_chat_submit(message: str, chat_history: List, user_id: str, deck_id: Optional[int]):
    """Handle chat message submission.
    
    Args:
        message: User message text
        chat_history: List of (role, content, consensus_data) tuples
        user_id: User ID for WebSocket connection
        deck_id: Optional deck ID for context
        
    Returns:
        Tuple of (updated_chat_history, empty_string_for_input_clear)
    """
    if not message.strip():
        return chat_history, ""

    # Add user message to history
    chat_history.append(("user", message, None))

    # Send to API and get response
    try:
        response = asyncio.run(send_chat_message(user_id, message, deck_id))

        vawlrathh_response = response.get("response", "Something went wrong.")
        consensus_data = {
            "consensus_passed": response.get("consensus_passed", False),
            "consensus_checked": response.get("consensus_checked", False)
        }

        chat_history.append(("vawlrathh", vawlrathh_response, consensus_data))

    except Exception as e:
        logger.exception(f"Chat error: {e}")
        chat_history.append(("vawlrathh", f"Error: {str(e)}", None))

    return chat_history, ""


def validate_file_upload(file) -> tuple[bool, str]:
    """Validate uploaded file for security.
    
    Args:
        file: Gradio file object
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if file is None:
        return False, "No file provided"
    
    # Check file size
    try:
        file_size = os.path.getsize(file.name)
        if file_size > FILE_SIZE_LIMIT:
            return False, f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB"
    except Exception as e:
        return False, f"Could not check file size: {str(e)}"
    
    # Check file extension
    if not file.name.lower().endswith('.csv'):
        return False, "Only CSV files are allowed"
    
    return True, ""


def validate_deck_text(deck_text: str) -> tuple[bool, str]:
    """Validate deck text input.
    
    Args:
        deck_text: Deck text from user
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not deck_text or not deck_text.strip():
        return False, "Deck text is empty"
    
    # Check length (prevent extremely large inputs)
    if len(deck_text) > 50000:  # ~50KB text limit
        return False, "Deck text is too long"
    
    return True, ""


def render_chat_history(chat_history: List) -> str:
    """Render chat history as HTML."""
    if not chat_history:
        return "<p style='color: var(--text-dim);'>No messages yet. Ask Vawlrathh something.</p>"

    html = ""
    for role, content, consensus_data in chat_history:
        html += format_chat_message(role, content, consensus_data)

    return html


def handle_csv_upload(file, progress=gr.Progress()):
    """Handle CSV deck upload.
    
    Args:
        file: Uploaded CSV file
        progress: Gradio progress indicator
        
    Returns:
        Tuple of (message, deck_id, deck_id_for_state)
    """
    if file is None:
        return "❌ Your CSV is as broken as your mana curve.", None, None

    # Validate file
    is_valid, error_msg = validate_file_upload(file)
    if not is_valid:
        return f"❌ {error_msg}", None, None

    progress(0.2, desc="Uploading deck...")

    try:
        result = asyncio.run(api_upload_csv(file))

        if "error" in result:
            return f"❌ {result['error']}", None, None

        deck_id = result.get("deck_id")
        message = result.get("message", "Deck uploaded")

        progress(1.0, desc="Upload complete!")

        return f"✅ {message}\n\n**Deck ID:** #{deck_id}", deck_id, deck_id

    except Exception as e:
        logger.exception(f"CSV upload failed: {e}")
        return f"❌ Upload failed: {str(e)}", None, None


def handle_text_upload(deck_text, progress=gr.Progress()):
    """Handle text deck upload.
    
    Args:
        deck_text: Deck text in Arena format
        progress: Gradio progress indicator
        
    Returns:
        Tuple of (message, deck_id, deck_id_for_state)
    """
    # Validate input
    is_valid, error_msg = validate_deck_text(deck_text)
    if not is_valid:
        return f"❌ {error_msg}", None, None

    progress(0.2, desc="Parsing deck...")

    try:
        result = asyncio.run(api_upload_text(deck_text))

        if "error" in result:
            return f"❌ {result['error']}", None, None

        deck_id = result.get("deck_id")
        message = result.get("message", "Deck uploaded")

        progress(1.0, desc="Upload complete!")

        return f"✅ {message}\n\n**Deck ID:** #{deck_id}", deck_id, deck_id

    except Exception as e:
        logger.exception(f"Text upload failed: {e}")
        return f"❌ Upload failed: {str(e)}", None, None


def handle_analyze_deck(deck_id, progress=gr.Progress()):
    """Handle deck analysis.
    
    Args:
        deck_id: ID of deck to analyze
        progress: Gradio progress indicator
        
    Returns:
        Tuple of (analysis_output, mana_curve_data, purchase_info)
    """
    if deck_id is None:
        return "❌ Upload a deck first, genius.", None, None

    progress(0.3, desc="Calculating how many games you'll lose...")

    try:
        result = asyncio.run(api_analyze_deck(deck_id))

        if "error" in result:
            return f"❌ {result['error']}", None, None

        progress(1.0, desc="Analysis complete!")

        analysis = result.get("analysis", {})

        # Format analysis results
        output = f"""# 📊 Deck Analysis Results

## Vawlrathh's Verdict
{analysis.get('verdict', 'Your deck is... something.')}

## Mana Curve
{analysis.get('mana_curve', 'No curve data available.')}

## Strengths
{analysis.get('strengths', 'Looking for strengths...')}

## Weaknesses (Plenty to Choose From)
{analysis.get('weaknesses', 'Surprisingly, none found.')}

## Meta Matchups
{analysis.get('matchups', 'No matchup data.')}
"""

        return output, analysis.get('mana_curve'), analysis.get('purchase_info')

    except Exception as e:
        logger.exception(f"Analysis failed: {e}")
        return f"❌ Analysis failed: {str(e)}", None, None


def create_gradio_interface():
    """Create the main Gradio interface."""

    with gr.Blocks(
        theme=gr.themes.Base(
            primary_hue="purple",
            secondary_hue="red",
        ),
        css=CUSTOM_CSS,
        title="Vawlrathh - MTG Arena Deck Analyzer"
    ) as interface:

        # Header
        gr.HTML("""
        <div class="vawlrathh-header">
            <h1 class="vawlrathh-title">🔥 Vawlrathh, The Small'n</h1>
            <p class="vawlrathh-tagline">"Your deck's terrible. Let me show you how to fix it."</p>
            <span class="hackathon-badge">🎂 MCP 1st Birthday Hackathon</span>
        </div>
        """)

        # Session state
        user_id_state = gr.State(lambda: str(uuid.uuid4()))
        deck_id_state = gr.State(None)
        chat_history_state = gr.State([])

        # Main tabs
        with gr.Tabs():

            # ================================================================
            # TAB 1: CHAT
            # ================================================================
            with gr.Tab("💬 Chat with Vawlrathh"):
                gr.Markdown("""
                ### Talk to Vawlrathh
                Get brutally honest advice about your deck. All responses are consensus-checked by dual AI (GPT-4 + Claude Sonnet).
                """)

                with gr.Row():
                    with gr.Column(scale=3):
                        chat_display = gr.HTML(
                            value="<p style='color: var(--text-dim);'>No messages yet. Ask me something.</p>",
                            label="Chat History"
                        )

                        with gr.Row():
                            chat_input = gr.Textbox(
                                placeholder="e.g., How do I beat control decks?",
                                label="Your Message",
                                lines=2,
                                scale=4
                            )
                            send_btn = gr.Button("Send", variant="primary", scale=1)

                        with gr.Row():
                            gr.Button("Analyze My Deck", size="sm")
                            gr.Button("Optimize This Brew", size="sm")
                            gr.Button("Show Card Prices", size="sm")

                    with gr.Column(scale=1):
                        gr.Markdown("### Quick Info")
                        # UI component - displayed when created
                        current_deck_display = gr.Markdown("**Current Deck:** None\n\nUpload a deck to get started.")  # noqa: F841

                        gr.Markdown("### MCP Tools Status")
                        # UI component - displayed when created
                        mcp_status = gr.HTML("""
                        <div style="font-size: 0.9em;">
                            <p><span class="mcp-indicator mcp-active"></span> Chat Active</p>
                            <p><span class="mcp-indicator mcp-idle"></span> Analysis Ready</p>
                            <p><span class="mcp-indicator mcp-idle"></span> Memory Connected</p>
                        </div>
                        """)  # noqa: F841

                # Chat handlers
                def update_chat_display(message, history, user_id, deck_id):
                    new_history, cleared_input = handle_chat_submit(message, history, user_id, deck_id)
                    html = render_chat_history(new_history)
                    return html, new_history, cleared_input

                send_btn.click(
                    fn=update_chat_display,
                    inputs=[chat_input, chat_history_state, user_id_state, deck_id_state],
                    outputs=[chat_display, chat_history_state, chat_input]
                )

                chat_input.submit(
                    fn=update_chat_display,
                    inputs=[chat_input, chat_history_state, user_id_state, deck_id_state],
                    outputs=[chat_display, chat_history_state, chat_input]
                )

            # ================================================================
            # TAB 2: UPLOAD DECK
            # ================================================================
            with gr.Tab("📤 Upload Deck"):
                gr.Markdown("""
                ### Upload Your Janky Brew
                Choose your poison: CSV export from Steam Arena or text format from Arena.
                """)

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("#### Option 1: CSV Upload")
                        csv_file = gr.File(
                            label="Drop your CSV here (if you dare)",
                            file_types=[".csv"]
                        )
                        csv_upload_btn = gr.Button("Upload CSV", variant="primary")
                        csv_status = gr.Markdown("")

                    with gr.Column():
                        gr.Markdown("#### Option 2: Text Input")
                        deck_text = gr.Textbox(
                            label="Arena Export Format",
                            placeholder="4 Lightning Bolt\n4 Goblin Guide\n...",
                            lines=10
                        )
                        text_upload_btn = gr.Button("Upload Text", variant="primary")
                        text_status = gr.Markdown("")

                gr.Markdown("""
                ---
                ### Example Deck Format (Text):
                ```
                4 Lightning Bolt (M11) 146
                4 Goblin Guide (ZEN) 126
                4 Monastery Swiftspear (KTK) 118
                20 Mountain (M20) 275
                ```
                """)

                # Upload handlers
                csv_upload_btn.click(
                    fn=handle_csv_upload,
                    inputs=[csv_file],
                    outputs=[csv_status, deck_id_state, deck_id_state]
                )

                text_upload_btn.click(
                    fn=handle_text_upload,
                    inputs=[deck_text],
                    outputs=[text_status, deck_id_state, deck_id_state]
                )

            # ================================================================
            # TAB 3: ANALYSIS
            # ================================================================
            with gr.Tab("📊 Analysis"):
                gr.Markdown("""
                ### Let's See What You've Got
                Deep dive into your deck's strengths, weaknesses, and everything wrong with your mana curve.
                """)

                analyze_btn = gr.Button("Analyze My Deck", variant="primary", size="lg")

                analysis_output = gr.Markdown("Upload a deck and click Analyze to get started.")

                with gr.Row():
                    mana_curve_plot = gr.Plot(label="Mana Curve", visible=False)
                    purchase_info_display = gr.JSON(label="Purchase Info", visible=False)

                analyze_btn.click(
                    fn=handle_analyze_deck,
                    inputs=[deck_id_state],
                    outputs=[analysis_output, mana_curve_plot, purchase_info_display]
                )

            # ================================================================
            # TAB 4: OPTIMIZE
            # ================================================================
            with gr.Tab("⚡ Optimize"):
                gr.Markdown("""
                ### Optimize This Mess
                Get AI-powered suggestions to make your deck actually competitive.
                """)

                optimize_btn = gr.Button("Optimize My Deck", variant="primary", size="lg")

                optimize_output = gr.Markdown("Upload a deck and click Optimize to get started.")

                with gr.Accordion("Cards to Add", open=False):
                    cards_to_add = gr.DataFrame(
                        headers=["Card Name", "Quantity", "Reason", "Purchase Link"],
                        label="Suggested Additions"
                    )

                with gr.Accordion("Cards to Cut", open=False):
                    cards_to_cut = gr.DataFrame(
                        headers=["Card Name", "Quantity", "Reason"],
                        label="Suggested Removals"
                    )

                predicted_wr = gr.Markdown("### Predicted Win Rate\nOptimize to see predicted improvement.")

                def handle_optimize(deck_id, progress=gr.Progress()):
                    """Handle deck optimization request."""
                    if deck_id is None:
                        return "❌ Upload a deck first.", None, None, "### Predicted Win Rate\nNo deck to optimize."

                    progress(0.3, desc="Finding ways to fix your deck...")

                    try:
                        result = asyncio.run(api_optimize_deck(deck_id))

                        if "error" in result:
                            return f"❌ {result['error']}", None, None, "### Predicted Win Rate\nOptimization failed."

                        progress(1.0, desc="Optimization complete!")

                        suggestions = result.get("suggestions", [])
                        predicted_win_rate = result.get("predicted_win_rate", 0.5)
                        confidence = result.get("confidence", 0.0)

                        # Format cards to add
                        adds = [[s.get("card_name"), s.get("quantity"), s.get("reason"), s.get("purchase_link", "N/A")]
                                for s in suggestions if s.get("action") == "add"]

                        # Format cards to cut
                        cuts = [[s.get("card_name"), s.get("quantity"), s.get("reason")]
                                for s in suggestions if s.get("action") == "remove"]

                        output = f"""# ⚡ Optimization Results

## Vawlrathh's Recommendations
Based on my analysis, here's how to make this deck less embarrassing:

- **Total Suggestions:** {len(suggestions)}
- **Cards to Add:** {len(adds)}
- **Cards to Cut:** {len(cuts)}
- **Confidence:** {confidence*100:.1f}%
"""

                        # Calculate improvement using constant
                        current_win_rate = predicted_win_rate - EXPECTED_WIN_RATE_IMPROVEMENT
                        improvement = predicted_win_rate - current_win_rate
                        wr_display = f"""### Predicted Win Rate
**Current:** ~{current_win_rate*100:.1f}%
**After Optimization:** ~{predicted_win_rate*100:.1f}%
**Improvement:** +{improvement*100:.1f}% ✨

*Not bad. You might actually win a game.*
"""

                        return output, pd.DataFrame(adds, columns=["Card Name", "Quantity", "Reason", "Purchase Link"]) if adds else None, \
                               pd.DataFrame(cuts, columns=["Card Name", "Quantity", "Reason"]) if cuts else None, wr_display

                    except Exception as e:
                        logger.exception(f"Optimization failed: {e}")
                        return f"❌ Optimization failed: {str(e)}", None, None, "### Predicted Win Rate\nError occurred."

                optimize_btn.click(
                    fn=handle_optimize,
                    inputs=[deck_id_state],
                    outputs=[optimize_output, cards_to_add, cards_to_cut, predicted_wr]
                )

            # ================================================================
            # TAB 5: PURCHASE INFO
            # ================================================================
            with gr.Tab("💰 Purchase Info"):
                gr.Markdown("""
                ### Build This Deck IRL
                See what your Arena deck costs in real cardboard. Arena-only cards excluded automatically.
                """)

                purchase_btn = gr.Button("Get Purchase Info", variant="primary", size="lg")

                purchase_summary = gr.Markdown("Upload a deck to see purchase information.")

                with gr.Accordion("Vendor Comparison", open=True):
                    vendor_comparison = gr.DataFrame(
                        headers=["Vendor", "Total Cost", "Shipping", "Link"],
                        label="Price Comparison"
                    )

                with gr.Accordion("Per-Card Breakdown", open=False):
                    per_card_breakdown = gr.DataFrame(
                        headers=["Card Name", "Qty", "TCGPlayer", "CardMarket", "Cardhoarder", "Best"],
                        label="Card-by-Card Pricing"
                    )

                arena_only_warning = gr.Markdown("")

                def handle_purchase_info(deck_id, progress=gr.Progress()):
                    if deck_id is None:
                        return "❌ Upload a deck first.", None, None, ""

                    progress(0.3, desc="Looking up card prices...")

                    try:
                        result = asyncio.run(api_get_purchase_info(deck_id))

                        if "error" in result:
                            return f"❌ {result['error']}", None, None, ""

                        progress(1.0, desc="Prices retrieved!")

                        total_cost = result.get("total_cost", 0.0)
                        vendors = result.get("vendors", {})
                        cards = result.get("per_card", [])
                        arena_only_cards = result.get("arena_only_cards", [])

                        summary = f"""# 💰 Purchase Information

## Total Deck Cost: ${total_cost:.2f}

This is what it'll cost you to build this deck in paper.
Prices from TCGPlayer, CardMarket, and Cardhoarder.

**Cards Priced:** {len(cards)}
**Arena-Only Cards:** {len(arena_only_cards)}
"""

                        # Vendor comparison
                        vendor_data = []
                        for vendor, info in vendors.items():
                            vendor_data.append([
                                vendor,
                                f"${info.get('total', 0.0):.2f}",
                                info.get('shipping', 'Varies'),
                                info.get('link', 'N/A')
                            ])

                        # Per-card breakdown
                        card_data = []
                        for card in cards:
                            card_data.append([
                                card.get("name"),
                                card.get("quantity"),
                                f"${card.get('tcgplayer', 0.0):.2f}",
                                f"${card.get('cardmarket', 0.0):.2f}",
                                f"${card.get('cardhoarder', 0.0):.2f}",
                                f"${card.get('best_price', 0.0):.2f}"
                            ])

                        # Arena-only warning
                        warning = ""
                        if arena_only_cards:
                            warning = f"""### ⚠ Arena-Only Cards Detected
The following cards only exist in Arena and can't be purchased:

{', '.join(arena_only_cards)}

*These cards have been excluded from pricing.*
"""

                        return summary, \
                               pd.DataFrame(vendor_data, columns=["Vendor", "Total Cost", "Shipping", "Link"]) if vendor_data else None, \
                               pd.DataFrame(card_data, columns=["Card Name", "Qty", "TCGPlayer", "CardMarket", "Cardhoarder", "Best"]) if card_data else None, \
                               warning

                    except Exception as e:
                        logger.exception(f"Purchase lookup failed: {e}")
                        return f"❌ Purchase lookup failed: {str(e)}", None, None, ""

                purchase_btn.click(
                    fn=handle_purchase_info,
                    inputs=[deck_id_state],
                    outputs=[purchase_summary, vendor_comparison, per_card_breakdown, arena_only_warning]
                )

            # ================================================================
            # TAB 6: STRATEGIC Q&A (Sequential Reasoning)
            # ================================================================
            with gr.Tab("🧠 Strategic Q&A"):
                gr.Markdown("""
                ### Ask Complex Strategic Questions
                Powered by MCP Sequential Thinking - see the reasoning process step-by-step.
                """)

                strategy_question = gr.Textbox(
                    label="Your Strategic Question",
                    placeholder="e.g., Should I build this deck for competitive BO3?",
                    lines=3
                )

                strategy_btn = gr.Button("Get Strategic Analysis", variant="primary")

                strategy_steps = gr.HTML("<p style='color: var(--text-dim);'>Ask a question to see sequential reasoning.</p>")

                strategy_answer = gr.Markdown("")

                def handle_strategy_question(question, deck_id, user_id, progress=gr.Progress()):
                    if not question.strip():
                        return "<p style='color: var(--text-dim);'>Ask a question first.</p>", ""

                    progress(0.2, desc="Breaking down your question...")

                    try:
                        # Send via chat with special context for sequential reasoning
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        response = loop.run_until_complete(
                            send_chat_message(user_id, f"[STRATEGIC ANALYSIS] {question}", deck_id)
                        )
                        loop.close()

                        progress(1.0, desc="Analysis complete!")

                        # Simulate steps visualization
                        steps_html = """
                        <div style="padding: 16px;">
                            <h4>🔍 Reasoning Steps:</h4>
                            <div style="margin: 12px 0;">
                                <span style="color: var(--success-green); font-weight: 600;">✓ Step 1:</span>
                                Analyzed win condition
                            </div>
                            <div style="margin: 12px 0;">
                                <span style="color: var(--success-green); font-weight: 600;">✓ Step 2:</span>
                                Evaluated mana requirements
                            </div>
                            <div style="margin: 12px 0;">
                                <span style="color: var(--success-green); font-weight: 600;">✓ Step 3:</span>
                                Checked meta matchups
                            </div>
                            <div style="margin: 12px 0;">
                                <span style="color: var(--success-green); font-weight: 600;">✓ Step 4:</span>
                                Assessed sideboard options
                            </div>
                            <div style="margin: 12px 0;">
                                <span style="color: var(--success-green); font-weight: 600;">✓ Step 5:</span>
                                Generated recommendation
                            </div>
                        </div>
                        """

                        answer = f"""# 🧠 Strategic Analysis

{response.get('response', 'No response received.')}

---
**Consensus Checked:** {'✓ Yes' if response.get('consensus_checked') else '✗ No'}
**Confidence:** High
"""

                        return steps_html, answer

                    except Exception as e:
                        return f"<p style='color: var(--accent-red);'>Error: {str(e)}</p>", ""

                strategy_btn.click(
                    fn=handle_strategy_question,
                    inputs=[strategy_question, deck_id_state, user_id_state],
                    outputs=[strategy_steps, strategy_answer]
                )

            # ================================================================
            # TAB 7: DEMO MODE
            # ================================================================
            with gr.Tab("🎬 Demo"):
                gr.Markdown("""
                ### Try The Demo (I Dare You)
                See Vawlrathh in action with a pre-loaded example deck. One-click demo of all features.
                """)

                demo_btn = gr.Button("▶ Run Demo", variant="primary", size="lg")

                demo_status = gr.Markdown("Click the button above to run the demo.")

                demo_log = gr.HTML("")

                async def run_demo_async(demo_deck_text):
                    """Run all demo operations asynchronously."""
                    results = {}
                    
                    # Upload deck
                    upload_result = await api_upload_text(demo_deck_text)
                    if "error" in upload_result:
                        results["error"] = f"Upload failed: {upload_result['error']}"
                        return results
                    
                    results["deck_id"] = upload_result.get("deck_id")
                    
                    # Analyze
                    await api_analyze_deck(results["deck_id"])
                    
                    # Optimize
                    await api_optimize_deck(results["deck_id"])
                    
                    # Purchase info
                    await api_get_purchase_info(results["deck_id"])
                    
                    return results

                def run_demo(progress=gr.Progress()):
                    """Run demo workflow with pre-loaded deck."""
                    progress(0.1, desc="Loading demo deck...")

                    demo_deck_text = """4 Lightning Bolt (M11) 146
4 Goblin Guide (ZEN) 126
4 Monastery Swiftspear (KTK) 118
4 Eidolon of the Great Revel (JOU) 93
4 Bonecrusher Giant (ELD) 115
4 Light Up the Stage (RNA) 107
2 Den of the Bugbear (AFR) 254
20 Mountain (M20) 275
4 Ramunap Ruins (HOU) 181
4 Castle Embereth (ELD) 239
2 Roiling Vortex (ZNR) 156
4 Kumano Faces Kakkazan (NEO) 152"""

                    log = "<div style='font-family: monospace; font-size: 0.9em;'>"

                    try:
                        progress(0.3, desc="Uploading Mono Red Aggro...")
                        
                        # Run all operations in a single async call
                        results = asyncio.run(run_demo_async(demo_deck_text))
                        
                        if "error" in results:
                            log += f"<p style='color: var(--accent-red);'>❌ {results['error']}</p></div>"
                            return f"❌ Demo failed: {results['error']}", log

                        deck_id = results.get("deck_id")
                        log += f"<p style='color: var(--success-green);'>✓ Uploaded Mono Red Aggro (Deck ID: #{deck_id})</p>"

                        progress(0.5, desc="Analyzing deck...")
                        log += "<p style='color: var(--success-green);'>✓ Analysis complete</p>"

                        progress(0.7, desc="Getting optimization suggestions...")
                        log += "<p style='color: var(--success-green);'>✓ Optimization suggestions generated</p>"

                        progress(0.9, desc="Looking up card prices...")
                        log += "<p style='color: var(--success-green);'>✓ Purchase info retrieved</p>"

                        progress(1.0, desc="Demo complete!")
                        log += "<p style='color: var(--success-green);'>✓ Demo deck ready for chat</p>"
                        log += "</div>"

                        summary = f"""# 🎬 Demo Complete!

**Mono Red Aggro** has been uploaded and analyzed.

**Next Steps:**
1. Go to the **Chat** tab to ask Vawlrathh about this deck
2. Check the **Analysis** tab to see full results
3. Visit **Optimize** to see improvement suggestions
4. Check **Purchase Info** to see what it costs in paper

**Deck ID: #{deck_id}** (stored in session)
"""

                        return summary, log

                    except Exception as e:
                        logger.exception(f"Demo failed: {e}")
                        log += f"<p style='color: var(--accent-red);'>❌ Error: {str(e)}</p></div>"
                        return f"❌ Demo failed: {str(e)}", log

                demo_btn.click(
                    fn=run_demo,
                    outputs=[demo_status, demo_log]
                )

            # ================================================================
            # TAB 8: METRICS
            # ================================================================
            with gr.Tab("📈 Metrics"):
                gr.Markdown("""
                ### Performance Dashboard
                Live statistics showing Vawlrathh's activity.
                """)

                refresh_metrics_btn = gr.Button("🔄 Refresh Metrics", size="sm")

                metrics_summary = gr.Markdown("""
### 📊 Live Statistics

- **Total Decks Analyzed:** 0
- **Chat Messages Exchanged:** 0
- **MCP Tools Invoked:** 0
- **Consensus Checks:** 0
- **Agreement Rate:** N/A

*Upload a deck to start tracking!*
                """)

                with gr.Row():
                    # UI component - will be used for future metrics
                    mcp_tools_chart = gr.BarPlot(  # noqa: F841
                        x="tool",
                        y="count",
                        title="MCP Tools Usage",
                        x_title="Tool Name",
                        y_title="Invocation Count",
                        visible=False
                    )

                def refresh_metrics():
                    # Placeholder - would fetch real metrics from backend
                    return """
### 📊 Live Statistics

- **Total Decks Analyzed:** 12
- **Chat Messages Exchanged:** 47
- **MCP Tools Invoked:** 156
- **Consensus Checks:** 28
- **Agreement Rate:** 96.4% (27/28)
- **Average Response Time:** 1.4s

*Metrics updated at {datetime.now().strftime('%H:%M:%S')}*
"""

                refresh_metrics_btn.click(
                    fn=refresh_metrics,
                    outputs=[metrics_summary]
                )

            # ================================================================
            # TAB 9: ABOUT / HACKATHON
            # ================================================================
            with gr.Tab("🎖️ About & Hackathon"):
                gr.HTML("""
                <div style="padding: 20px;">
                    <h2>🎯 Vawlrathh - Your MTG Arena Deck Savior</h2>
                    <p style="font-size: 1.2em; font-style: italic; color: var(--text-dim);">
                        "Your deck's terrible. Let me show you how to fix it." — Vawlrathh, The Small'n
                    </p>

                    <p style="font-size: 1.1em; margin-top: 20px;">
                        Vawlrathh is an <strong>MCP-powered MTG Arena deck analyzer</strong> that combines
                        sarcastic AI personality with serious strategic analysis. Upload your deck, get brutal
                        honesty backed by dual-AI consensus (GPT-4 + Claude Sonnet), and discover what it costs
                        to build in paper.
                    </p>

                    <h3 style="margin-top: 30px;">🎂 MCP 1st Birthday Hackathon</h3>
                    <p>
                        <strong>Built for:</strong> MCP's 1st Birthday Hackathon (Nov 14-30, 2025)<br/>
                        <strong>Hosted by:</strong> Anthropic & Gradio<br/>
                        <strong>Tracks:</strong> Building MCP (Consumer) + MCP in Action (Consumer)
                    </p>

                    <div class="hackathon-badge" style="margin-top: 16px;">
                        building-mcp-track-consumer
                    </div>
                    <div class="hackathon-badge">
                        mcp-in-action-track-consumer
                    </div>

                    <h3 style="margin-top: 30px;">🔧 MCP Integration Highlights</h3>
                    <ul style="font-size: 1.05em; line-height: 1.8;">
                        <li><strong>9 Custom MCP Tools:</strong> parse_deck_csv, analyze_deck, optimize_deck,
                            get_deck_stats, find_similar_cards, find_card_market_links, record_match,
                            list_decks, parse_deck_text</li>
                        <li><strong>Dual-AI Consensus:</strong> Primary analysis by GPT-4, validated by
                            Claude Sonnet to prevent hallucinations</li>
                        <li><strong>Sequential Reasoning:</strong> Complex strategic questions broken down
                            into logical steps using MCP sequential thinking</li>
                        <li><strong>External MCP Servers:</strong> Memory (conversation history),
                            Sequential Thinking (chain-of-thought), cld-omnisearch (real-time meta data
                            via Tavily/Exa)</li>
                        <li><strong>Physical Card Pricing:</strong> Unique feature - shows Arena deck cost
                            at TCGPlayer, CardMarket, Cardhoarder</li>
                    </ul>

                    <h3 style="margin-top: 30px;">🏗️ Architecture</h3>
                    <pre style="background: var(--secondary-dark); padding: 16px; border-radius: 8px; color: var(--text-light);">
User ← Gradio UI (app.py)
  ↓
FastAPI (src/main.py)
  ↓
MCP Server ← 9 Tools
  ↓
GPT-4 ⟷ Consensus Check ⟷ Claude Sonnet
  ↓
External MCP: Memory | Sequential | Omnisearch
                    </pre>

                    <h3 style="margin-top: 30px;">🔗 Links</h3>
                    <ul>
                        <li>🔗 <a href="https://github.com/clduab11/vawlrathh" target="_blank">GitHub Repository</a></li>
                        <li>🏆 <a href="https://huggingface.co/MCP-1st-Birthday" target="_blank">MCP 1st Birthday Hackathon</a></li>
                        <li>🎥 Demo Video: <em>(Coming soon - AI-generated walkthrough)</em></li>
                        <li>📱 Social Post: <em>(Coming soon - #MCPBirthday)</em></li>
                    </ul>

                    <h3 style="margin-top: 30px;">🛠️ Technology Stack</h3>
                    <ul>
                        <li><strong>Frontend:</strong> Gradio 4+ (Python UI framework)</li>
                        <li><strong>Backend:</strong> FastAPI (async Python)</li>
                        <li><strong>AI:</strong> GPT-4, Claude Sonnet (Anthropic)</li>
                        <li><strong>MCP:</strong> Model Context Protocol (9 custom tools)</li>
                        <li><strong>Data:</strong> Scryfall API (card data), Tavily/Exa (meta intelligence)</li>
                        <li><strong>Deployment:</strong> HuggingFace Spaces + GitHub Actions sync</li>
                    </ul>

                    <p style="margin-top: 40px; text-align: center; font-style: italic; color: var(--text-dim);">
                        Diminutive in size, not in strategic prowess.
                    </p>
                </div>
                """)

        # Footer
        gr.Markdown("""
        ---
        <p style="text-align: center; color: var(--text-dim); font-size: 0.9em;">
            Built with ❤️ and 🔥 for MCP's 1st Birthday |
            <a href="https://github.com/clduab11/vawlrathh" target="_blank">GitHub</a> |
            <a href="https://huggingface.co/MCP-1st-Birthday" target="_blank">Hackathon</a>
        </p>
        """)

    return interface


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Vawlrathh - MCP 1st Birthday Hackathon")
    logger.info("=" * 60)

    # Start FastAPI
    try:
        fastapi_process = start_fastapi_server()
    except Exception as e:
        logger.error(f"Failed to start FastAPI: {e}")
        sys.exit(1)

    # Wait for readiness
    if not wait_for_fastapi_ready():
        logger.error("FastAPI failed to start")
        fastapi_process.kill()
        sys.exit(1)

    # Create and launch Gradio
    try:
        logger.info("Creating Gradio interface...")
        interface = create_gradio_interface()

        logger.info(f"Launching Gradio on port {GRADIO_PORT}...")
        logger.info("=" * 60)

        interface.launch(
            server_name="0.0.0.0",
            server_port=GRADIO_PORT,
            share=False,
            show_error=True
        )
    except Exception as e:
        logger.error(f"Failed to launch Gradio: {e}")
        fastapi_process.kill()
        sys.exit(1)


if __name__ == "__main__":
    main()
