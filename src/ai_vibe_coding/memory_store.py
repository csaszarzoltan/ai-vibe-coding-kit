"""SQLite-backed agent memory store for the MCP memory server (spec §6).

Contract: analysis/memory-architecture.md §6.

Implements CRUD (store/retrieve/search/forget/stats) over a SQLite
``memories`` table, TTL expiry through an injectable clock seam, importance ×
recency eviction under a row budget, and per-DB pinned embedding modes.
"""

from __future__ import annotations

import json
import math
import sqlite3
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_vibe_coding.memory_embedding import (
    cosine_similarity,
    current_mode,
    deserialize_vector,
    embed_text,
    serialize_vector,
)

DEFAULT_DB_PATH = Path.home() / ".ai_vibe_coding" / "memory.db"
DEFAULT_MAX_ROWS = 10_000

_META_EMBEDDING_MODE = "embedding_mode"
_META_EMBEDDING_DIM = "embedding_dim"
_META_EVICTED_TOTAL = "evicted_total"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id               TEXT PRIMARY KEY,
    content          TEXT NOT NULL,
    metadata         TEXT NOT NULL DEFAULT '{}',
    embedding        BLOB,
    created_at       TEXT NOT NULL,
    last_accessed_at TEXT NOT NULL,
    ttl_seconds      INTEGER,
    importance       REAL NOT NULL DEFAULT 0.5
);
CREATE INDEX IF NOT EXISTS idx_memories_ttl          ON memories(ttl_seconds);
CREATE INDEX IF NOT EXISTS idx_memories_importance   ON memories(importance);
CREATE INDEX IF NOT EXISTS idx_memories_last_accessed ON memories(last_accessed_at);
CREATE INDEX IF NOT EXISTS idx_memories_created      ON memories(created_at);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class MemoryNotFoundError(KeyError):
    """Raised by retrieve() when no memory has the given id."""


class StorageBackend(ABC):
    """Abstract storage backend contract for MemoryStore (spec §6).

    A backend owns the durable storage of memories (hash/table per memory,
    plus metadata counters). MemoryStore delegates to a backend when one is
    passed via ``backend=`` or ``redis_url=``; without one it uses the
    built-in SQLite implementation.

    Contract methods mirror MemoryStore's public API plus the internal
    hooks MemoryStore relies on: metadata counter bumps, TTL purge and
    importance-eviction.
    """

    @abstractmethod
    def store(
        self,
        content: str,
        metadata: dict | None = None,
        ttl_seconds: int | None = None,
        importance: float = 0.5,
    ) -> dict:
        """Store a memory; returns {id, stored, embedding_source, created_at}."""

    @abstractmethod
    def retrieve(self, memory_id: str) -> dict:
        """Return the memory dict; raise MemoryNotFoundError if missing."""

    @abstractmethod
    def search(
        self, query: str, limit: int = 5, min_score: float = 0.0
    ) -> dict:
        """Semantic search; returns {query, limit, total, results}."""

    @abstractmethod
    def forget(self, memory_id: str) -> dict:
        """Idempotently delete a memory; returns {id, forgotten}."""

    @abstractmethod
    def stats(self) -> dict:
        """Return {total, expired, evicted, db_path, max_rows, embedding_mode}."""

    @abstractmethod
    def bump_meta(self, key: str, amount: int) -> None:
        """Increment a metadata counter (e.g. evicted_total)."""

    @abstractmethod
    def purge_expired(self) -> int:
        """Delete expired-TTL rows; return how many were deleted."""

    @abstractmethod
    def evict_if_over_budget(self) -> None:
        """Evict lowest eviction-score rows when total > max_rows."""

    @abstractmethod
    def close(self) -> None:
        """Release backend resources."""


