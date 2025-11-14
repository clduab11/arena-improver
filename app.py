"""Hugging Face Space wrapper for Arena Improver.

This module provides a Gradio interface that wraps the FastAPI application
for deployment on Hugging Face Spaces. The FastAPI server runs on port 7860
(HF Space default), and Gradio provides a web interface on port 7861.

"Your deck's terrible. Let me show you how to fix it."
— Vawlrathh, The Small'n
"""

import os
import subprocess
import sys
import time
import logging

import gradio as gr
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# HF Space configuration
FASTAPI_PORT = 7860  # HF Spaces expect main app on 7860
GRADIO_PORT = 7861   # Gradio interface on different port
HEALTH_CHECK_URL = f"http://localhost:{FASTAPI_PORT}/health"
DOCS_URL = f"/proxy/{FASTAPI_PORT}/docs"  # HF Space proxy pattern


def kill_existing_uvicorn():
    """Kill any existing uvicorn processes to avoid port conflicts."""
    try:
        # Find and kill existing uvicorn processes running on our port
        # More specific pattern to avoid killing unrelated processes
        result = subprocess.run(
            ["pkill", "-9", "-f", f"uvicorn.*{FASTAPI_PORT}"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logger.info(f"Killed existing uvicorn processes on port {FASTAPI_PORT}")
        time.sleep(1)  # Give processes time to clean up
    except Exception as e:
        logger.warning(f"Error killing uvicorn processes: {e}")


def start_fastapi_server():
    """Start the FastAPI server in the background."""
    kill_existing_uvicorn()
    
    logger.info(f"Starting FastAPI server on port {FASTAPI_PORT}...")
    
    try:
        # Start uvicorn as a subprocess
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
            logger.info(f"Server not ready yet, waiting {check_interval}s...")
            time.sleep(check_interval)
        except Exception as e:
            logger.warning(f"Health check error: {e}")
            time.sleep(check_interval)
    
    logger.error(f"FastAPI server did not become ready within {max_wait}s")
    return False


def check_environment():
    """Check if required environment variables are set and provide helpful feedback."""
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
    
    status_html = "<h3>Environment Configuration</h3><ul>"
    for key, status in env_status.items():
        status_html += f"<li><strong>{key}:</strong> {status}</li>"
    status_html += "</ul>"
    
    if has_missing_required:
        status_html += "<p style='color: red;'><strong>⚠ Warning:</strong> Some required API keys are missing. Configure them in the HF Space settings.</p>"
    
    return status_html


def create_gradio_interface():
    """Create the Gradio interface with tabs."""
    
    # About content with Vawlrath's personality
    about_html = """
    <div style="padding: 20px;">
        <h1>Arena Improver</h1>
        <p style="font-style: italic; color: #666;">
            "Your deck's terrible. Let me show you how to fix it."<br/>
            — <strong>Vawlrathh, The Small'n</strong>
        </p>
        
        <h2>🎯 What This Is</h2>
        <p>
            Listen up. I'm <strong>Vawlrathh, The Small'n</strong>—a pint-sized, sharp-tongued version 
            of Volrath, The Fallen. Despite my stature, I know MTG Arena better than you know your own 
            deck (which, frankly, isn't saying much).
        </p>
        
        <p>
            <strong>Arena Improver</strong> is an MCP-powered deck analysis tool that actually works. 
            It analyzes your janky brews, tells you what's wrong (plenty), and helps you build something 
            that won't embarrass you at FNM.
        </p>
        
        <h3>What Makes This Not-Garbage</h3>
        <ul>
            <li><strong>Physical Card Prices:</strong> Shows you what your Arena deck costs in real cardboard</li>
            <li><strong>Real-Time Strategy Chat:</strong> Talk to me via WebSocket. I'll tell you the truth</li>
            <li><strong>AI Consensus Checking:</strong> Two AI brains so you don't get bad advice</li>
            <li><strong>Sequential Reasoning:</strong> Breaks down complex decisions into steps you can follow</li>
            <li><strong>Full MCP Integration:</strong> Memory, sequential thinking, omnisearch—the works</li>
        </ul>
        
        <h3>🎖️ MCP 1st Birthday Hackathon</h3>
        <p>
            This project is submitted for the <strong>MCP 1st Birthday Hackathon</strong>. 
            Visit the <a href="https://huggingface.co/MCP-1st-Birthday" target="_blank">hackathon page</a> 
            to see more amazing MCP-powered projects.
        </p>
        
        <p style="margin-top: 30px; color: #666;">
            <strong>Repository:</strong> 
            <a href="https://github.com/clduab11/arena-improver" target="_blank">
                github.com/clduab11/arena-improver
            </a>
        </p>
    </div>
    """
    
    # Quick Start instructions
    quick_start_html = """
    <div style="padding: 20px;">
        <h2>🚀 Quick Start Guide</h2>
        
        <h3>Using the API</h3>
        <p>
            The FastAPI server is running and accessible through the <strong>API Documentation</strong> tab.
            You can explore all available endpoints, try them out directly, and see example responses.
        </p>
        
        <h3>Key Endpoints</h3>
        <ul>
            <li><strong>POST /api/v1/upload/csv</strong> - Upload a deck from Steam Arena CSV export</li>
            <li><strong>POST /api/v1/upload/text</strong> - Upload a deck from Arena text format</li>
            <li><strong>POST /api/v1/analyze/{deck_id}</strong> - Analyze a deck's strengths and weaknesses</li>
            <li><strong>POST /api/v1/optimize/{deck_id}</strong> - Get AI-powered optimization suggestions</li>
            <li><strong>GET /api/v1/purchase/{deck_id}</strong> - Get physical card purchase information</li>
            <li><strong>WebSocket /api/v1/ws/chat/{user_id}</strong> - Chat with Vawlrathh in real-time</li>
        </ul>
        
        <h3>Example Workflow</h3>
        <ol>
            <li>Export your deck from Arena as CSV or text</li>
            <li>Upload it using the <code>/api/v1/upload/csv</code> or <code>/api/v1/upload/text</code> endpoint</li>
            <li>Get the returned <code>deck_id</code></li>
            <li>Analyze it with <code>/api/v1/analyze/{deck_id}</code></li>
            <li>Get optimization suggestions with <code>/api/v1/optimize/{deck_id}</code></li>
            <li>Check physical card prices with <code>/api/v1/purchase/{deck_id}</code></li>
        </ol>
        
        <h3>WebSocket Chat</h3>
        <p>
            Connect to <code>ws://this-space-url/api/v1/ws/chat/your_user_id</code> to chat with me 
            in real-time. Send JSON messages like:
        </p>
        <pre><code>{
  "type": "chat",
  "message": "How do I beat control decks?",
  "context": {"deck_id": 1}
}</code></pre>
        
        <h3>Need Help?</h3>
        <p>
            Check the full documentation at 
            <a href="https://github.com/clduab11/arena-improver" target="_blank">
                GitHub Repository
            </a>
        </p>
        
        <p style="margin-top: 30px; font-style: italic; color: #666;">
            "If you have to ask, your deck probably needs more removal."<br/>
            — Vawlrathh
        </p>
    </div>
    """
    
    # Environment status
    env_status_html = check_environment()
    
    # Create the interface with tabs
    with gr.Blocks(title="Arena Improver - Vawlrathh's Deck Analysis") as interface:
        gr.Markdown("# Arena Improver - Vawlrathh, The Small'n")
        gr.Markdown("*Your deck's terrible. Let me show you how to fix it.*")
        
        with gr.Tabs():
            with gr.Tab("API Documentation"):
                gr.Markdown("""
                ### Interactive API Documentation
                The embedded documentation below allows you to explore and test all API endpoints.
                Click on any endpoint to expand it, then click "Try it out" to make requests.
                """)
                gr.HTML(f'<iframe src="{DOCS_URL}" width="100%" height="800px" style="border: 1px solid #ccc; border-radius: 4px;"></iframe>')
            
            with gr.Tab("About"):
                gr.HTML(about_html)
            
            with gr.Tab("Quick Start"):
                gr.HTML(quick_start_html)
            
            with gr.Tab("Status"):
                gr.HTML(env_status_html)
                gr.Markdown("""
                ### Troubleshooting
                If you see missing API keys above:
                1. Go to your Hugging Face Space settings
                2. Click on "Settings" → "Repository secrets"
                3. Add the required API keys as secrets
                4. Restart the Space
                
                See the [HF Deployment Guide](https://github.com/clduab11/arena-improver/blob/main/docs/HF_DEPLOYMENT.md) 
                for detailed instructions.
                """)
        
        gr.Markdown("""
        ---
        <p style="text-align: center; color: #666; font-size: 0.9em;">
            Diminutive in size, not in strategic prowess. | 
            <a href="https://github.com/clduab11/arena-improver" target="_blank">GitHub</a> | 
            <a href="https://huggingface.co/MCP-1st-Birthday" target="_blank">MCP 1st Birthday Hackathon</a>
        </p>
        """)
    
    return interface


def main():
    """Main entry point for the Hugging Face Space."""
    logger.info("=" * 60)
    logger.info("Arena Improver - Hugging Face Space")
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
        logger.info("Creating Gradio interface...")
        interface = create_gradio_interface()
        
        logger.info(f"Launching Gradio on port {GRADIO_PORT}...")
        logger.info("=" * 60)
        
        # Launch Gradio
        interface.launch(
            server_name="0.0.0.0",
            server_port=GRADIO_PORT,
            share=False,
            show_error=True
        )
    except Exception as e:
        logger.error(f"Failed to launch Gradio interface: {e}")
        fastapi_process.kill()
        sys.exit(1)


if __name__ == "__main__":
    main()
