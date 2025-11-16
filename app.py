"""Hugging Face Space wrapper for Arena Improver.

This module provides a Gradio interface that wraps the FastAPI application
for deployment on Hugging Face Spaces. The FastAPI server runs on port 7860
(HF Space default), and Gradio provides a web interface on port 7861.

"Your deck's terrible. Let me show you how to fix it."
— Vawlrathh, The Small'n
"""

# pylint: disable=no-member

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
import logging
import textwrap
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import gradio as gr
import httpx
import websockets
import plotly.graph_objects as go
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# HF Space configuration
FASTAPI_PORT = 7860  # HF Spaces expect main app on 7860
GRADIO_PORT = 7861   # Gradio interface on different port
HEALTH_CHECK_URL = f"http://localhost:{FASTAPI_PORT}/health"
DOCS_URL = f"/proxy/{FASTAPI_PORT}/docs"  # HF Space proxy pattern
REPO_URL = "https://github.com/clduab11/arena-improver"
HACKATHON_URL = "https://huggingface.co/MCP-1st-Birthday"
HF_DEPLOYMENT_GUIDE_URL = (
    f"{REPO_URL}/blob/main/docs/HF_DEPLOYMENT.md"
)
API_BASE_URL = os.getenv(
    "FASTAPI_BASE_URL",
    f"http://localhost:{FASTAPI_PORT}",
)
WS_BASE_URL = os.getenv(
    "FASTAPI_WS_URL",
    f"ws://localhost:{FASTAPI_PORT}",
)


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


def _upload_csv_to_api(file_path: Optional[str]) -> Dict[str, Any]:
    """Upload a CSV file to the FastAPI backend with defensive logging."""

    if not file_path:
        return {"status": "error", "message": "No CSV file selected"}

    try:
        with open(file_path, "rb") as file_handle:
            files = {
                "file": (os.path.basename(file_path), file_handle, "text/csv"),
            }
            response = httpx.post(
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
            "message": (
                "Backend rejected CSV upload "
                f"({status_code})"
            ),
        }
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unexpected CSV upload failure")
        return {"status": "error", "message": str(exc)}


def _upload_text_to_api(deck_text: str, fmt: str) -> Dict[str, Any]:
    """Upload Arena text export to the FastAPI backend."""

    if not deck_text or not deck_text.strip():
        return {"status": "error", "message": "Deck text is empty"}

    payload = {"deck_string": deck_text, "format": fmt}
    try:
        response = httpx.post(
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
            "message": (
                "Backend rejected text upload "
                f"({status_code})"
            ),
        }
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Unexpected text upload failure")
        return {"status": "error", "message": str(exc)}