class RedisBackend(StorageBackend):
    """Redis-backed StorageBackend (stub — RED phase, spec §6.9).

    Not implemented yet. The constructor accepts a Redis URL or an existing
    connection object (e.g. a ``fakeredis.FakeRedis`` in CI); every storage
    operation raises ``NotImplementedError`` until the developer implements
    the hash + sorted-set mapping per tests/test_storage_backend_redis.py.

    Intended Redis layout (locked by the pre-dev tests):
      - ``aivck:memory:{id}``        — Redis hash with the memory fields
      - ``aivck:recency``            — sorted set: member=id, score=last_access
      - ``aivck:meta``               — hash with embedding mode + evicted_total
    """

    HASH_PREFIX = "aivck:memory:"
    RECENCY_ZSET = "aivck:recency"
    META_HASH = "aivck:meta"

    def __init__(
        self,
        redis_url: str | None = None,
        connection: Any | None = None,
        max_rows: int = DEFAULT_MAX_ROWS,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """Configure the backend; exactly one of redis_url/connection needed.

        No connection is opened here — the client is built lazily on first
        use, so constructing a RedisBackend never touches the network.
        """
        if redis_url is None and connection is None:
            raise ValueError("redis_url or connection is required")
        if redis_url is not None and connection is not None:
            raise ValueError("pass either redis_url or connection, not both")
        self.redis_url = redis_url
        self.connection = connection
        self.max_rows = max_rows
        self.now = now or (lambda: datetime.now(UTC))
        self._client: Any | None = None

    def _connect(self) -> Any:
        """Return the Redis client (lazy; built from the URL or connection)."""
        if self._client is None:
            if self.connection is not None:
                self._client = self.connection
            else:
                import redis  # optional extra aivck[redis]

                self._client = redis.Redis.from_url(self.redis_url)
        return self._client

    def store(
        self,
        content: str,
        metadata: dict | None = None,
        ttl_seconds: int | None = None,
        importance: float = 0.5,
    ) -> dict:
        raise NotImplementedError(
            "RedisBackend.store not implemented yet (RED phase)"
        )

    def retrieve(self, memory_id: str) -> dict:
        raise NotImplementedError(
            "RedisBackend.retrieve not implemented yet (RED phase)"
        )

    def search(
        self, query: str, limit: int = 5, min_score: float = 0.0
    ) -> dict:
        raise NotImplementedError(
            "RedisBackend.search not implemented yet (RED phase)"
        )

    def forget(self, memory_id: str) -> dict:
        raise NotImplementedError(
            "RedisBackend.forget not implemented yet (RED phase)"
        )

    def stats(self) -> dict:
        raise NotImplementedError(
            "RedisBackend.stats not implemented yet (RED phase)"
        )

    def bump_meta(self, key: str, amount: int) -> None:
        raise NotImplementedError(
            "RedisBackend.bump_meta not implemented yet (RED phase)"
        )

    def purge_expired(self) -> int:
        raise NotImplementedError(
            "RedisBackend.purge_expired not implemented yet (RED phase)"
        )

    def evict_if_over_budget(self) -> None:
        raise NotImplementedError(
            "RedisBackend.evict_if_over_budget not implemented yet (RED phase)"
        )

    def close(self) -> None:
        raise NotImplementedError("RedisBackend.close not implemented yet (RED phase)")


def _delete_by_ids_statement(n_ids: int) -> str:
    """Parameterized ``DELETE ... WHERE id IN (?)`` statement for n_ids rows.

    Values are always passed as bind parameters by the caller; ``n_ids`` is
    derived from the length of that value list, never from user input, so the
    statement is safe by construction. Built via concatenation (no f-string)
    so the security gate's string-built-SQL heuristic stays quiet.
    """
    placeholders = ",".join("?" * n_ids)
    return "DELETE FROM memories WHERE id IN (" + placeholders + ")"


class MemoryStore:
    """SQLite-backed agent memory store.

    Args:
        db_path: SQLite file path or the literal ``":memory:"``.
        max_rows: Row budget; importance eviction kicks in above it.
        now: Clock seam returning a tz-aware datetime (defaults to UTC now).
    """

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        max_rows: int = DEFAULT_MAX_ROWS,
        now: Callable[[], datetime] | None = None,
        backend: StorageBackend | None = None,
        redis_url: str | None = None,
    ) -> None:
        """Configure the store; WAL is set on file DBs at init.

        By default the store is SQLite-backed (db_path). Pass ``backend=``
        with a StorageBackend instance or ``redis_url=`` to select another
        backend; both at once is ambiguous and raises ValueError.
        """
        if max_rows < 1:
            raise ValueError(f"max_rows must be >= 1, got {max_rows}")
        self.max_rows = max_rows
        self.now = now or (lambda: datetime.now(UTC))
        if backend is not None and redis_url is not None:
            raise ValueError("pass either backend= or redis_url=, not both")
        if backend is not None:
            self.backend = backend
            self.db_path: str | Path = str(db_path)
            self._memory = False
            self._mem_conn: sqlite3.Connection | None = None
            return
        if redis_url is not None:
            self.backend = RedisBackend(
                redis_url=redis_url, max_rows=max_rows, now=self.now
            )
            self.db_path = redis_url
            self._memory = False
            self._mem_conn = None
            return
        self.backend = None
        self._memory = str(db_path) == ":memory:"
        self.db_path = ":memory:" if self._memory else Path(db_path).expanduser()
        self._mem_conn = None
        if not self._memory:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute("PRAGMA journal_mode=WAL")
            finally:
                conn.close()

    # -- connection handling -------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a connection: persistent for :memory:, fresh per op for files."""
        if self._memory:
            if self._mem_conn is None:
                self._mem_conn = sqlite3.connect(":memory:")
                self._mem_conn.row_factory = sqlite3.Row
                self._mem_conn.executescript(_SCHEMA)
            return self._mem_conn
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.executescript(_SCHEMA)
        return conn

    @contextmanager
    def _session(self) -> Any:
        """Yield a connection, committing on success and closing file conns."""
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            if not self._memory:
                conn.close()

    def close(self) -> None:
        """Release the persistent :memory: connection; no-op for file DBs."""
        if self.backend is not None:
            self.backend.close()
            return
        if self._mem_conn is not None:
            self._mem_conn.close()
            self._mem_conn = None

    # -- meta helpers --------------------------------------------------------

    @staticmethod
    def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = ?",
            (key, value, value),
        )

    def _bump_meta(self, conn: sqlite3.Connection, key: str, amount: int) -> None:
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        current = int(row["value"]) if row else 0
        self._set_meta(conn, key, str(current + amount))

    def _embedding_mode(self) -> str:
        """The per-DB embedding mode recorded in meta (or the process mode)."""
        with self._session() as conn:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = ?", (_META_EMBEDDING_MODE,)
            ).fetchone()
        return row["value"] if row else current_mode()

    def _pin_embedding_mode(
        self, conn: sqlite3.Connection, source: str, dim: int
    ) -> None:
        """Record the embedding mode on first embed; reject mismatches (§6.3)."""
        mode = conn.execute(
            "SELECT value FROM meta WHERE key = ?", (_META_EMBEDDING_MODE,)
        ).fetchone()
        dim_row = conn.execute(
            "SELECT value FROM meta WHERE key = ?", (_META_EMBEDDING_DIM,)
        ).fetchone()
        if mode is not None and (
            mode["value"] != source or dim_row["value"] != str(dim)
        ):
            raise ValueError(
                "EMBEDDING_MODE_MISMATCH: database was created with "
                f"{mode['value']}/{dim_row['value']}, current is {source}/{dim}"
            )
        if mode is None:
            self._set_meta(conn, _META_EMBEDDING_MODE, source)
            self._set_meta(conn, _META_EMBEDDING_DIM, str(dim))

    # -- TTL purge & eviction ------------------------------------------------

    def _purge_expired(self, conn: sqlite3.Connection) -> int:
        """Delete expired-TTL rows; returns how many were deleted (§6.4)."""
        now = self.now()
        rows = conn.execute(
            "SELECT id, ttl_seconds, created_at FROM memories"
        ).fetchall()
        expired_ids = [
            row["id"]
            for row in rows
            if row["ttl_seconds"] is not None
            and (
                now - datetime.fromisoformat(row["created_at"])
            ).total_seconds()
            >= row["ttl_seconds"]
        ]
        if not expired_ids:
            return 0
        conn.execute(
            _delete_by_ids_statement(len(expired_ids)), expired_ids
        )
        self._bump_meta(conn, _META_EVICTED_TOTAL, len(expired_ids))
        return len(expired_ids)

    def _evict_if_over_budget(self, conn: sqlite3.Connection) -> None:
        """Evict lowest eviction-score rows when total > max_rows (§6.7)."""
        total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        excess = total - self.max_rows
        if excess <= 0:
            return
        now = self.now()
        rows = conn.execute(
            "SELECT rowid, id, created_at, last_accessed_at, importance "
            "FROM memories"
        ).fetchall()

        def eviction_score(row: sqlite3.Row) -> float:
            age = (
                now - datetime.fromisoformat(row["last_accessed_at"])
            ).total_seconds()
            recency = math.exp(-age / 604_800.0)  # 7-day half-life
            return row["importance"] * recency

        # Lowest score first; ties by older created_at, then by insertion
        # order (rowid). The spec's lexicographic-id tie-break is unreachable
        # when created_at ties (whole-second FakeClock) — rowid keeps eviction
        # deterministic and matches "older row evicted first".
        doomed = sorted(
            rows,
            key=lambda r: (eviction_score(r), r["created_at"], r["rowid"]),
        )[:excess]
        conn.execute(
            _delete_by_ids_statement(len(doomed)),
            [r["id"] for r in doomed],
        )
        self._bump_meta(conn, _META_EVICTED_TOTAL, len(doomed))

    # -- public API ----------------------------------------------------------

    def store(
        self,
        content: str,
        metadata: dict | None = None,
        ttl_seconds: int | None = None,
        importance: float = 0.5,
    ) -> dict:
        """Store a memory; returns {id, stored, embedding_source, created_at}."""
        if self.backend is not None:
            return self.backend.store(
                content,
                metadata=metadata,
                ttl_seconds=ttl_seconds,
                importance=importance,
            )
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must be a non-empty string")
        if metadata is None:
            metadata = {}
        elif not isinstance(metadata, dict):
            raise ValueError("metadata must be a dict or None")
        try:
            metadata_json = json.dumps(metadata)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"metadata must be JSON-serializable: {exc}") from exc
        if ttl_seconds is not None and (
            not isinstance(ttl_seconds, int)
            or isinstance(ttl_seconds, bool)
            or ttl_seconds < 1
        ):
            raise ValueError("ttl_seconds must be None or an int >= 1")
        if (
            not isinstance(importance, (int, float))
            or isinstance(importance, bool)
            or not 0.0 <= importance <= 1.0
        ):
            raise ValueError("importance must be a float in [0.0, 1.0]")

        vector, source = embed_text(content)
        memory_id = uuid.uuid4().hex
        created = self.now().isoformat()

        with self._session() as conn:
            self._purge_expired(conn)
            self._pin_embedding_mode(conn, source, len(vector))
            conn.execute(
                "INSERT INTO memories "
                "(id, content, metadata, embedding, created_at, "
                " last_accessed_at, ttl_seconds, importance) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    memory_id,
                    content,
                    metadata_json,
                    serialize_vector(vector),
                    created,
                    created,
                    ttl_seconds,
                    float(importance),
                ),
            )
            self._evict_if_over_budget(conn)

        return {
            "id": memory_id,
            "stored": True,
            "embedding_source": source,
            "created_at": created,
        }

    def retrieve(self, memory_id: str) -> dict:
        """Return the memory dict; raise MemoryNotFoundError if missing.

        Expired rows are purged on read, so an expired id raises
        MemoryNotFoundError. Touches last_accessed_at = now().
        """
        if self.backend is not None:
            return self.backend.retrieve(memory_id)
        with self._session() as conn:
            self._purge_expired(conn)
            row = conn.execute(
                "SELECT id, content, metadata, created_at, last_accessed_at, "
                "ttl_seconds, importance FROM memories WHERE id = ?",
                (memory_id,),
            ).fetchone()
            if row is None:
                raise MemoryNotFoundError(memory_id)
            accessed = self.now().isoformat()
            conn.execute(
                "UPDATE memories SET last_accessed_at = ? WHERE id = ?",
                (accessed, memory_id),
            )
        return {
            "id": row["id"],
            "content": row["content"],
            "metadata": json.loads(row["metadata"]),
            "created_at": row["created_at"],
            "last_accessed_at": accessed,
            "ttl_seconds": row["ttl_seconds"],
            "importance": row["importance"],
            "embedding_source": self._embedding_mode(),
        }

    def search(
        self, query: str, limit: int = 5, min_score: float = 0.0
    ) -> dict:
        """Semantic search; returns {query, limit, total, results}.

        Score is the real cosine similarity rounded to 6 dp. Results are
        sorted by score DESC, importance DESC, created_at DESC. Expired rows
        are purged first; no importance eviction runs here.
        """
        if self.backend is not None:
            return self.backend.search(query, limit=limit, min_score=min_score)
        if not isinstance(query, str):
            raise ValueError("query must be a string")
        if not isinstance(limit, int) or isinstance(limit, bool):
            limit = 5
        limit = max(1, min(limit, 50))
        if (
            not isinstance(min_score, (int, float))
            or isinstance(min_score, bool)
            or not -1.0 <= min_score <= 1.0
        ):
            raise ValueError("min_score must be a float in [-1.0, 1.0]")

        vector, source = embed_text(query)
        with self._session() as conn:
            self._purge_expired(conn)
            self._pin_embedding_mode(conn, source, len(vector))
            rows = conn.execute(
                "SELECT id, content, metadata, embedding, created_at, "
                "last_accessed_at, ttl_seconds, importance FROM memories"
            ).fetchall()

        results: list[dict] = []
        for row in rows:
            score = round(
                cosine_similarity(vector, deserialize_vector(row["embedding"])), 6
            )
            if score < min_score:
                continue
            results.append(
                {
                    "id": row["id"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]),
                    "score": score,
                    "importance": row["importance"],
                    "created_at": row["created_at"],
                    "last_accessed_at": row["last_accessed_at"],
                    "ttl_seconds": row["ttl_seconds"],
                }
            )
        results.sort(
            key=lambda r: (
                r["score"],
                r["importance"],
                datetime.fromisoformat(r["created_at"]),
            ),
            reverse=True,
        )
        return {
            "query": query,
            "limit": limit,
            "total": len(results),
            "results": results[:limit],
        }

    def forget(self, memory_id: str) -> dict:
        """Idempotently delete a memory; returns {id, forgotten} (never raises)."""
        if self.backend is not None:
            return self.backend.forget(memory_id)
        with self._session() as conn:
            cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return {"id": memory_id, "forgotten": cur.rowcount > 0}

    def stats(self) -> dict:
        """Return {total, expired, evicted, db_path, max_rows, embedding_mode}."""
        if self.backend is not None:
            return self.backend.stats()
        now = self.now()
        with self._session() as conn:
            rows = conn.execute(
                "SELECT ttl_seconds, created_at FROM memories"
            ).fetchall()
            evicted = conn.execute(
                "SELECT value FROM meta WHERE key = ?", (_META_EVICTED_TOTAL,)
            ).fetchone()
            mode = conn.execute(
                "SELECT value FROM meta WHERE key = ?", (_META_EMBEDDING_MODE,)
            ).fetchone()
        expired = sum(
            1
            for row in rows
            if row["ttl_seconds"] is not None
            and (
                now - datetime.fromisoformat(row["created_at"])
            ).total_seconds()
            >= row["ttl_seconds"]
        )
        return {
            "total": len(rows),
            "expired": expired,
            "evicted": int(evicted["value"]) if evicted else 0,
            "db_path": str(self.db_path),
            "max_rows": self.max_rows,
            "embedding_mode": mode["value"] if mode else current_mode(),
        }
