"""Pre-development stub for the MCP memory server SQLite store.

Contract: analysis/memory-architecture.md §6.

Public API (interface tests pass immediately against this stub):
    DEFAULT_DB_PATH       — ~/.ai_vibe_coding/memory.db
    DEFAULT_MAX_ROWS      — 10_000
    MemoryNotFoundError   — KeyError subclass for retrieve() misses
    MemoryStore           — SQLite-backed store with store/retrieve/search/
                            forget/stats/close

The constructor stores configuration (db_path, max_rows, now) so interface
tests can build instances; all behavior methods raise NotImplementedError
until the developer implements them per the spec.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".ai_vibe_coding" / "memory.db"
DEFAULT_MAX_ROWS = 10_000


class MemoryNotFoundError(KeyError):
    """Raised by retrieve() when no memory has the given id."""


class MemoryStore:
    """SQLite-backed agent memory store (stub)."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        max_rows: int = DEFAULT_MAX_ROWS,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """Configure the store; no DB work until the first operation."""
        self.db_path = db_path
        self.max_rows = max_rows
        self.now = now or (lambda: datetime.now(UTC))

    def store(
        self,
        content: str,
        metadata: dict | None = None,
        ttl_seconds: int | None = None,
        importance: float = 0.5,
    ) -> dict:
        """Store a memory; returns {id, stored, embedding_source, created_at}."""
        raise NotImplementedError("MemoryStore.store not implemented yet")

    def retrieve(self, memory_id: str) -> dict:
        """Return the memory dict; raise MemoryNotFoundError if missing."""
        raise NotImplementedError("MemoryStore.retrieve not implemented yet")

    def search(
        self, query: str, limit: int = 5, min_score: float = 0.0
    ) -> dict:
        """Semantic search; returns {query, limit, total, results}."""
        raise NotImplementedError("MemoryStore.search not implemented yet")

    def forget(self, memory_id: str) -> dict:
        """Idempotently delete a memory; returns {id, forgotten}."""
        raise NotImplementedError("MemoryStore.forget not implemented yet")

    def stats(self) -> dict:
        """Return {total, expired, evicted, db_path, max_rows, embedding_mode}."""
        raise NotImplementedError("MemoryStore.stats not implemented yet")

    def close(self) -> None:
        """Release the persistent :memory: connection; no-op for file DBs."""
        raise NotImplementedError("MemoryStore.close not implemented yet")