def _fetch_meta_snapshot(game_format: str) -> Dict[str, Any]:
    """Fetch meta intelligence for a specific format."""

    try:
        response = httpx.get(
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


def _fetch_memory_summary(deck_id: Optional[float]) -> Dict[str, Any]:
    """Fetch Smart Memory stats for the supplied deck id."""

    if not deck_id:
        return {"status": "error", "message": "Deck ID required"}

    try:
        response = httpx.get(
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


def _analyze_deck(deck_id: Optional[int]) -> Dict[str, Any]:
    """Analyze a deck and return comprehensive results."""
    if not deck_id:
        return {"status": "error", "message": "Deck ID required"}

    try:
        response = httpx.post(
            f"{API_BASE_URL}/api/v1/analyze/{deck_id}",
            params={"include_purchase_info": True},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("Deck analysis failed: %s", exc)
        return {
            "status": "error",
            "message": f"Analysis endpoint error ({exc.response.status_code})",
        }
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Deck analysis unexpected failure")
        return {"status": "error", "message": str(exc)}


def _optimize_deck(deck_id: Optional[int]) -> Dict[str, Any]:
    """Get AI optimization suggestions for a deck."""
    if not deck_id:
        return {"status": "error", "message": "Deck ID required"}

    try:
        response = httpx.post(
            f"{API_BASE_URL}/api/v1/optimize/{deck_id}",
            params={"include_purchase_info": True},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("Deck optimization failed: %s", exc)
        return {
            "status": "error",
            "message": f"Optimization endpoint error ({exc.response.status_code})",
        }
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Deck optimization unexpected failure")
        return {"status": "error", "message": str(exc)}


def _get_purchase_info(deck_id: Optional[int]) -> Dict[str, Any]:
    """Get physical card purchase information for a deck."""
    if not deck_id:
        return {"status": "error", "message": "Deck ID required"}

    try:
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/purchase/{deck_id}",
            params={"exclude_arena_only": True},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("Purchase info failed: %s", exc)
        return {
            "status": "error",
            "message": f"Purchase endpoint error ({exc.response.status_code})",
        }
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Purchase info unexpected failure")
        return {"status": "error", "message": str(exc)}


def _record_match(
    deck_id: Optional[int],
    opponent_archetype: str,
    result: str,
    games_won: int,
    games_lost: int,
    notes: str,
) -> Dict[str, Any]:
    """Record a match result."""
    if not deck_id:
        return {"status": "error", "message": "Deck ID required"}

    if not opponent_archetype or not result:
        return {"status": "error", "message": "Opponent archetype and result required"}

    try:
        response = httpx.post(
            f"{API_BASE_URL}/api/v1/performance/{deck_id}",
            json={
                "opponent_archetype": opponent_archetype,
                "result": result,
                "games_won": games_won,
                "games_lost": games_lost,
                "notes": notes,
            },
            timeout=60,
        )
        response.raise_for_status()
        return {"status": "success", "message": "Match recorded successfully"}
    except httpx.HTTPStatusError as exc:
        logger.error("Match recording failed: %s", exc)
        return {
            "status": "error",
            "message": f"Performance endpoint error ({exc.response.status_code})",
        }
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Match recording unexpected failure")
        return {"status": "error", "message": str(exc)}


def _create_mana_curve_chart(mana_curve_data: Dict[str, Any]) -> go.Figure:
    """Create a mana curve visualization using Plotly."""
    distribution = mana_curve_data.get("distribution", {})

    # Convert keys to integers and sort
    cmcs = sorted([int(k) for k in distribution.keys()])
    counts = [distribution[str(cmc)] for cmc in cmcs]

    fig = go.Figure(
        data=[
            go.Bar(
                x=cmcs,
                y=counts,
                marker_color="#9333ea",  # Purple color for Vawlrathh theme
                text=counts,
                textposition="outside",
            )
        ]
    )

    fig.update_layout(
        title="Mana Curve Distribution",
        xaxis_title="Converted Mana Cost",
        yaxis_title="Number of Cards",
        template="plotly_dark",
        height=400,
        showlegend=False,
    )

    return fig


def _create_color_pie_chart(color_distribution: Dict[str, int]) -> go.Figure:
    """Create a color distribution pie chart."""
    colors_map = {
        "W": "White",
        "U": "Blue",
        "B": "Black",
        "R": "Red",
        "G": "Green",
        "C": "Colorless",
    }

    color_hex = {
        "W": "#f8f8f0",
        "U": "#0e68ab",
        "B": "#150b00",
        "R": "#d3202a",
        "G": "#00733e",
        "C": "#ccc2c0",
    }

    labels = [colors_map.get(k, k) for k in color_distribution.keys()]
    values = list(color_distribution.values())
    colors = [color_hex.get(k, "#666") for k in color_distribution.keys()]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                marker=dict(colors=colors),
                textinfo="label+percent",
            )
        ]
    )

    fig.update_layout(
        title="Color Distribution",
        template="plotly_dark",
        height=400,
    )

    return fig


def _format_analysis_display(analysis: Dict[str, Any]) -> str:
    """Format deck analysis for display."""
    if "status" in analysis and analysis["status"] == "error":
        return f"❌ **Error:** {analysis.get('message', 'Unknown error')}"

    output = []

    # Deck name and overall score
    deck_name = analysis.get("deck_name", "Unknown Deck")
    overall_score = analysis.get("overall_score", 0)

    output.append(f"# 🎯 {deck_name}")
    output.append(f"**Overall Score:** {overall_score:.1f}/100")
    output.append("")

    # Mana curve stats
    mana_curve = analysis.get("mana_curve", {})
    if mana_curve:
        avg_cmc = mana_curve.get("average_cmc", 0)
        median_cmc = mana_curve.get("median_cmc", 0)
        curve_score = mana_curve.get("curve_score", 0)

        output.append("## 📊 Mana Curve Analysis")
        output.append(f"- **Average CMC:** {avg_cmc:.2f}")
        output.append(f"- **Median CMC:** {median_cmc:.1f}")
        output.append(f"- **Curve Score:** {curve_score:.1f}/100")
        output.append("")

    # Card types
    card_types = analysis.get("card_types", {})
    if card_types:
        output.append("## 🃏 Card Types")
        for card_type, count in card_types.items():
            output.append(f"- **{card_type}:** {count}")
        output.append("")

    # Strengths
    strengths = analysis.get("strengths", [])
    if strengths:
        output.append("## ✅ Strengths")
        for strength in strengths:
            output.append(f"- {strength}")
        output.append("")

    # Weaknesses
    weaknesses = analysis.get("weaknesses", [])
    if weaknesses:
        output.append("## ⚠️ Weaknesses")
        for weakness in weaknesses:
            output.append(f"- {weakness}")
        output.append("")

    # Meta matchups
    meta_matchups = analysis.get("meta_matchups", [])
    if meta_matchups:
        output.append("## 🎮 Meta Matchups")
        for matchup in meta_matchups[:5]:  # Show top 5
            archetype = matchup.get("archetype", "Unknown")
            win_rate = matchup.get("win_rate", 0)
            favorable = matchup.get("favorable", False)
            emoji = "✅" if favorable else "❌"
            output.append(f"- {emoji} **{archetype}:** {win_rate:.1f}% win rate")
        output.append("")

    return "\n".join(output)


def _format_purchase_info_table(purchase_info: Dict[str, Any]) -> pd.DataFrame:
    """Format purchase information as a DataFrame for display."""
    if "status" in purchase_info and purchase_info["status"] == "error":
        return pd.DataFrame()

    cards = purchase_info.get("cards", [])

    if not cards:
        return pd.DataFrame()

    rows = []
    for card in cards:
        rows.append({
            "Quantity": card.get("quantity", 1),
            "Card Name": card.get("card_name", "Unknown"),
            "Unit Price": f"${card.get('unit_price_usd', 0):.2f}",
            "Total Price": f"${card.get('total_price_usd', 0):.2f}",
            "Best Vendor": card.get("best_vendor", "N/A"),
        })

    return pd.DataFrame(rows)


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

    def handle_csv_upload(uploaded_file, previous_id):
        file_path = getattr(uploaded_file, "name", None)
        payload = _upload_csv_to_api(file_path)
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
        placeholder="4 Lightning Bolt (M11) 146\n2 Counterspell (MH2) 267",
    )
    format_dropdown = gr.Dropdown(
        choices=["Standard", "Pioneer", "Modern"],
        value="Standard",
        label="Format",
    )
    text_upload_btn = gr.Button("Upload Text", variant="secondary")

    def handle_text_upload(deck_text, fmt, previous_id):
        payload = _upload_text_to_api(deck_text, fmt)
        deck_id = payload.get("deck_id") or previous_id
        return payload, deck_id, deck_id

    text_upload_btn.click(  # pylint: disable=no-member
        fn=handle_text_upload,
        inputs=[deck_text_input, format_dropdown, deck_id_state],
        outputs=[upload_status, deck_id_state, deck_id_box],
    )

    gr.Markdown("### Tips")
    tips_markdown = (
        "* CSV uploads should come from the Steam Arena export.\n"
        "* Text uploads should be the Arena clipboard format.\n"
        "* The latest `deck_id` works across the Meta dashboard and chat tabs."
    )
    gr.Markdown(tips_markdown)


