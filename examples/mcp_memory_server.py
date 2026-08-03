"""Pre-development stub for the standalone MCP memory server.

Contract: analysis/memory-architecture.md §7.

Mirrors the repo's examples/standalone_mcp_server.py pattern: a module-level
FastMCP instance named "ai-vibe-memory" with five @mcp.tool()-decorated,
importable, plain-Python functions run over stdio.

Interface tests pass immediately (module import, mcp instance, tool
registration, signatures); tool bodies raise NotImplementedError until the
developer implements the real server per the spec.

Usage (after implementation):
    python examples/mcp_memory_server.py --db /tmp/memory.db --max-rows 1000
"""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ai_vibe_coding.memory_store import (
    DEFAULT_DB_PATH,
    DEFAULT_MAX_ROWS,
    MemoryStore,
)

SERVER_NAME = "ai-vibe-memory"
mcp = FastMCP(SERVER_NAME)

_DB_PATH = Path(os.environ.get("AI_VIBE_MEMORY_DB", DEFAULT_DB_PATH)).expanduser()
_MAX_ROWS = int(os.environ.get("AI_VIBE_MEMORY_MAX_ROWS", DEFAULT_MAX_ROWS))
_store: MemoryStore | None = None  # lazy singleton; built on first tool call


def _get_store() -> MemoryStore:
    """Build the lazy MemoryStore singleton from module config."""
    raise NotImplementedError("mcp_memory_server._get_store not implemented yet")


@mcp.tool()
def memory_store(
    content: str,
    metadata: dict | None = None,
    ttl_seconds: int | None = None,
    importance: float = 0.5,
) -> dict:
    """Store a memory in the agent memory server."""
    raise NotImplementedError("mcp_memory_server.memory_store not implemented yet")


@mcp.tool()
def memory_retrieve(memory_id: str) -> dict:
    """Retrieve a memory by its id."""
    raise NotImplementedError(
        "mcp_memory_server.memory_retrieve not implemented yet"
    )


@mcp.tool()
def memory_search(query: str, limit: int = 5, min_score: float = 0.0) -> dict:
    """Semantically search stored memories."""
    raise NotImplementedError("mcp_memory_server.memory_search not implemented yet")


@mcp.tool()
def memory_forget(memory_id: str) -> dict:
    """Forget (delete) a stored memory by id."""
    raise NotImplementedError("mcp_memory_server.memory_forget not implemented yet")


@mcp.tool()
def memory_stats() -> dict:
    """Return store statistics."""
    raise NotImplementedError("mcp_memory_server.memory_stats not implemented yet")


if __name__ == "__main__":
    # argparse --db/--max-rows written into module globals, then:
    mcp.run(transport="stdio")
