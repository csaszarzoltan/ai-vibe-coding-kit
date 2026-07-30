"""Application entry point for Railway deployment.

Creates the FastAPI application with the playground router included.
Run with: uvicorn ai_vibe_coding.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ai_vibe_coding.control_api import router as control_router
from ai_vibe_coding.playground import create_router

app = FastAPI(
    title="AI Vibe Coding Kit — Playground API",
    version="0.3.0",
    description="Multi-provider LLM playground comparison API",
)

# Include the playground router
router = create_router()
app.include_router(router)

app.include_router(control_router)
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="static",
)