@builder_registry(
    name="chat_ui",
    description="WebSocket chat surface with consensus checking",
    endpoints=["/api/v1/ws/chat/{user_id}"],
    websocket_path="/api/v1/ws/chat/{user_id}",
)
def build_chat_ui_tab():
    """Enhanced WebSocket chat interface with consensus checking display."""

    gr.Markdown("## 💬 Chat with Vawlrathh, The Small'n")
    gr.Markdown(
        "*I'm not your friend. I'm your strategic advisor. Ask me about your deck, "
        "the meta, or why you keep losing.*"
    )

    # Consensus status indicator
    consensus_status = gr.Markdown(value="**Consensus Checking:** Ready", label="Consensus Status")

    chatbot = gr.Chatbot(
        label="Conversation",
        height=500,
        show_label=False,
    )

    with gr.Row():
        message_box = gr.Textbox(
            label="Message",
            lines=2,
            placeholder="Ask Vawlrathh for deck advice...",
            scale=4,
        )
        deck_context = gr.Number(
            label="Deck ID (optional)",
            precision=0,
            scale=1,
        )

    with gr.Row():
        send_btn = gr.Button("Send Message", variant="primary", size="lg")
        clear_btn = gr.Button("Clear Chat", variant="secondary")

    # Hidden state for managing conversation
    user_id_state = gr.State(value=str(uuid.uuid4()))
    chat_history_state = gr.State(value=[])

    async def send_message_async(message, deck_id, user_id, history):
        """Send message via WebSocket and get response."""
        if not message or not message.strip():
            return history, "", "**Consensus Checking:** Ready"

        # Add user message to history
        history = history or []
        history.append((message.strip(), None))

        # Connect to WebSocket
        ws_url = f"{WS_BASE_URL}/api/v1/ws/chat/{user_id}"

        try:
            async with websockets.connect(ws_url, open_timeout=10) as ws:
                # Build message payload
                payload = {
                    "type": "chat",
                    "message": message.strip(),
                }

                # Add deck context if provided
                if deck_id:
                    payload["context"] = {
                        "deck_id": int(deck_id),
                        "include_analysis": True,
                    }

                # Send message
                await ws.send(json.dumps(payload))

                # Wait for response
                response_data = await asyncio.wait_for(
                    ws.recv(),
                    timeout=60.0,
                )
                response = json.loads(response_data)

                # Process response
                if response.get("type") == "consensus_breaker":
                    # Consensus check failed
                    assistant_reply = response.get("response", "...")
                    consensus_info = response.get("consensus_breaker", {})

                    # Update chat history with warning
                    warning = consensus_info.get("warning", "Consensus check failed")
                    severity = consensus_info.get("severity", "warning")

                    # Format response with consensus warning
                    if severity == "critical":
                        formatted_response = (
                            f"🚨 **CRITICAL CONSENSUS FAILURE**\n\n"
                            f"{assistant_reply}\n\n"
                            f"---\n\n"
                            f"⚠️ **{warning}**"
                        )
                        consensus_display = "🚨 **Consensus Checking:** CRITICAL FAILURE"
                    else:
                        formatted_response = (
                            f"{assistant_reply}\n\n"
                            f"---\n\n"
                            f"⚠️ **{warning}**"
                        )
                        consensus_display = "⚠️ **Consensus Checking:** WARNING"

                    # Update last message with response
                    history[-1] = (history[-1][0], formatted_response)

                elif response.get("type") == "response":
                    # Normal response with successful consensus
                    assistant_reply = response.get("response", "...")
                    consensus_passed = response.get("consensus_passed", True)

                    if consensus_passed:
                        consensus_display = "✅ **Consensus Checking:** PASSED"
                    else:
                        consensus_display = "⚠️ **Consensus Checking:** See warning above"

                    # Update last message with response
                    history[-1] = (history[-1][0], assistant_reply)

                elif response.get("type") == "system":
                    # System message
                    system_msg = response.get("message", "System message")
                    history[-1] = (history[-1][0], f"*{system_msg}*")
                    consensus_display = "**Consensus Checking:** Ready"

                else:
                    # Unknown response type
                    history[-1] = (
                        history[-1][0],
                        f"*Unexpected response type: {response.get('type')}*",
                    )
                    consensus_display = "**Consensus Checking:** Ready"

        except asyncio.TimeoutError:
            history[-1] = (
                history[-1][0],
                "⏱️ *Request timed out. Vawlrathh is busy. Try again.*",
            )
            consensus_display = "**Consensus Checking:** Timeout"

        except websockets.exceptions.WebSocketException as exc:
            logger.error("WebSocket error: %s", exc)
            history[-1] = (
                history[-1][0],
                f"❌ *WebSocket connection failed: {str(exc)}*",
            )
            consensus_display = "**Consensus Checking:** Connection Error"

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Chat error")
            history[-1] = (
                history[-1][0],
                f"❌ *Error: {str(exc)}*",
            )
            consensus_display = "**Consensus Checking:** Error"

        return history, "", consensus_display

    def clear_chat():
        """Clear chat history."""
        return [], "**Consensus Checking:** Ready"

    send_btn.click(  # pylint: disable=no-member
        fn=send_message_async,
        inputs=[message_box, deck_context, user_id_state, chat_history_state],
        outputs=[chatbot, message_box, consensus_status],
    )

    clear_btn.click(  # pylint: disable=no-member
        fn=clear_chat,
        outputs=[chatbot, consensus_status],
    )

    gr.Markdown(
        "**Vawlrathh says:** *The consensus checker makes sure I don't give you terrible advice. "
        "Though honestly, your deck needs all the help it can get.*"
    )

    gr.Markdown(
        "### How Consensus Checking Works\n\n"
        "Every response from Vawlrathh is validated by a second AI (Claude Sonnet 4.5) to ensure:\n"
        "- Factually correct MTG rules and strategy\n"
        "- No contradictory meta information\n"
        "- Safe and helpful advice\n\n"
        "If consensus fails, you'll see a warning. Pay attention to these!"
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
    name="deck_analysis",
    description="Comprehensive deck analysis with visualizations",
    endpoints=["/api/v1/analyze/{deck_id}"],
)
def build_deck_analysis_tab():
    """Enhanced deck analysis tab with mana curve, card types, and pricing."""

    gr.Markdown("## 🎯 Deck Analysis")
    gr.Markdown("*Upload a deck first, then analyze it here. Your mana curve's probably a disaster.*")

    deck_id_input = gr.Number(label="Deck ID", precision=0)
    analyze_btn = gr.Button("Analyze Deck", variant="primary", size="lg")

    with gr.Row():
        with gr.Column(scale=1):
            mana_curve_plot = gr.Plot(label="Mana Curve")
        with gr.Column(scale=1):
            color_dist_plot = gr.Plot(label="Color Distribution")

    analysis_markdown = gr.Markdown(label="Analysis Results")

    def handle_analysis(deck_id):
        analysis = _analyze_deck(deck_id)

        if "status" in analysis and analysis["status"] == "error":
            return None, None, _format_analysis_display(analysis)

        # Create visualizations
        mana_curve_fig = None
        color_fig = None

        if "mana_curve" in analysis:
            mana_curve_fig = _create_mana_curve_chart(analysis["mana_curve"])

        if "color_distribution" in analysis:
            color_fig = _create_color_pie_chart(analysis["color_distribution"])

        analysis_text = _format_analysis_display(analysis)

        return mana_curve_fig, color_fig, analysis_text

    analyze_btn.click(  # pylint: disable=no-member
        fn=handle_analysis,
        inputs=deck_id_input,
        outputs=[mana_curve_plot, color_dist_plot, analysis_markdown],
    )

    gr.Markdown(
        "**Vawlrathh says:** *Fix your curve before you embarrass yourself at FNM.*"
    )


