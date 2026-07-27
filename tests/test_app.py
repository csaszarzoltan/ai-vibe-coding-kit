"""Tests for the FastAPI application entry point (app.py)."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_app_imports() -> None:
    """app.py should create a FastAPI instance with the correct title."""
    from ai_vibe_coding.app import app

    assert app.title == "AI Vibe Coding Kit — Playground API"
    assert app.version == "0.3.0"
    assert len(app.routes) > 0
