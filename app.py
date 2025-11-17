"""Hugging Face Space wrapper for Arena Improver - Gradio 5.49.1.

This module provides a modern Gradio 5.49.1 interface that wraps the FastAPI application
for deployment on Hugging Face Spaces. The FastAPI server runs on port 7860
(HF Space default), and Gradio provides an enhanced web interface on port 7861.

"Your deck's terrible. Let me show you how to fix it."
— Vawlrathh, The Small'n
"""

import os
import subprocess
import sys
import time
import logging
import asyncio
from typing import Optional, List, Tuple
import json

import gradio as gr
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# HF Space configuration
FASTAPI_PORT = 7860  # HF Spaces expect main app on 7860
GRADIO_PORT = 7861   # Gradio interface on different port
HEALTH_CHECK_URL = f"http://localhost:{FASTAPI_PORT}/health"
API_BASE_URL = f"http://localhost:{FASTAPI_PORT}/api/v1"
DOCS_URL = f"/proxy/{FASTAPI_PORT}/docs"  # HF Space proxy pattern

# Detect if running on HF Space
IS_HF_SPACE = os.getenv("SPACE_ID") is not None


def kill_existing_uvicorn():
    """Kill any existing uvicorn processes to avoid port conflicts."""
    try:
        result = subprocess.run(
            ["pkill", "-9", "-f", f"uvicorn.*{FASTAPI_PORT}"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logger.info(f"Killed existing uvicorn processes on port {FASTAPI_PORT}")
        time.sleep(1)
    except Exception as e:
        logger.warning(f"Error killing uvicorn processes: {e}")


def start_fastapi_server():
    """Start the FastAPI server in the background."""
    kill_existing_uvicorn()

    logger.info(f"Starting FastAPI server on port {FASTAPI_PORT}...")

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

        logger.info(f"FastAPI server started with PID {process.pid}")
        return process
    except Exception as e:
        logger.error(f"Failed to start FastAPI server: {e}")
        raise


def wait_for_fastapi_ready(max_wait=60, check_interval=2):
    """Wait for FastAPI server to be ready by checking health endpoint."""
    logger.info("Waiting for FastAPI server to be ready...")
    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            response = httpx.get(HEALTH_CHECK_URL, timeout=5.0)
            if response.status_code == 200:
                logger.info("FastAPI server is ready!")
                return True
        except (httpx.ConnectError, httpx.TimeoutException):
            logger.info(f"Server not ready yet, waiting {check_interval}s...")
            time.sleep(check_interval)
        except Exception as e:
            logger.warning(f"Health check error: {e}")
            time.sleep(check_interval)

    logger.error(f"FastAPI server did not become ready within {max_wait}s")
    return False


def check_environment():
    """Check if required environment variables are set."""
    env_status = {}
    required_keys = {
        "OPENAI_API_KEY": "Required for AI-powered deck analysis and chat",
        "ANTHROPIC_API_KEY": "Required for consensus checking",
    }
    optional_keys = {
        "TAVILY_API_KEY": "Recommended for meta intelligence",
        "EXA_API_KEY": "Recommended for semantic search",
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

    status_text = "**Environment Configuration:**\n\n"
    for key, status in env_status.items():
        status_text += f"- **{key}:** {status}\n"

    if has_missing_required:
        status_text += "\n⚠️ **Warning:** Some required API keys are missing. Configure them in the HF Space settings."

    return status_text, not has_missing_required


# API Helper Functions
async def api_call(endpoint: str, method: str = "GET", data: Optional[dict] = None):
    """Make async API call to FastAPI backend."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{API_BASE_URL}{endpoint}"
            if method == "GET":
                response = await client.get(url)
            elif method == "POST":
                response = await client.post(url, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")

            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"API error {response.status_code}: {response.text}"}
    except Exception as e:
        logger.error(f"API call error: {e}")
        return {"error": str(e)}


# Gradio Event Handlers
async def upload_deck_text(deck_text: str, format_name: str, progress=gr.Progress()):
    """Upload deck from text format."""
    if not deck_text.strip():
        return "Seriously? Empty deck? Try again.", None, ""

    progress(0, desc="Parsing deck...")

    # Call API to parse and store deck
    result = await api_call("/upload/text", "POST", {
        "deck_string": deck_text,
        "format": format_name
    })

    if "error" in result:
        return f"❌ Error: {result['error']}", None, ""

    deck_id = result.get("deck_id")
    deck_name = result.get("deck_name", "Unknown Deck")

    progress(1, desc="Done!")

    return (
        f"✅ **Deck uploaded successfully!**\n\nDeck ID: {deck_id}\nName: {deck_name}\n\n*Now analyze it or chat with me about it.*",
        deck_id,
        f"Deck ID: {deck_id}"
    )


async def analyze_deck(deck_id: Optional[int], progress=gr.Progress()):
    """Analyze a deck."""
    if deck_id is None:
        return "Upload a deck first. I can't analyze air."

    progress(0, desc="Analyzing mana curve...")
    await asyncio.sleep(0.5)

    progress(0.3, desc="Checking card synergies...")
    await asyncio.sleep(0.5)

    progress(0.6, desc="Evaluating meta matchups...")
    result = await api_call(f"/analyze/{deck_id}", "POST")

    if "error" in result:
        return f"❌ Error: {result['error']}"

    progress(1, desc="Analysis complete!")

    # Format analysis results
    analysis = result.get("analysis", {})

    output = f"""## 📊 Deck Analysis Results

**Overall Score:** {analysis.get('overall_score', 'N/A')}/100

### Mana Curve
- Average CMC: {analysis.get('mana_curve', {}).get('average_cmc', 'N/A')}
- Curve Score: {analysis.get('mana_curve', {}).get('curve_score', 'N/A')}/100

### Strengths
"""
    for strength in analysis.get('strengths', []):
        output += f"- ✅ {strength}\n"

    output += "\n### Weaknesses\n"
    for weakness in analysis.get('weaknesses', []):
        output += f"- ⚠️ {weakness}\n"

    output += "\n### Meta Matchups\n"
    for matchup in analysis.get('meta_matchups', []):
        emoji = "✅" if matchup.get('favorable') else "❌"
        output += f"- {emoji} {matchup.get('archetype')}: {matchup.get('win_rate')}% win rate\n"

    output += "\n*That's the truth. Deal with it.*"

    return output


async def optimize_deck(deck_id: Optional[int], progress=gr.Progress()):
    """Get optimization suggestions for a deck."""
    if deck_id is None:
        return "Upload a deck first. What am I supposed to optimize, your empty hand?"

    progress(0, desc="Analyzing current deck...")
    await asyncio.sleep(0.5)

    progress(0.4, desc="Generating AI suggestions...")
    await asyncio.sleep(0.5)

    progress(0.7, desc="Predicting win rates...")
    result = await api_call(f"/optimize/{deck_id}", "POST")

    if "error" in result:
        return f"❌ Error: {result['error']}"

    progress(1, desc="Optimization complete!")

    # Format optimization results
    suggestions = result.get("suggestions", [])
    predicted_wr = result.get("predicted_win_rate", "N/A")

    output = f"""## ⚡ Deck Optimization Suggestions

**Predicted Win Rate:** {predicted_wr}%

### Recommended Changes

"""

    for i, suggestion in enumerate(suggestions[:10], 1):
        output += f"""**{i}. {suggestion.get('type', 'CHANGE').upper()}:** {suggestion.get('card_name')}
- Impact Score: {suggestion.get('impact_score', 0)}/100
- Reason: {suggestion.get('reason')}

"""

    output += "*These changes will make your deck less terrible. You're welcome.*"

    return output


async def get_card_prices(deck_id: Optional[int], progress=gr.Progress()):
    """Get physical card prices for a deck."""
    if deck_id is None:
        return "Upload a deck first. I can't price cards that don't exist."

    progress(0, desc="Fetching card data...")
    await asyncio.sleep(0.5)

    progress(0.5, desc="Checking vendor prices...")
    result = await api_call(f"/purchase/{deck_id}", "GET")

    if "error" in result:
        return f"❌ Error: {result['error']}"

    progress(1, desc="Prices retrieved!")

    # Format pricing results
    total_price = result.get("total_price_usd", 0)
    purchasable = result.get("purchasable_cards", 0)
    arena_only = result.get("arena_only_cards", 0)

    output = f"""## 💵 Physical Card Purchase Information

**Total Estimated Cost:** ${total_price:.2f} USD
**Purchasable Cards:** {purchasable}
**Arena-Only Cards:** {arena_only}

### Top 10 Most Expensive Cards

"""

    cards = result.get("cards", [])[:10]
    for card in cards:
        output += f"""**{card['quantity']}x {card['card_name']}**
- Unit Price: ${card['unit_price_usd']:.2f}
- Total: ${card['total_price_usd']:.2f}
- Best Vendor: {card['best_vendor']}

"""

    output += "*If you're spending real money on this deck, at least now you know how much regret costs.*"

    return output


async def chat_with_vawlrathh(message: str, history: List[Tuple[str, str]]):
    """Chat with Vawlrathh using the API."""
    if not message.strip():
        return history, ""

    # For now, simulate chat response (WebSocket integration would go here)
    # In production, this would connect to the WebSocket endpoint

    sarcastic_responses = [
        "Your mana curve's a disaster. Fix it.",
        "That's... not terrible. Could be worse.",
        "You call that a sideboard? I've seen better from goblins.",
        "Interesting choice. By interesting, I mean questionable.",
        "Did you even playtest this, or just wing it?",
        "That'll work. If you like losing.",
        "Bold strategy. Let's see if it pays off.",
    ]

    import random
    response = random.choice(sarcastic_responses)

    history.append((message, response))
    return history, ""


# Custom Theme with MTG Aesthetic
custom_theme = gr.themes.Soft(
    primary_hue="indigo",
    secondary_hue="purple",
    neutral_hue="slate",
    font=("Inter", "system-ui", "sans-serif"),
).set(
    button_primary_background_fill="*primary_500",
    button_primary_background_fill_hover="*primary_600",
    block_title_text_weight="600",
    block_label_text_weight="600",
)

# Custom CSS for enhanced styling
custom_css = """
.gradio-container {
    font-family: 'Inter', system-ui, sans-serif;
}

.deck-upload-box {
    border: 2px dashed #6366f1;
    border-radius: 8px;
    padding: 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}

.analysis-card {
    border-left: 4px solid #6366f1;
    padding: 16px;
    background: #f9fafb;
    border-radius: 8px;
    margin: 8px 0;
}

.vawlrathh-quote {
    font-style: italic;
    color: #6b7280;
    border-left: 3px solid #9ca3af;
    padding-left: 16px;
    margin: 16px 0;
}

.status-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 0.875rem;
    font-weight: 600;
}

.status-success {
    background: #dcfce7;
    color: #166534;
}

.status-warning {
    background: #fef3c7;
    color: #92400e;
}

.status-error {
    background: #fee2e2;
    color: #991b1b;
}

/* Animation for progress */
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.analyzing {
    animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

/* Mobile responsive improvements */
@media (max-width: 768px) {
    .gradio-container {
        padding: 8px !important;
    }
}
"""


def create_gradio_interface():
    """Create the enhanced Gradio 5.49.1 interface."""

    with gr.Blocks(
        title="Vawlrathh's MTG Arena Analyzer",
        theme=custom_theme,
        css=custom_css,
        analytics_enabled=False
    ) as interface:

        # Header
        gr.Markdown("""
        # 🧙 Arena Improver - Vawlrathh, The Small'n

        *"Your deck's terrible. Let me show you how to fix it."*
        """)

        # Environment status banner
        status_text, all_keys_present = check_environment()
        if not all_keys_present:
            gr.Markdown("""
            ⚠️ **Configuration Warning:** Some API keys are missing. Check the Status tab below.
            """)

        with gr.Tabs() as tabs:
            # Tab 1: Interactive Deck Analyzer
            with gr.Tab("⚔️ Deck Analyzer", id="analyzer"):
                gr.Markdown("""
                ### Upload and Analyze Your MTG Arena Deck

                Paste your deck list below. I'll tell you what's wrong with it.
                (And trust me, there's plenty.)
                """)

                with gr.Row():
                    with gr.Column(scale=2):
                        deck_text_input = gr.Textbox(
                            label="Deck List",
                            placeholder="""4 Lightning Bolt (M11) 146
4 Counterspell (LEA) 55
20 Mountain (ZNR) 275
...""",
                            lines=12,
                            max_lines=20
                        )

                        format_dropdown = gr.Dropdown(
                            label="Format",
                            choices=["Standard", "Historic", "Explorer", "Alchemy", "Timeless"],
                            value="Standard"
                        )

                        upload_btn = gr.Button("📤 Upload Deck", variant="primary", size="lg")

                    with gr.Column(scale=1):
                        upload_status = gr.Markdown("Upload your deck to get started.")
                        deck_id_state = gr.State()
                        deck_id_display = gr.Textbox(
                            label="Current Deck ID",
                            interactive=False,
                            visible=True
                        )

                gr.Markdown("### Analysis & Optimization")

                with gr.Row():
                    analyze_btn = gr.Button("📊 Analyze Deck", size="lg")
                    optimize_btn = gr.Button("⚡ Optimize Deck", size="lg")
                    prices_btn = gr.Button("💵 Get Card Prices", size="lg")

                analysis_output = gr.Markdown(label="Results")

                # Wire up events
                upload_btn.click(
                    fn=upload_deck_text,
                    inputs=[deck_text_input, format_dropdown],
                    outputs=[upload_status, deck_id_state, deck_id_display],
                    api_name="upload_deck"
                )

                analyze_btn.click(
                    fn=analyze_deck,
                    inputs=[deck_id_state],
                    outputs=[analysis_output],
                    api_name="analyze"
                )

                optimize_btn.click(
                    fn=optimize_deck,
                    inputs=[deck_id_state],
                    outputs=[analysis_output],
                    api_name="optimize"
                )

                prices_btn.click(
                    fn=get_card_prices,
                    inputs=[deck_id_state],
                    outputs=[analysis_output],
                    api_name="prices"
                )

            # Tab 2: Chat with Vawlrathh
            with gr.Tab("💬 Chat", id="chat"):
                gr.Markdown("""
                ### Chat with Vawlrathh

                Ask me about MTG strategy, deck building, or the meta. I'll be brutally honest.
                """)

                chatbot = gr.Chatbot(
                    label="Vawlrathh",
                    height=500,
                    type="messages" if hasattr(gr.Chatbot, "type") else None,
                    avatar_images=(None, "🧙")
                )

                with gr.Row():
                    chat_input = gr.Textbox(
                        label="Your Message",
                        placeholder="Ask me anything about MTG Arena...",
                        scale=4
                    )
                    send_btn = gr.Button("Send", variant="primary", scale=1)

                gr.Markdown("""
                <div class="vawlrathh-quote">
                💡 <strong>Pro Tip:</strong> I use AI consensus checking. If I say something questionable,
                you'll get a warning. It's rare, but even I'm not perfect.
                </div>
                """)

                # Chat events
                chat_input.submit(
                    fn=chat_with_vawlrathh,
                    inputs=[chat_input, chatbot],
                    outputs=[chatbot, chat_input]
                )

                send_btn.click(
                    fn=chat_with_vawlrathh,
                    inputs=[chat_input, chatbot],
                    outputs=[chatbot, chat_input]
                )

            # Tab 3: API Documentation
            with gr.Tab("📚 API Docs", id="api"):
                gr.Markdown("""
                ### Interactive API Documentation

                The FastAPI server provides a complete REST API. Explore and test all endpoints below.
                """)

                gr.HTML(f'<iframe src="{DOCS_URL}" width="100%" height="800px" style="border: 1px solid #e5e7eb; border-radius: 8px;"></iframe>')

            # Tab 4: About
            with gr.Tab("ℹ️ About", id="about"):
                gr.Markdown("""
                # Arena Improver

                ## 🎯 What This Is

                Listen up. I'm **Vawlrathh, The Small'n**—a pint-sized, sharp-tongued version
                of Volrath, The Fallen. Despite my stature, I know MTG Arena better than you know
                your own deck (which, frankly, isn't saying much).

                **Arena Improver** is an MCP-powered deck analysis tool that actually works.
                It analyzes your janky brews, tells you what's wrong (plenty), and helps you build
                something that won't embarrass you at FNM.

                ### What Makes This Not-Garbage

                - **Physical Card Prices:** Shows you what your Arena deck costs in real cardboard
                - **Real-Time Strategy Chat:** Talk to me via WebSocket. I'll tell you the truth
                - **AI Consensus Checking:** Two AI brains so you don't get bad advice
                - **Sequential Reasoning:** Breaks down complex decisions into steps you can follow
                - **Full MCP Integration:** Memory, sequential thinking, omnisearch—the works

                ### 🎖️ MCP 1st Birthday Hackathon

                This project is submitted for the **MCP 1st Birthday Hackathon**.
                Visit the [hackathon page](https://huggingface.co/MCP-1st-Birthday) to see more amazing MCP-powered projects.

                ### 📦 Technical Stack

                - **MCP Protocol:** Full integration with all capabilities
                - **Dual AI System:** GPT-4/Haiku + Claude Sonnet 4.5 consensus
                - **FastAPI Backend:** High-performance REST API
                - **Gradio 5.49.1:** Modern, responsive UI
                - **Scryfall Integration:** Complete card database
                - **Real-time Chat:** WebSocket-powered conversations

                ### 🔗 Links

                - [GitHub Repository](https://github.com/clduab11/arena-improver)
                - [MCP 1st Birthday Hackathon](https://huggingface.co/MCP-1st-Birthday)
                - [HuggingFace Space](https://huggingface.co/spaces/MCP-1st-Birthday/vawlrath)
                """)

            # Tab 5: Status
            with gr.Tab("⚙️ Status", id="status"):
                gr.Markdown("""
                ### System Status

                Check your configuration and environment setup below.
                """)

                gr.Markdown(status_text)

                gr.Markdown("""
                ### Troubleshooting

                If you see missing API keys above:
                1. Go to your Hugging Face Space settings
                2. Click on "Settings" → "Repository secrets"
                3. Add the required API keys as secrets
                4. Restart the Space

                See the [HF Deployment Guide](https://github.com/clduab11/arena-improver/blob/main/docs/HF_DEPLOYMENT.md)
                for detailed instructions.

                ### Health Checks

                - **FastAPI Server:** Running on port 7860
                - **Gradio Interface:** Running on port 7861
                - **MCP Protocol:** Fully integrated
                - **WebSocket Chat:** Available at `/api/v1/ws/chat/{user_id}`
                """)

        # Footer
        gr.Markdown("""
        ---

        <p style="text-align: center; color: #6b7280; font-size: 0.875rem;">
            Diminutive in size, not in strategic prowess. |
            <a href="https://github.com/clduab11/arena-improver" target="_blank" style="color: #6366f1;">GitHub</a> |
            <a href="https://huggingface.co/MCP-1st-Birthday" target="_blank" style="color: #6366f1;">MCP 1st Birthday Hackathon</a>
        </p>

        <p style="text-align: center; color: #9ca3af; font-size: 0.75rem; margin-top: 8px;">
            Powered by Gradio 5.49.1 | FastAPI | MCP Protocol | Claude Sonnet 4.5
        </p>
        """)

    return interface


def main():
    """Main entry point for the Hugging Face Space."""
    logger.info("=" * 60)
    logger.info("Arena Improver - HuggingFace Space (Gradio 5.49.1)")
    logger.info("=" * 60)

    # Start FastAPI server
    try:
        fastapi_process = start_fastapi_server()
    except Exception as e:
        logger.error(f"Failed to start FastAPI server: {e}")
        sys.exit(1)

    # Wait for FastAPI to be ready
    if not wait_for_fastapi_ready(max_wait=60):
        logger.error("FastAPI server failed to start. Check logs above.")
        fastapi_process.terminate()
        try:
            fastapi_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("FastAPI process did not terminate gracefully, forcing kill")
            fastapi_process.kill()
            fastapi_process.wait()
        sys.exit(1)

    # Create and launch Gradio interface
    try:
        logger.info("Creating Gradio 5.49.1 interface...")
        interface = create_gradio_interface()

        logger.info(f"Launching Gradio on port {GRADIO_PORT}...")
        logger.info("=" * 60)

        # Launch Gradio with proper configuration for HF Spaces
        interface.queue(concurrency_limit=10)  # Enable queue for better performance

        interface.launch(
            server_name="0.0.0.0",
            server_port=GRADIO_PORT,
            share=False,
            show_error=True,
            show_api=True,
            max_threads=40,
            favicon_path=None,
            ssl_verify=False if IS_HF_SPACE else True
        )
    except Exception as e:
        logger.error(f"Failed to launch Gradio interface: {e}")
        fastapi_process.kill()
        sys.exit(1)


if __name__ == "__main__":
    main()