@builder_registry(
    name="deck_optimization",
    description="AI-powered deck optimization suggestions",
    endpoints=["/api/v1/optimize/{deck_id}"],
)
def build_deck_optimization_tab():
    """Deck optimization tab with AI suggestions."""

    gr.Markdown("## ⚡ Deck Optimization")
    gr.Markdown("*Let me tell you what's wrong with your deck. It's a lot.*")

    deck_id_input = gr.Number(label="Deck ID", precision=0)
    optimize_btn = gr.Button("Get Optimization Suggestions", variant="primary", size="lg")

    suggestions_output = gr.Markdown(label="Suggestions")
    raw_json = gr.JSON(label="Raw Response (for debugging)", visible=False)

    def handle_optimization(deck_id):
        result = _optimize_deck(deck_id)

        if "status" in result and result["status"] == "error":
            return f"❌ **Error:** {result.get('message', 'Unknown error')}", result

        output = []
        output.append("# 🔧 Optimization Suggestions")
        output.append("")

        # Predicted win rate
        predicted_wr = result.get("predicted_win_rate", 0)
        confidence = result.get("confidence", 0)
        output.append(f"**Predicted Win Rate:** {predicted_wr:.1f}%")
        output.append(f"**Confidence:** {confidence:.1f}%")
        output.append("")

        # Suggestions
        suggestions = result.get("suggestions", [])
        if suggestions:
            output.append("## 📝 Suggested Changes")

            adds = [s for s in suggestions if s.get("type") == "add"]
            removes = [s for s in suggestions if s.get("type") == "remove"]
            replaces = [s for s in suggestions if s.get("type") == "replace"]

            if adds:
                output.append("### ➕ Cards to Add")
                for suggestion in adds:
                    card_name = suggestion.get("card_name", "Unknown")
                    quantity = suggestion.get("quantity", 1)
                    reason = suggestion.get("reason", "No reason given")
                    impact = suggestion.get("impact_score", 0)
                    output.append(f"- **{quantity}x {card_name}** (Impact: {impact:.1f}/100)")
                    output.append(f"  - {reason}")
                output.append("")

            if removes:
                output.append("### ➖ Cards to Remove")
                for suggestion in removes:
                    card_name = suggestion.get("card_name", "Unknown")
                    quantity = suggestion.get("quantity", 1)
                    reason = suggestion.get("reason", "No reason given")
                    impact = suggestion.get("impact_score", 0)
                    output.append(f"- **{quantity}x {card_name}** (Impact: {impact:.1f}/100)")
                    output.append(f"  - {reason}")
                output.append("")

            if replaces:
                output.append("### 🔄 Card Replacements")
                for suggestion in replaces:
                    card_name = suggestion.get("card_name", "Unknown")
                    replacement_for = suggestion.get("replacement_for", "Unknown")
                    quantity = suggestion.get("quantity", 1)
                    reason = suggestion.get("reason", "No reason given")
                    impact = suggestion.get("impact_score", 0)
                    output.append(
                        f"- Replace **{quantity}x {replacement_for}** with **{quantity}x {card_name}** "
                        f"(Impact: {impact:.1f}/100)"
                    )
                    output.append(f"  - {reason}")
                output.append("")

        else:
            output.append("*No suggestions. Your deck is... actually not terrible. Shocking.*")

        return "\n".join(output), result

    optimize_btn.click(  # pylint: disable=no-member
        fn=handle_optimization,
        inputs=deck_id_input,
        outputs=[suggestions_output, raw_json],
    )

    gr.Markdown("**Vawlrathh says:** *These suggestions won't fix your play skill, but they'll help.*")


