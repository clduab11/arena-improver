"""Unit tests for Gradio helper utilities and builders."""

from contextlib import asynccontextmanager

import pytest
import gradio as gr

from app import (
    check_environment,
    GRADIO_BUILDERS,
    build_deck_uploader_tab,
    build_chat_ui_tab,
    build_meta_dashboard_tab,
    _check_chat_websocket,  # pylint: disable=protected-access
    _upload_text_to_api,  # pylint: disable=protected-access
)


ENV_KEYS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "TAVILY_API_KEY",
    "EXA_API_KEY",
)


@pytest.fixture()
def reset_env(monkeypatch):
    """Clear relevant environment variables for each test."""
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_check_environment_missing_required(reset_env):
    """Ensure warning is shown when required secrets are absent."""
    html = check_environment()

    assert "OPENAI_API_KEY" in html
    assert "ANTHROPIC_API_KEY" in html
    assert "✗ Missing" in html
    assert "⚠ Warning" in html


def test_check_environment_all_configured(reset_env, monkeypatch):
    """Ensure configured secrets display success indicators."""
    for key in ENV_KEYS:
        monkeypatch.setenv(key, "configured")

    html = check_environment()

    assert "⚠ Warning" not in html
    for key in ENV_KEYS:
        assert f"{key}:</strong> ✓ Configured" in html


def test_builder_registry_contains_expected_tabs():
    """Ensure required Gradio builders are registered with metadata."""
    expected = {"deck_uploader", "chat_ui", "meta_dashboards"}
    assert expected.issubset(set(GRADIO_BUILDERS))

    chat_builder = GRADIO_BUILDERS["chat_ui"]
    assert "/api/v1/ws/chat/{user_id}" in chat_builder.endpoints
    assert chat_builder.websocket_path == "/api/v1/ws/chat/{user_id}"


def test_builders_render_without_errors():
    """Ensure builder functions can render inside a Blocks context."""
    with gr.Blocks():
        build_deck_uploader_tab()
        build_chat_ui_tab()
        build_meta_dashboard_tab()


@pytest.mark.asyncio
async def test_upload_text_validation_short_circuit():
    """Empty deck strings should not attempt HTTP calls."""
    response = await _upload_text_to_api("", "Standard")
    assert response["status"] == "error"
    assert "empty" in response["message"].lower()


@pytest.mark.asyncio
async def test_check_chat_websocket_handles_error(monkeypatch):
    """WebSocket helper should report error details when connect fails."""

    @asynccontextmanager
    async def fake_connect(*args, **kwargs):  # pylint: disable=unused-argument
        raise RuntimeError("boom")
        yield

    monkeypatch.setattr("app.websockets.connect", fake_connect)

    result = await _check_chat_websocket()
    assert result["status"] == "error"
    assert "boom" in result["message"]
