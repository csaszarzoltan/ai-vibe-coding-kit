"""Application entry point for Railway deployment.

Creates the FastAPI application with the playground router included.
Run with: uvicorn ai_vibe_coding.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI

from ai_vibe_coding.playground import create_router

app = FastAPI(
    title="AI Vibe Coding Kit — Playground API",
    version="0.3.0",
    description="Multi-provider LLM playground comparison API",
)

# Include the playground router
router = create_router()
app.include_router(router)