@builder_registry(
    name="card_pricing",
    description="Physical card purchase information",
    endpoints=["/api/v1/purchase/{deck_id}"],
)
def build_card_pricing_tab():
    """Physical card pricing tab."""

    gr.Markdown("## 💰 Physical Card Pricing")
    gr.Markdown("*Want to build this in paper? Here's what it'll cost you.*")

    deck_id_input = gr.Number(label="Deck ID", precision=0)
    pricing_btn = gr.Button("Get Purchase Info", variant="primary", size="lg")

    pricing_summary = gr.Markdown(label="Pricing Summary")
    pricing_table = gr.Dataframe(label="Card-by-Card Pricing")

    def handle_pricing(deck_id):
        purchase_info = _get_purchase_info(deck_id)

        if "status" in purchase_info and purchase_info["status"] == "error":
            return f"❌ **Error:** {purchase_info.get('message', 'Unknown error')}", pd.DataFrame()

        # Summary
        output = []
        output.append("# 💵 Purchase Summary")
        output.append("")

        total_cards = purchase_info.get("total_cards", 0)
        purchasable = purchase_info.get("purchasable_cards", 0)
        arena_only = purchase_info.get("arena_only_cards", 0)
        total_price = purchase_info.get("total_price_usd", 0)

        output.append(f"**Total Cards:** {total_cards}")
        output.append(f"**Purchasable in Paper:** {purchasable}")
        output.append(f"**Arena-Only Cards:** {arena_only}")
        output.append(f"**Total Price:** ${total_price:.2f} USD")
        output.append("")

        # Arena-only warning
        if arena_only > 0:
            output.append("## ⚠️ Arena-Only Cards")
            output.append("*These cards don't exist in paper. Stick to Arena with these.*")
            arena_only_list = purchase_info.get("arena_only", [])
            for card in arena_only_list[:10]:  # Show first 10
                quantity = card.get("quantity", 1)
                card_name = card.get("card_name", "Unknown")
                output.append(f"- {quantity}x {card_name}")
            output.append("")

        # Vendor breakdown
        summary = purchase_info.get("summary", {})
        vendor_breakdown = summary.get("cheapest_vendor_breakdown", {})
        if vendor_breakdown:
            output.append("## 🏪 Vendor Comparison")
            output.append("*If buying all cards from one vendor:*")
            for vendor, price in vendor_breakdown.items():
                output.append(f"- **{vendor}:** ${price:.2f}")
            output.append("")

        summary_text = "\n".join(output)
        pricing_df = _format_purchase_info_table(purchase_info)

        return summary_text, pricing_df

    pricing_btn.click(  # pylint: disable=no-member
        fn=handle_pricing,
        inputs=deck_id_input,
        outputs=[pricing_summary, pricing_table],
    )

    gr.Markdown("**Vawlrathh says:** *TCGPlayer usually has the best prices. You're welcome.*")


