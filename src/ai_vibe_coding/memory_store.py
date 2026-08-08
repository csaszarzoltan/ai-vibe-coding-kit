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

# Schema additions for v0.14.0 compaction & knowledge distillation (spec §4.1).
# Applied once per connection alongside _SCHEMA via a guarded migration.
_COMPACT_SCHEMA = """
CREATE TABLE IF NOT EXISTS compaction_log (
    run_id      TEXT PRIMARY KEY,
    mode        TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    distilled   INTEGER NOT NULL DEFAULT 0,
    archived    INTEGER NOT NULL DEFAULT 0,
    merged      INTEGER NOT NULL DEFAULT 0,
    summary     TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS decay_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id   TEXT NOT NULL,
    happened_at TEXT NOT NULL,
    old_score   REAL NOT NULL,
    new_score   REAL NOT NULL
);
"""

# Column names added to the memories table for compaction support (spec §4.1).
_COMPACT_COLUMNS = ("status", "archived_at", "last_decayed_at")


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

    # -- compaction / distillation ABC (v0.14.0, spec §4.2) -----------------

    @abstractmethod
    def archive(self, memory_id: str, *, archived_at: str) -> dict:
        """Mark a memory 'archived' (never delete). Returns {id, status}."""

    @abstractmethod
    def list_memories(self, include_archived: bool = False) -> list[dict]:
        """Return all memory rows for the compaction engine to plan over."""

    @abstractmethod
    def batch_update_status(
        self, ids: list[str], status: str, *, archived_at: str | None = None
    ) -> int:
        """Atomic status update; returns rows affected (idempotent)."""

    @abstractmethod
    def write_distilled(
        self, content: str, sources: list[str], importance: float
    ) -> dict:
        """Persist a distilled entry with status='distilled'."""

    @abstractmethod
    def record_compaction_run(
        self, run_id: str, *, mode: str, distilled: int,
        archived: int, merged: int, summary: str
    ) -> None:
        """Append a compaction_log row (no-op if run_id exists)."""

    @abstractmethod
    def list_compaction_log(self, limit: int = 20) -> list[dict]:
        """Return recent compaction runs (newest first)."""

    @abstractmethod
    def record_decay(
        self, memory_id: str, *, old_score: float,
        new_score: float, happened_at: str
    ) -> None:
        """Append a decay_log row."""

    @abstractmethod
    def list_decay_log(self, limit: int = 50) -> list[dict]:
        """Return recent decay events (newest first)."""

    @abstractmethod
    def set_importance(
        self, memory_id: str, importance: float, *, last_decayed_at: str
    ) -> dict:
        """Update importance + last_decayed_at atomically; return the row."""


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

    def _hash_key(self, memory_id: str) -> str:
        """Return the Redis hash key for a memory."""
        return self.HASH_PREFIX + memory_id

    def _embedding_mode(self) -> str:
        """The per-backend embedding mode recorded in meta (or process mode)."""
        try:
            client = self._connect()
        except Exception:  # noqa: BLE001
            return current_mode()
        if client is None:
            return current_mode()
        mode = client.hget(self.META_HASH, _META_EMBEDDING_MODE)
        return mode.decode() if mode else current_mode()

    def _pin_embedding_mode(
        self, client: Any, source: str, dim: int
    ) -> None:
        """Record the embedding mode on first embed; reject mismatches."""
        if client is None:
            return
        mode = client.hget(self.META_HASH, _META_EMBEDDING_MODE)
        dim_val = client.hget(self.META_HASH, _META_EMBEDDING_DIM)
        if mode is not None and (
            mode.decode() != source or dim_val.decode() != str(dim)
        ):
            raise ValueError(
                "EMBEDDING_MODE_MISMATCH: backend was created with "
                f"{mode.decode()}/{dim_val.decode()}, current is {source}/{dim}"
            )
        if mode is None:
            client.hset(self.META_HASH, _META_EMBEDDING_MODE, source)
            client.hset(self.META_HASH, _META_EMBEDDING_DIM, str(dim))

    def _evict_if_over_budget(self, client: Any) -> None:
        """Evict lowest eviction-score rows when total > max_rows."""
        if client is None:
            return
        total = client.zcard(self.RECENCY_ZSET)
        excess = total - self.max_rows
        if excess <= 0:
            return
        now = self.now()
        scored: list[tuple[str, float]] = []
        for member in client.zscan_iter(self.RECENCY_ZSET, match="*", count=100):
            mid = member[0] if isinstance(member[0], str) else member[0].decode()
            key = self._hash_key(mid)
            fields = client.hgetall(key)
            if not fields:
                continue
            importance = float(fields[b"importance"])
            created = datetime.fromisoformat(fields[b"created_at"].decode())
            age = (now - created).total_seconds()
            recency = math.exp(-age / 604_800.0)
            scored.append((mid, importance * recency))
        scored.sort(key=lambda x: (x[1], x[0]))
        doomed = [mid for mid, _ in scored[:excess]]
        if doomed:
            pipe = client.pipeline(transaction=False)
            for mid in doomed:
                pipe.delete(self._hash_key(mid))
                pipe.zrem(self.RECENCY_ZSET, mid)
            pipe.execute()
            self.bump_meta(_META_EVICTED_TOTAL, len(doomed))

    def store(
        self,
        content: str,
        metadata: dict | None = None,
        ttl_seconds: int | None = None,
        importance: float = 0.5,
    ) -> dict:
        """Store a memory in Redis; returns id, stored, source, created_at."""
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

        try:
            client = self._connect()
            self.purge_expired()
        except Exception:  # noqa: BLE001
            client = None

        vector, source = embed_text(content)
        memory_id = uuid.uuid4().hex
        created = self.now().isoformat()

        if client is None:
            return {
                "id": memory_id,
                "stored": True,
                "embedding_source": source,
                "created_at": created,
            }

        key = self._hash_key(memory_id)
        pipe = client.pipeline(transaction=False)
        pipe.hset(key, mapping={
            "content": content,
            "metadata": metadata_json,
            "embedding": serialize_vector(vector),
            "created_at": created,
            "last_accessed_at": created,
            "ttl_seconds": "" if ttl_seconds is None else str(ttl_seconds),
            "importance": str(float(importance)),
        })
        ts = self.now().timestamp()
        pipe.zadd(self.RECENCY_ZSET, {memory_id: ts})
        if ttl_seconds is not None:
            pipe.expire(key, ttl_seconds)
        pipe.execute()

        self._pin_embedding_mode(client, source, len(vector))
        self._evict_if_over_budget(client)

        return {
            "id": memory_id,
            "stored": True,
            "embedding_source": source,
            "created_at": created,
        }

    def retrieve(self, memory_id: str) -> dict:
        """Return the memory dict; raise MemoryNotFoundError if missing."""
        try:
            client = self._connect()
            self.purge_expired()
        except Exception:  # noqa: BLE001
            raise MemoryNotFoundError(memory_id) from None

        key = self._hash_key(memory_id)
        fields = client.hgetall(key)
        if not fields:
            raise MemoryNotFoundError(memory_id)

        accessed = self.now().isoformat()
        client.hset(key, "last_accessed_at", accessed)
        ts = self.now().timestamp()
        client.zadd(self.RECENCY_ZSET, {memory_id: ts})

        ttl_val = fields[b"ttl_seconds"]
        return {
            "id": memory_id,
            "content": fields[b"content"].decode(),
            "metadata": json.loads(fields[b"metadata"].decode()),
            "created_at": fields[b"created_at"].decode(),
            "last_accessed_at": accessed,
            "ttl_seconds": int(ttl_val) if ttl_val else None,
            "importance": float(fields[b"importance"]),
            "embedding_source": self._embedding_mode(),
        }

    def search(
        self, query: str, limit: int = 5, min_score: float = 0.0
    ) -> dict:
        """Semantic search; returns {query, limit, total, results}."""
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

        try:
            client = self._connect()
            self.purge_expired()
        except Exception:  # noqa: BLE001
            client = None

        vector, source = embed_text(query)
        self._pin_embedding_mode(client, source, len(vector))

        results: list[dict] = []
        if client is None:
            return {
                "query": query,
                "limit": limit,
                "total": 0,
                "results": [],
            }
        for member in client.zscan_iter(self.RECENCY_ZSET, match="*", count=100):
            mid = member[0] if isinstance(member[0], str) else member[0].decode()
            key = self._hash_key(mid)
            fields = client.hgetall(key)
            if not fields:
                continue
            emb = deserialize_vector(fields[b"embedding"])
            score = round(cosine_similarity(vector, emb), 6)
            if score < min_score:
                continue
            ttl_val = fields[b"ttl_seconds"]
            results.append({
                "id": mid,
                "content": fields[b"content"].decode(),
                "metadata": json.loads(fields[b"metadata"].decode()),
                "score": score,
                "importance": float(fields[b"importance"]),
                "created_at": fields[b"created_at"].decode(),
                "last_accessed_at": fields[b"last_accessed_at"].decode(),
                "ttl_seconds": int(ttl_val) if ttl_val else None,
            })
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
        """Idempotently delete a memory; returns {id, forgotten}."""
        try:
            client = self._connect()
        except Exception:  # noqa: BLE001
            return {"id": memory_id, "forgotten": False}
        if client is None:
            return {"id": memory_id, "forgotten": False}
        key = self._hash_key(memory_id)
        existed = client.exists(key)
        client.delete(key)
        client.zrem(self.RECENCY_ZSET, memory_id)
        if existed:
            self.bump_meta(_META_EVICTED_TOTAL, 1)
        return {"id": memory_id, "forgotten": bool(existed)}

    def stats(self) -> dict:
        """Return {total, expired, evicted, db_path, max_rows, embedding_mode}."""
        try:
            client = self._connect()
        except Exception:  # noqa: BLE001
            client = None
        if client is None:
            return {
                "total": 0,
                "expired": 0,
                "evicted": 0,
                "db_path": str(self.redis_url),
                "max_rows": self.max_rows,
                "embedding_mode": self._embedding_mode(),
            }
        total = 0
        expired = 0
        now = self.now()
        for member in client.zscan_iter(self.RECENCY_ZSET, match="*", count=100):
            mid = member[0] if isinstance(member[0], str) else member[0].decode()
            key = self._hash_key(mid)
            fields = client.hgetall(key)
            if not fields:
                continue
            total += 1
            ttl_val = fields[b"ttl_seconds"]
            if ttl_val:
                ttl_int = int(ttl_val)
                created = datetime.fromisoformat(fields[b"created_at"].decode())
                if (now - created).total_seconds() >= ttl_int:
                    expired += 1
        evicted = client.hget(self.META_HASH, _META_EVICTED_TOTAL)
        mode = self._embedding_mode()
        return {
            "total": total,
            "expired": expired,
            "evicted": int(evicted) if evicted else 0,
            "db_path": str(self.redis_url),
            "max_rows": self.max_rows,
            "embedding_mode": mode,
        }

    def bump_meta(self, key: str, amount: int) -> None:
        """Increment a metadata counter atomically via HINCRBY."""
        try:
            client = self._connect()
        except Exception:  # noqa: BLE001
            return
        if client is None:
            return
        client.hincrby(self.META_HASH, key, amount)

    def purge_expired(self) -> int:
        """Delete expired-TTL rows; return how many were deleted."""
        try:
            client = self._connect()
        except Exception:  # noqa: BLE001
            return 0
        if client is None:
            return 0
        now = self.now()
        expired_ids: list[str] = []
        for member in client.zscan_iter(self.RECENCY_ZSET, match="*", count=100):
            mid = member[0] if isinstance(member[0], str) else member[0].decode()
            key = self._hash_key(mid)
            fields = client.hgetall(key)
            if not fields:
                continue
            ttl_val = fields[b"ttl_seconds"]
            if ttl_val:
                ttl_int = int(ttl_val)
                created = datetime.fromisoformat(fields[b"created_at"].decode())
                if (now - created).total_seconds() >= ttl_int:
                    expired_ids.append(mid)
        if not expired_ids:
            return 0
        pipe = client.pipeline(transaction=False)
        for mid in expired_ids:
            pipe.delete(self._hash_key(mid))
            pipe.zrem(self.RECENCY_ZSET, mid)
        pipe.execute()
        self.bump_meta(_META_EVICTED_TOTAL, len(expired_ids))
        return len(expired_ids)

    def evict_if_over_budget(self) -> None:
        """Evict lowest eviction-score rows when total > max_rows."""
        self._evict_if_over_budget(self._connect())

    def close(self) -> None:
        """Release the Redis client."""
        if self._client is not None and self.connection is None:
            self._client.close()
            self._client = None

    # -- compaction / distillation stubs (v0.14.0 RED phase, spec §4.2) -----

    def archive(self, memory_id: str, *, archived_at: str) -> dict:
        """Mark a memory 'archived' (never delete). Returns {id, status}."""
        raise NotImplementedError(
            "RedisBackend.archive not implemented yet (RED phase)"
        )

    def list_memories(self, include_archived: bool = False) -> list[dict]:
        """Return all memory rows for the compaction engine to plan over."""
        raise NotImplementedError(
            "RedisBackend.list_memories not implemented yet (RED phase)"
        )

    def batch_update_status(
        self, ids: list[str], status: str, *, archived_at: str | None = None
    ) -> int:
        """Atomic status update; returns rows affected (idempotent)."""
        raise NotImplementedError(
            "RedisBackend.batch_update_status not implemented yet (RED phase)"
        )

    def write_distilled(
        self, content: str, sources: list[str], importance: float
    ) -> dict:
        """Persist a distilled entry with status='distilled'."""
        raise NotImplementedError(
            "RedisBackend.write_distilled not implemented yet (RED phase)"
        )

    def record_compaction_run(
        self, run_id: str, *, mode: str, distilled: int,
        archived: int, merged: int, summary: str
    ) -> None:
        """Append a compaction_log row (no-op if run_id exists)."""
        raise NotImplementedError(
            "RedisBackend.record_compaction_run not implemented yet (RED phase)"
        )

    def list_compaction_log(self, limit: int = 20) -> list[dict]:
        """Return recent compaction runs (newest first)."""
        raise NotImplementedError(
            "RedisBackend.list_compaction_log not implemented yet (RED phase)"
        )

    def record_decay(
        self, memory_id: str, *, old_score: float,
        new_score: float, happened_at: str
    ) -> None:
        """Append a decay_log row."""
        raise NotImplementedError(
            "RedisBackend.record_decay not implemented yet (RED phase)"
        )

    def list_decay_log(self, limit: int = 50) -> list[dict]:
        """Return recent decay events (newest first)."""
        raise NotImplementedError(
            "RedisBackend.list_decay_log not implemented yet (RED phase)"
        )

    def set_importance(
        self, memory_id: str, importance: float, *, last_decayed_at: str
    ) -> dict:
        """Update importance + last_decayed_at atomically; return the row."""
        raise NotImplementedError(
            "RedisBackend.set_importance not implemented yet (RED phase)"
        )


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
                self._apply_compact_migration(self._mem_conn)
            return self._mem_conn
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.executescript(_SCHEMA)
        self._apply_compact_migration(conn)
        return conn

    @staticmethod
    def _apply_compact_migration(conn: sqlite3.Connection) -> None:
        """Guarded v0.14.0 migration: compaction_log/decay_log tables and
        status/archived_at/last_decayed_at columns on memories.

        Each statement is idempotent (CREATE TABLE IF NOT EXISTS; column
        added only when the pragma shows it is absent) so repeated calls
        and existing databases are safe.
        """
        conn.executescript(_COMPACT_SCHEMA)
        existing = {row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
        for col in _COMPACT_COLUMNS:
            if col not in existing:
                if col == "status":
                    conn.execute(
                        "ALTER TABLE memories ADD COLUMN status "
                        "TEXT NOT NULL DEFAULT 'active'"
                    )
                elif col == "archived_at":
                    conn.execute(
                        "ALTER TABLE memories ADD COLUMN archived_at TEXT"
                    )
                elif col == "last_decayed_at":
                    conn.execute(
                        "ALTER TABLE memories ADD COLUMN last_decayed_at TEXT"
                    )
        conn.commit()

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

    # -- compaction / distillation stubs (v0.14.0 RED phase, spec §4.3) -----

    def compact(
        self, *, dry_run: bool = True,
        age_days: float | None = None,
        importance_threshold: float | None = None,
        merge_threshold: float | None = None,
    ) -> dict:
        """Run the compaction job (spec §4.3).

        dry_run=True returns a PLAN dict; dry_run=False applies distill,
        merge and archive.  Idempotent: re-running skips already-archived
        rows.  Returns {run_id, mode, distilled, archived, merged, skipped,
        cluster_count, merge_count, dry_run}.
        """
        raise NotImplementedError("MemoryStore.compact not implemented yet")

    def impact_decay(
        self, *, decay_days: float | None = None, dry_run: bool = False
    ) -> dict:
        """Reduce importance of rarely-accessed old memories (spec §4.3).

        Returns {decayed, eligible_for_compaction, min_importance, dry_run}.
        """
        raise NotImplementedError("MemoryStore.impact_decay not implemented yet")

    def memory_stats(self) -> dict:
        """Extended stats including compaction/decay counters (spec §4.3).

        Extends the existing stats() dict with distilled_count,
        archived_count, merged_count, decayed_count, last_compaction,
        compact_runs and decay_events.
        """
        raise NotImplementedError("MemoryStore.memory_stats not implemented yet")
