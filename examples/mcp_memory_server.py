#!/usr/bin/env python3
"""Standalone MCP agent memory server (spec §7).

A self-hosted, SQLite-backed MCP memory server exposing five tools —
``memory_store``, ``memory_retrieve``, ``memory_search``, ``memory_forget``,
``memory_stats`` — over stdio. Follows the repo's
``examples/standalone_mcp_server.py`` pattern: a module-level FastMCP
instance with importable, plain-Python tool functions. No API keys required.

Usage:
    # Run the server (stdio transport, default):
    python examples/mcp_memory_server.py

    # Point it at a specific database / row budget:
    python examples/mcp_memory_server.py --db /tmp/memory.db --max-rows 1000

    # Or via environment variables (CLI flags win):
    #   AI_VIBE_MEMORY_DB=/tmp/memory.db AI_VIBE_MEMORY_MAX_ROWS=1000

Config precedence: CLI flag > env var > default
(``~/.ai_vibe_coding/memory.db``, 10_000 rows).
"""

from __future__ import annotations

import argparse
import os
import threading
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ai_vibe_coding.memory_store import (
    DEFAULT_DB_PATH,
    DEFAULT_MAX_ROWS,
    MemoryStore,
)

SERVER_NAME = "ai-vibe-memory"
# mcp 1.x FastMCP defaults serverInfo.version to the SDK version; the spec
# (§7.4) pins the app version to 0.12.0, so set it on the low-level server.
mcp = FastMCP(SERVER_NAME)
mcp._mcp_server.version = "0.12.0"  # noqa: SLF001 - SDK has no public setter

_DB_PATH = Path(os.environ.get("AI_VIBE_MEMORY_DB", DEFAULT_DB_PATH)).expanduser()
_MAX_ROWS = int(os.environ.get("AI_VIBE_MEMORY_MAX_ROWS", DEFAULT_MAX_ROWS))
_store: MemoryStore | None = None  # lazy singleton; built on first tool call
_store_lock = threading.Lock()


def _get_store() -> MemoryStore:
    """Build the lazy MemoryStore singleton from module config."""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = MemoryStore(db_path=_DB_PATH, max_rows=_MAX_ROWS)
    return _store


@mcp.tool()
def memory_store(
    content: str,
    metadata: dict | None = None,
    ttl_seconds: int | None = None,
    importance: float = 0.5,
) -> dict:
    """Store a memory in the agent memory server.

    Args:
        content: Memory content to store (non-empty string).
        metadata: Optional structured metadata (JSON object).
        ttl_seconds: Time-to-live in seconds; omit for never-expiring.
        importance: Importance weight 0.0-1.0 (default 0.5), used by eviction.

    Returns:
        A dict with the new memory id, stored flag, embedding source and
        creation timestamp.
    """
    return _get_store().store(
        content,
        metadata=metadata,
        ttl_seconds=ttl_seconds,
        importance=importance,
    )


@mcp.tool()
def memory_retrieve(memory_id: str) -> dict:
    """Retrieve a memory by its id.

    Args:
        memory_id: The 32-char hex id returned by memory_store.

    Returns:
        The full memory dict (content, metadata, timestamps, importance).
    """
    return _get_store().retrieve(memory_id)


@mcp.tool()
def memory_search(query: str, limit: int = 5, min_score: float = 0.0) -> dict:
    """Semantically search stored memories.

    Args:
        query: The search text; results are ranked by cosine similarity.
        limit: Max results 1-50 (default 5).
        min_score: Minimum cosine score (default 0.0).

    Returns:
        A dict with the query, limit, total hit count and ranked results.
    """
    return _get_store().search(query, limit=limit, min_score=min_score)


@mcp.tool()
def memory_forget(memory_id: str) -> dict:
    """Forget (delete) a stored memory by id.

    Args:
        memory_id: The 32-char hex id of the memory to delete.

    Returns:
        A dict with the id and whether a row was actually forgotten.
        Idempotent: forgetting a missing id returns forgotten=False.
    """
    return _get_store().forget(memory_id)


@mcp.tool()
def memory_stats() -> dict:
    """Return store statistics.

    Returns:
        A dict with total rows, expired rows, evicted total, db path, row
        budget and the active embedding mode.
    """
    return _get_store().stats()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the MCP agent memory server over stdio."
    )
    parser.add_argument(
        "--db",
        default=str(_DB_PATH),
        help=f"SQLite database path (default: {_DB_PATH})",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=_MAX_ROWS,
        help=f"Row budget before importance eviction (default: {_MAX_ROWS})",
    )
    args = parser.parse_args()
    _DB_PATH = Path(args.db).expanduser()
    _MAX_ROWS = args.max_rows
    mcp.run(transport="stdio")