@builder_registry(
    name="match_tracking",
    description="Record and track match results",
    endpoints=["/api/v1/performance/{deck_id}", "/api/v1/stats/{deck_id}"],
)
def build_match_tracking_tab():
    """Match tracking interface."""

    gr.Markdown("## 📊 Match Tracking")
    gr.Markdown("*Record your matches. Let's see how badly you're doing.*")

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Record Match Result")
            deck_id_input = gr.Number(label="Deck ID", precision=0)
            opponent_input = gr.Textbox(label="Opponent Archetype", placeholder="Mono-Red Aggro")
            result_dropdown = gr.Dropdown(
                choices=["win", "loss", "draw"],
                value="win",
                label="Result",
            )
            games_won_input = gr.Number(label="Games Won", value=2, precision=0)
            games_lost_input = gr.Number(label="Games Lost", value=1, precision=0)
            notes_input = gr.Textbox(
                label="Notes",
                lines=3,
                placeholder="Sideboard choices, key plays, etc.",
            )
            record_btn = gr.Button("Record Match", variant="primary")
            record_status = gr.Markdown(label="Status")

        with gr.Column():
            gr.Markdown("### Deck Statistics")
            stats_deck_id = gr.Number(label="Deck ID", precision=0)
            load_stats_btn = gr.Button("Load Statistics", variant="secondary")
            stats_output = gr.JSON(label="Statistics")

    def handle_record_match(deck_id, opponent, result, games_won, games_lost, notes):
        response = _record_match(
            deck_id,
            opponent,
            result,
            int(games_won) if games_won else 0,
            int(games_lost) if games_lost else 0,
            notes,
        )

        if response.get("status") == "success":
            return f"✅ **Success:** {response.get('message', 'Match recorded')}"
        else:
            return f"❌ **Error:** {response.get('message', 'Unknown error')}"

    record_btn.click(  # pylint: disable=no-member
        fn=handle_record_match,
        inputs=[
            deck_id_input,
            opponent_input,
            result_dropdown,
            games_won_input,
            games_lost_input,
            notes_input,
        ],
        outputs=record_status,
    )

    load_stats_btn.click(  # pylint: disable=no-member
        fn=_fetch_memory_summary,
        inputs=stats_deck_id,
        outputs=stats_output,
    )

    gr.Markdown("**Vawlrathh says:** *Track your losses. Learn from them. Or don't. Your choice.*")


@builder_registry(
    name="sequential_reasoning",
    description="Step-by-step sequential reasoning visualization",
    endpoints=[],  # This will be integrated via MCP
)
def build_sequential_reasoning_tab():
    """Sequential reasoning visualization tab."""

    gr.Markdown("## 🧠 Sequential Reasoning")
    gr.Markdown(
        "*Watch me think through complex deck decisions step-by-step. "
        "This is how you should approach deckbuilding.*"
    )

    gr.Markdown(
        "### Coming Soon: Live Sequential Reasoning\n\n"
        "This feature will visualize the step-by-step reasoning process for:\n"
        "- Deck building decisions\n"
        "- Meta positioning analysis\n"
        "- Sideboard strategy\n"
        "- Card evaluation\n\n"
        "Each step will show:\n"
        "- The question being asked\n"
        "- The reasoning process\n"
        "- The conclusion\n"
        "- Confidence level (0-100%)\n\n"
        "**Integration via MCP Sequential Thinking server**"
    )

    # Placeholder for demo
    with gr.Accordion("Example: Deck Building Reasoning", open=False):
        gr.Markdown(
            """
            #### Step 1: What is the primary win condition?
            **Reasoning:** Analyzing the deck composition, most cards focus on early
            creature deployment and combat damage. The mana curve is low (avg 2.1 CMC).

            **Conclusion:** Aggressive creature-based strategy aiming to win by turn 5-6

            **Confidence:** 92%

            ---

            #### Step 2: What are the mana requirements and color distribution needs?
            **Reasoning:** Deck is mono-red with 20 Mountains. All spells require only
            red mana. No color fixing needed.

            **Conclusion:** Stick with 20 Mountains, no dual lands needed

            **Confidence:** 95%

            ---

            #### Step 3: Which meta archetypes does this deck need to beat?
            **Reasoning:** Current Standard meta has 25% control, 30% midrange,
            45% aggro/tempo. This deck is fastest aggro, should beat midrange and
            control, struggle against mirror matches.

            **Conclusion:** Sideboard against aggro mirrors, maindeck anti-control

            **Confidence:** 85%

            ---

            #### Final Decision
            **Deck is well-positioned against control and midrange. Add sideboard
            cards for aggro mirrors. Consider 2-3 maindeck card draw sources for
            longer games. Overall strategy is sound.**

            **Overall Confidence:** 88%
            """
        )

    gr.Markdown(
        "**Vawlrathh says:** *This is how you should think about every deck you build. "
        "Step by step. No shortcuts.*"
    )


def kill_existing_uvicorn():
    """Kill any existing uvicorn processes to avoid port conflicts."""
    try:
        # Find and kill existing uvicorn processes running on our port
        # More specific pattern to avoid killing unrelated processes
        result = subprocess.run(
            ["pkill", "-9", "-f", f"uvicorn.*{FASTAPI_PORT}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            logger.info(
                "Killed existing uvicorn processes on port %s",
                FASTAPI_PORT,
            )
        time.sleep(1)  # Give processes time to clean up
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Error killing uvicorn processes: %s", exc)


def start_fastapi_server():
    """Start the FastAPI server in the background."""
    kill_existing_uvicorn()
    
    logger.info("Starting FastAPI server on port %s...", FASTAPI_PORT)
    
    try:
        # Start uvicorn as a subprocess
        process = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "src.main:app",
                "--host", "0.0.0.0",
                "--port", str(FASTAPI_PORT),
                "--log-level", "info",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        logger.info("FastAPI server started with PID %s", process.pid)
        return process
    except (OSError, subprocess.SubprocessError) as exc:
        logger.error("Failed to start FastAPI server: %s", exc)
        raise


def wait_for_fastapi_ready(max_wait=60, check_interval=2):
    """Wait for FastAPI server to be ready by checking health endpoint.
    
    Args:
        max_wait: Maximum time to wait in seconds
        check_interval: Time between health checks in seconds
    
    Returns:
        bool: True if server is ready, False otherwise
    """
    logger.info("Waiting for FastAPI server to be ready...")
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            response = httpx.get(HEALTH_CHECK_URL, timeout=5.0)
            if response.status_code == 200:
                logger.info("FastAPI server is ready!")
                return True
        except (httpx.ConnectError, httpx.TimeoutException):
            logger.info(
                "Server not ready yet, waiting %s seconds...",
                check_interval,
            )
            time.sleep(check_interval)
        except httpx.HTTPError as exc:
            logger.warning("Health check error: %s", exc)
            time.sleep(check_interval)
    
    logger.error(
        "FastAPI server did not become ready within %s seconds",
        max_wait,
    )
    return False


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
    """Create the Gradio interface with tabs and Vawlrathh theme."""

    # Custom CSS for Vawlrathh theme
    custom_css = """
    .gradio-container {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    .vawlrathh-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 8px;
        color: white;
        margin-bottom: 1rem;
        text-align: center;
    }
    .vawlrathh-quote {
        font-style: italic;
        color: #a78bfa;
        border-left: 4px solid #9333ea;
        padding-left: 1rem;
        margin: 1rem 0;
    }
    .consensus-indicator {
        padding: 0.5rem 1rem;
        border-radius: 4px;
        font-weight: bold;
        margin: 0.5rem 0;
    }
    .consensus-pass {
        background: #10b981;
        color: white;
    }
    .consensus-warning {
        background: #f59e0b;
        color: white;
    }
    .consensus-critical {
        background: #ef4444;
        color: white;
    }
    """

    # Vawlrathh theme using Gradio's theming system
    vawlrathh_theme = gr.themes.Base(
        primary_hue="purple",
        secondary_hue="indigo",
        neutral_hue="slate",
        font=gr.themes.GoogleFont("Inter"),
    ).set(
        body_background_fill="*neutral_950",
        body_background_fill_dark="*neutral_950",
        button_primary_background_fill="*primary_600",
        button_primary_background_fill_hover="*primary_700",
        button_primary_text_color="white",
        block_title_text_color="*primary_300",
        block_label_text_color="*primary_400",
        input_background_fill="*neutral_800",
    )

    # About content with Vawlrath's personality
    about_html = textwrap.dedent(
        f"""
<div style="padding: 20px;">
    <div class="vawlrathh-header">
        <h1 style="margin: 0; font-size: 2.5em;">Vawlrathh</h1>
        <p style="margin: 0.5rem 0 0 0; font-size: 1.2em;">The Small'n</p>
    </div>

    <div class="vawlrathh-quote">
        "Your deck's terrible. Let me show you how to fix it."
    </div>

    <h2>🎯 What This Is</h2>
    <p>
        Listen up. I'm <strong>Vawlrathh, The Small'n</strong>—a pint-sized,
        sharp-tongued version of Volrath, The Fallen. Despite my stature, I
        know MTG Arena better than you know your own deck (which, frankly,
        isn't saying much).
    </p>

    <p>
        <strong>Vawlrathh (Arena Improver)</strong> is an MCP-powered deck analysis tool
        that actually works. It analyzes your janky brews, tells you what's
        wrong (plenty), and helps you build something that won't embarrass
        you at FNM.
    </p>

    <h3>✨ Key Features</h3>
    <ul>
        <li><strong>💰 Physical Card Pricing:</strong> Shows you what your Arena
        deck costs in real cardboard (TCGPlayer, CardMarket, Cardhoarder)</li>
        <li><strong>💬 Real-Time Strategy Chat:</strong> Talk to me via WebSocket.
        I'll tell you the truth (with consensus checking!)</li>
        <li><strong>🤖 Dual AI Consensus Checking:</strong> Every response validated
        by Claude Sonnet 4.5 so you don't get bad advice</li>
        <li><strong>🧠 Sequential Reasoning:</strong> Breaks down complex
        decisions into clear steps you can follow</li>
        <li><strong>🔧 Full MCP Integration:</strong> Memory, sequential thinking,
        omnisearch—the works</li>
        <li><strong>📊 Match Tracking:</strong> Record your games and track performance</li>
        <li><strong>⚡ AI-Powered Optimization:</strong> Get suggestions to improve your deck</li>
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

    <p style="margin-top: 30px; color: #a78bfa;">
        <strong>Repository:</strong>
        <a href="{REPO_URL}" target="_blank" style="color: #c4b5fd;">
            github.com/clduab11/vawlrathh
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
        title="Vawlrathh - MTG Arena Deck Analyzer",
        theme=vawlrathh_theme,
        css=custom_css,
    ) as interface:
        gr.HTML('<div class="vawlrathh-header"><h1 style="margin:0;">Vawlrathh, The Small\'n</h1><p style="margin:0.5rem 0 0;">MTG Arena Deck Analyzer</p></div>')
        gr.HTML('<div class="vawlrathh-quote">"Your deck\'s terrible. Let me show you how to fix it."</div>')

        with gr.Tabs():
            with gr.Tab("About"):
                gr.HTML(about_html)

            with gr.Tab("Quick Start"):
                gr.HTML(quick_start_html)

            with gr.Tab("🃏 Deck Upload"):
                build_deck_uploader_tab()

            with gr.Tab("🎯 Deck Analysis"):
                build_deck_analysis_tab()

            with gr.Tab("💬 Chat (HIGH PRIORITY)"):
                build_chat_ui_tab()

            with gr.Tab("⚡ Optimization"):
                build_deck_optimization_tab()

            with gr.Tab("💰 Card Pricing"):
                build_card_pricing_tab()

            with gr.Tab("🧠 Sequential Reasoning"):
                build_sequential_reasoning_tab()

            with gr.Tab("📊 Match Tracking"):
                build_match_tracking_tab()

            with gr.Tab("🎮 Meta Intelligence"):
                build_meta_dashboard_tab()

            with gr.Tab("API Documentation"):
                docs_markdown = textwrap.dedent(
                    """
                    ### Interactive API Documentation
                    Use the embedded Swagger UI below to explore and test the
                    available API endpoints. Expand any route and select
                    "Try it out" to make test requests directly from the
                    browser.
                    """
                )
                gr.Markdown(docs_markdown)

                iframe_html = textwrap.dedent(
                    f"""
                    <iframe
                        src="{DOCS_URL}"
                        width="100%"
                        height="800px"
                        style="border: 1px solid #ccc; border-radius: 4px;">
                    </iframe>
                    """
                )
                gr.HTML(iframe_html)

            with gr.Tab("⚙️ Status"):
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


def main():
    """Main entry point for the Hugging Face Space."""
    logger.info("=" * 60)
    logger.info("Arena Improver - Hugging Face Space")
    logger.info("=" * 60)
    
    # Start FastAPI server
    try:
        fastapi_process = start_fastapi_server()
    except (OSError, subprocess.SubprocessError) as exc:
        logger.error("Failed to start FastAPI server: %s", exc)
        sys.exit(1)
    
    # Wait for FastAPI to be ready
    if not wait_for_fastapi_ready(max_wait=60):
        logger.error("FastAPI server failed to start. Check logs above.")
        fastapi_process.terminate()
        try:
            fastapi_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning(
                "FastAPI process did not terminate gracefully; forcing kill",
            )
            fastapi_process.kill()
            fastapi_process.wait()
        sys.exit(1)
    
    # Create and launch Gradio interface
    try:
        logger.info("Creating Gradio interface...")
        interface = create_gradio_interface()
        
        logger.info("Launching Gradio on port %s...", GRADIO_PORT)
        logger.info("=" * 60)
        
        # Launch Gradio
        interface.launch(
            server_name="0.0.0.0",
            server_port=GRADIO_PORT,
            share=False,
            show_error=True
        )
    except (OSError, RuntimeError) as exc:
        logger.error("Failed to launch Gradio interface: %s", exc)
        fastapi_process.kill()
        sys.exit(1)


if __name__ == "__main__":
    main()
