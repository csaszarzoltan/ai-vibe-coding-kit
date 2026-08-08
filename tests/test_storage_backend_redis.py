"""Pre-development tests for StorageBackend abstraction + Redis backend.

Contract: parent task t_587cba81 (extends analysis/memory-architecture.md §6 —
"StorageBackend + Redis backend" feature).

Convention (pre-tester):
    - Interface tests: MUST PASS immediately (ABC exists, MemoryStore accepts
      backend=/redis_url=, RedisBackend accepts URL/connection, redis extra in
      pyproject.toml, CLI --redis-url / AI_VIBE_MEMORY_REDIS_URL wiring).
    - Behavioral tests: MUST FAIL with NotImplementedError until the developer
      implements the Redis backend. The backend-agnostic parametrized suite
      runs the same scenario against SQLite (reference, passes) and
      RedisBackend (raises NotImplementedError → RED).

Stubs (raise NotImplementedError):
    src/ai_vibe_coding/memory_store.py — StorageBackend (ABC), RedisBackend
    examples/mcp_memory_server.py    — --redis-url / AI_VIBE_MEMORY_REDIS_URL

Run:
    .venv/bin/python -m pytest tests/test_storage_backend_redis.py -v
    .venv/bin/python -m pytest tests/test_storage_backend_redis.py -q -k Interface
    .venv/bin/python -m pytest tests/test_storage_backend_redis.py -q -k Behavioral
"""

from __future__ import annotations

import inspect
import os
import shutil
import socket
import subprocess
import sys
import time
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import fakeredis
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Ensure repo root is on sys.path so `import examples.mcp_memory_server` works
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ai_vibe_coding.memory_store import (  # noqa: E402
    DEFAULT_MAX_ROWS,
    MemoryNotFoundError,
    MemoryStore,
    RedisBackend,
    StorageBackend,
)
from examples import mcp_memory_server  # noqa: E402

MCP_TOOL_NAMES = [
    "memory_store",
    "memory_retrieve",
    "memory_search",
    "memory_forget",
    "memory_stats",
    "memory_compact",
]
_EMBEDDING_SOURCES = ("sentence-transformers", "hash-fallback")
REDIS_URL_ENV = "AI_VIBE_MEMORY_REDIS_URL"


class _FakeClock:
    """Deterministic clock seam (same as test_mcp_memory_server.py)."""

    def __init__(self) -> None:
        self.current = datetime(2026, 1, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


@pytest.fixture
def clock() -> _FakeClock:
    return _FakeClock()


# ===================================================================
# Interface tests — must PASS immediately against the stubs
# ===================================================================

class TestStorageBackendInterface:
    """StorageBackend ABC — the contract every backend must satisfy."""

    def test_storage_backend_is_abstract(self):
        """StorageBackend is an ABC (cannot be instantiated directly)."""
        assert inspect.isabstract(StorageBackend)
        with pytest.raises(TypeError):
            StorageBackend()  # type: ignore[abstract]

    def test_abstract_methods_declared(self):
        """store/retrieve/search/forget/stats + meta bump/expiry/eviction."""
        for name in (
            "store",
            "retrieve",
            "search",
            "forget",
            "stats",
            "bump_meta",
            "purge_expired",
            "evict_if_over_budget",
            "close",
        ):
            assert name in StorageBackend.__abstractmethods__, (
                f"StorageBackend missing abstract method {name}"
            )

    def test_store_signature(self):
        """store(content, metadata=None, ttl_seconds=None, importance=0.5)."""
        sig = inspect.signature(StorageBackend.store)
        assert list(sig.parameters) == [
            "self",
            "content",
            "metadata",
            "ttl_seconds",
            "importance",
        ]
        assert sig.parameters["metadata"].default is None
        assert sig.parameters["ttl_seconds"].default is None
        assert sig.parameters["importance"].default == 0.5

    def test_retrieve_signature(self):
        """retrieve(memory_id) — memory_id required."""
        sig = inspect.signature(StorageBackend.retrieve)
        assert list(sig.parameters) == ["self", "memory_id"]
        assert sig.parameters["memory_id"].default is inspect.Parameter.empty

    def test_search_signature(self):
        """search(query, limit=5, min_score=0.0)."""
        sig = inspect.signature(StorageBackend.search)
        params = sig.parameters
        assert list(params) == ["self", "query", "limit", "min_score"]
        assert params["limit"].default == 5
        assert params["min_score"].default == 0.0

    def test_forget_signature(self):
        """forget(memory_id) — memory_id required."""
        sig = inspect.signature(StorageBackend.forget)
        assert list(sig.parameters) == ["self", "memory_id"]

    def test_stats_signature(self):
        """stats() — no parameters beyond self."""
        sig = inspect.signature(StorageBackend.stats)
        assert list(sig.parameters) == ["self"]

    def test_meta_hook_signatures(self):
        """bump_meta(key, amount); purge_expired(); evict_if_over_budget()."""
        assert list(inspect.signature(StorageBackend.bump_meta).parameters) == [
            "self",
            "key",
            "amount",
        ]
        assert list(inspect.signature(StorageBackend.purge_expired).parameters) == [
            "self"
        ]
        assert list(
            inspect.signature(StorageBackend.evict_if_over_budget).parameters
        ) == ["self"]


class TestMemoryStoreBackendInterface:
    """MemoryStore accepts backend= and/or redis_url=; default stays SQLite."""

    def test_init_signature_has_backend_and_redis_url(self):
        """__init__ accepts backend=None and redis_url=None (default SQLite)."""
        sig = inspect.signature(MemoryStore.__init__)
        params = sig.parameters
        assert "backend" in params
        assert params["backend"].default is None
        assert "redis_url" in params
        assert params["redis_url"].default is None
        # Existing SQLite defaults are untouched.
        assert params["db_path"].default is not None
        assert params["max_rows"].default == DEFAULT_MAX_ROWS

    def test_default_backend_is_sqlite(self):
        """No backend/redis_url → SQLite (backend attribute is None)."""
        ms = MemoryStore(":memory:")
        assert ms.backend is None
        assert ms.db_path == ":memory:"

    def test_backend_kwarg_used(self):
        """backend= stores the provided StorageBackend instance."""
        backend = RedisBackend(redis_url="redis://localhost:6379/0")
        ms = MemoryStore(backend=backend)
        assert ms.backend is backend

    def test_redis_url_kwarg_builds_redis_backend(self):
        """redis_url= builds a RedisBackend internally."""
        ms = MemoryStore(redis_url="redis://localhost:6379/0")
        assert isinstance(ms.backend, RedisBackend)
        assert ms.backend.redis_url == "redis://localhost:6379/0"

    def test_backend_and_redis_url_together_rejected(self):
        """Passing both backend= and redis_url= is ambiguous → ValueError."""
        backend = RedisBackend(redis_url="redis://localhost:6379/0")
        with pytest.raises(ValueError):
            MemoryStore(backend=backend, redis_url="redis://localhost:6379/0")

    def test_backend_does_not_touch_sqlite(self):
        """Backend mode must not create a SQLite file or WAL side effects."""
        backend = RedisBackend(connection=fakeredis.FakeRedis())
        ms = MemoryStore(backend=backend)
        # No _session/_connect SQLite plumbing is set up in backend mode.
        assert ms._mem_conn is None
        assert ms.backend is backend


class TestRedisBackendInterface:
    """RedisBackend — exists, subclasses StorageBackend, accepts URL/conn."""

    def test_redis_backend_exists_and_subclasses(self):
        assert issubclass(RedisBackend, StorageBackend)

    def test_accepts_redis_url(self):
        """RedisBackend(redis_url=...) constructs without connecting."""
        rb = RedisBackend(redis_url="redis://localhost:6379/0")
        assert rb.redis_url == "redis://localhost:6379/0"
        assert rb.connection is None
        assert rb.max_rows == DEFAULT_MAX_ROWS

    def test_accepts_connection(self):
        """RedisBackend(connection=fakeredis.FakeRedis()) for local CI."""
        fake = fakeredis.FakeRedis()
        rb = RedisBackend(connection=fake)
        assert rb.connection is fake
        assert rb.redis_url is None

    def test_requires_exactly_one_of_url_or_connection(self):
        """Neither → ValueError; both → ValueError."""
        with pytest.raises(ValueError):
            RedisBackend()
        with pytest.raises(ValueError):
            RedisBackend(
                redis_url="redis://localhost:6379/0",
                connection=fakeredis.FakeRedis(),
            )

    def test_key_scheme_constants(self):
        """Locked Redis layout: hash prefix, recency zset, meta hash."""
        assert RedisBackend.HASH_PREFIX == "aivck:memory:"
        assert RedisBackend.RECENCY_ZSET == "aivck:recency"
        assert RedisBackend.META_HASH == "aivck:meta"


class TestPyprojectRedisExtraInterface:
    """pyproject.toml declares the optional aivck[redis] extra."""

    @staticmethod
    def _pyproject() -> dict:
        with open(_REPO_ROOT / "pyproject.toml", "rb") as fh:
            return tomllib.load(fh)

    def test_redis_optional_extra_declared(self):
        """[project.optional-dependencies] redis = [...] with redis-py."""
        extras = self._pyproject()["project"]["optional-dependencies"]
        assert "redis" in extras
        redis_deps = " ".join(extras["redis"]).lower()
        assert "redis" in redis_deps

    def test_fakeredis_in_dev_extras(self):
        """fakeredis is a dev dependency for local CI runs."""
        extras = self._pyproject()["project"]["optional-dependencies"]
        dev_deps = " ".join(extras["dev"]).lower()
        assert "fakeredis" in dev_deps


class TestMCPServerRedisCliInterface:
    """examples/mcp_memory_server.py — --redis-url + env var wiring."""

    def test_env_constant(self):
        """REDIS_URL_ENV == AI_VIBE_MEMORY_REDIS_URL (spec name)."""
        assert mcp_memory_server.REDIS_URL_ENV == "AI_VIBE_MEMORY_REDIS_URL"
        assert REDIS_URL_ENV == "AI_VIBE_MEMORY_REDIS_URL"

    def test_parser_has_redis_url_flag(self):
        """--redis-url flag exists on the CLI parser."""
        parser = mcp_memory_server.build_parser()
        args = parser.parse_args(["--redis-url", "redis://cli:6379/0"])
        assert args.redis_url == "redis://cli:6379/0"

    def test_env_var_is_parser_default(self, monkeypatch):
        """No flag + env set → env value (env > SQLite)."""
        monkeypatch.setenv(REDIS_URL_ENV, "redis://env:6379/0")
        parser = mcp_memory_server.build_parser()
        args = parser.parse_args([])
        assert args.redis_url == "redis://env:6379/0"

    def test_cli_flag_overrides_env(self, monkeypatch):
        """Flag + env set → CLI wins (CLI > env)."""
        monkeypatch.setenv(REDIS_URL_ENV, "redis://env:6379/0")
        parser = mcp_memory_server.build_parser()
        args = parser.parse_args(["--redis-url", "redis://cli:6379/0"])
        assert args.redis_url == "redis://cli:6379/0"

    def test_no_redis_defaults_to_sqlite(self, monkeypatch):
        """No flag, no env → None → SQLite backend."""
        monkeypatch.delenv(REDIS_URL_ENV, raising=False)
        parser = mcp_memory_server.build_parser()
        args = parser.parse_args([])
        assert args.redis_url is None

    def test_main_is_callable(self):
        """main(argv=None) is importable (does not run the server)."""
        assert callable(mcp_memory_server.main)
        sig = inspect.signature(mcp_memory_server.main)
        assert "argv" in sig.parameters
        assert sig.parameters["argv"].default is None

    def test_get_store_uses_redis_when_configured(self, monkeypatch):
        """_get_store() builds a RedisBackend store when _REDIS_URL is set."""
        monkeypatch.setattr(mcp_memory_server, "_REDIS_URL", "redis://x:6379/0")
        monkeypatch.setattr(mcp_memory_server, "_store", None)
        store = mcp_memory_server._get_store()
        assert isinstance(store.backend, RedisBackend)

    def test_get_store_uses_sqlite_by_default(self, monkeypatch):
        """_get_store() stays SQLite when no redis URL is configured."""
        monkeypatch.setattr(mcp_memory_server, "_REDIS_URL", None)
        monkeypatch.setattr(mcp_memory_server, "_store", None)
        store = mcp_memory_server._get_store()
        assert store.backend is None


# ===================================================================
# Behavioral tests — MUST FAIL with NotImplementedError (RED phase)
# ===================================================================

@pytest.fixture(params=["sqlite", "redis"])
def backend_store(request, tmp_path: Path, clock: _FakeClock) -> MemoryStore:
    """Backend-agnostic store: the SAME scenario runs against both backends.

    sqlite → built-in SQLite implementation (reference, fully implemented).
    redis  → MemoryStore(backend=RedisBackend(fakeredis)) → RED until
             RedisBackend is implemented.
    """
    if request.param == "sqlite":
        return MemoryStore(tmp_path / "mem.db", max_rows=10, now=clock)
    backend = RedisBackend(
        connection=fakeredis.FakeRedis(), max_rows=10, now=clock
    )
    return MemoryStore(backend=backend, max_rows=10, now=clock)


class TestBackendAgnosticBehavior:
    """Identical store/retrieve/search/forget/stats/expiry/eviction behavior.

    Parametrized over sqlite (passes now) and redis (raises
    NotImplementedError → RED). Proves both backends honor the same contract,
    including embedding-mode search pinning.
    """

    def test_store_retrieve_roundtrip(self, backend_store: MemoryStore):
        """store → retrieve returns content/metadata/importance/ttl."""
        result = backend_store.store("hello backend")
        assert result["stored"] is True
        assert len(result["id"]) == 32
        assert result["embedding_source"] in _EMBEDDING_SOURCES
        assert "created_at" in result

        retrieved = backend_store.retrieve(result["id"])
        assert retrieved["content"] == "hello backend"
        assert retrieved["metadata"] == {}
        assert retrieved["ttl_seconds"] is None
        assert retrieved["importance"] == 0.5

    def test_metadata_roundtrip(self, backend_store: MemoryStore):
        """Metadata dict survives store → retrieve on both backends."""
        result = backend_store.store(
            "with meta", metadata={"topic": "backend"}, importance=0.8
        )
        retrieved = backend_store.retrieve(result["id"])
        assert retrieved["metadata"] == {"topic": "backend"}
        assert retrieved["importance"] == 0.8

    def test_semantic_search_finds_related(self, backend_store: MemoryStore):
        """Search ranks the semantically related memory on both backends."""
        stored = backend_store.store("vector databases index embeddings")
        result = backend_store.search("embedding storage")
        assert result["query"] == "embedding storage"
        assert result["total"] >= 1
        hit = next(
            r for r in result["results"] if r["id"] == stored["id"]
        )
        assert isinstance(hit["score"], float)
        assert 0.0 <= hit["score"] <= 1.0

    def test_forget_removes_and_is_idempotent(self, backend_store: MemoryStore):
        """forget deletes; a second forget returns forgotten=False."""
        result = backend_store.store("to be forgotten")
        assert backend_store.forget(result["id"]) == {
            "id": result["id"],
            "forgotten": True,
        }
        assert backend_store.forget(result["id"]) == {
            "id": result["id"],
            "forgotten": False,
        }
        with pytest.raises(MemoryNotFoundError):
            backend_store.retrieve(result["id"])

    def test_stats_shape(self, backend_store: MemoryStore):
        """stats() carries total/expired/evicted/max_rows/embedding_mode."""
        backend_store.store("stats row")
        stats = backend_store.stats()
        for key in (
            "total",
            "expired",
            "evicted",
            "db_path",
            "max_rows",
            "embedding_mode",
        ):
            assert key in stats, f"stats() missing key {key}"
        assert stats["total"] == 1
        assert stats["max_rows"] == 10
        assert stats["embedding_mode"] in _EMBEDDING_SOURCES

    def test_ttl_expiry_via_clock(self, backend_store: MemoryStore, clock: _FakeClock):
        """A ttl=1 memory is purged after the clock advances 2s."""
        stored = backend_store.store("temporary fact", ttl_seconds=1)
        clock.advance(2)
        ids = [r["id"] for r in backend_store.search("temporary")["results"]]
        assert stored["id"] not in ids
        with pytest.raises(MemoryNotFoundError):
            backend_store.retrieve(stored["id"])

    def test_importance_eviction_over_budget(self, backend_store: MemoryStore):
        """max_rows=10, 12 stores → 2 lowest-score rows evicted."""
        for i in range(12):
            backend_store.store(f"row {i}", importance=0.1)
        stats = backend_store.stats()
        assert stats["total"] == 10
        assert stats["evicted"] >= 2

    def test_embedding_mode_pinned_across_stores(
        self, backend_store: MemoryStore
    ):
        """The per-backend embedding mode stays pinned (no mismatch errors)."""
        first = backend_store.store("pin mode one")
        mode = first["embedding_source"]
        second = backend_store.store("pin mode two")
        assert second["embedding_source"] == mode
        assert backend_store.stats()["embedding_mode"] == mode
        # A search on the same backend must not raise a mode-mismatch.
        backend_store.search("pin mode")


class TestRedisMappingBehavior:
    """Redis-specific: hash + sorted-set mapping (RED until implemented)."""

    def test_hash_mapping_after_store(self, clock: _FakeClock):
        """store → hash aivck:memory:{id} holds the memory fields."""
        client = fakeredis.FakeRedis()
        backend = RedisBackend(connection=client, now=clock)
        result = backend.store(
            "redis note",
            metadata={"topic": "redis"},
            ttl_seconds=3600,
            importance=0.7,
        )
        key = RedisBackend.HASH_PREFIX + result["id"]
        fields = client.hgetall(key)
        assert fields[b"content"] == b"redis note"
        assert b"metadata" in fields
        assert b"importance" in fields
        assert b"created_at" in fields
        assert b"ttl_seconds" in fields

    def test_recency_zset_scoring(self, clock: _FakeClock):
        """store → recency zset member=id; retrieve bumps its score."""
        client = fakeredis.FakeRedis()
        backend = RedisBackend(connection=client, now=clock)
        result = backend.store("recency probe")
        zset = RedisBackend.RECENCY_ZSET
        score_before = client.zscore(zset, result["id"])
        assert score_before is not None
        clock.advance(60)
        backend.retrieve(result["id"])
        score_after = client.zscore(zset, result["id"])
        assert score_after > score_before

    def test_recency_scored_eviction(self, clock: _FakeClock):
        """max_rows=2: oldest/least-recent memory evicted first."""
        client = fakeredis.FakeRedis()
        backend = RedisBackend(connection=client, max_rows=2, now=clock)
        old = backend.store("old", importance=0.5)
        clock.advance(10)
        fresh = backend.store("fresh", importance=0.5)
        clock.advance(10)
        newest = backend.store("newest", importance=0.5)
        assert client.zcard(RedisBackend.RECENCY_ZSET) == 2
        assert client.exists(RedisBackend.HASH_PREFIX + old["id"]) == 0
        assert client.exists(RedisBackend.HASH_PREFIX + fresh["id"]) == 1
        assert client.exists(RedisBackend.HASH_PREFIX + newest["id"]) == 1

    def test_ttl_sets_redis_expire(self, clock: _FakeClock):
        """store with ttl → the hash key carries a Redis TTL."""
        client = fakeredis.FakeRedis()
        backend = RedisBackend(connection=client, now=clock)
        result = backend.store("short lived", ttl_seconds=3600)
        ttl = client.ttl(RedisBackend.HASH_PREFIX + result["id"])
        assert ttl > 0
        assert ttl <= 3600

    def test_meta_hash_tracks_evicted_total(self, clock: _FakeClock):
        """eviction bumps evicted_total in the meta hash."""
        client = fakeredis.FakeRedis()
        backend = RedisBackend(connection=client, max_rows=2, now=clock)
        for i in range(5):
            backend.store(f"row {i}", importance=0.1)
        evicted = client.hget(RedisBackend.META_HASH, "evicted_total")
        assert evicted is not None
        assert int(evicted) >= 3

    def test_multi_connection_visibility(self, clock: _FakeClock):
        """Two backends sharing one server see each other's writes."""
        server = fakeredis.FakeServer()
        client_a = fakeredis.FakeRedis(server=server)
        client_b = fakeredis.FakeRedis(server=server)
        backend_a = RedisBackend(connection=client_a, now=clock)
        backend_b = RedisBackend(connection=client_b, now=clock)
        result = backend_a.store("shared memory")
        retrieved = backend_b.retrieve(result["id"])
        assert retrieved["content"] == "shared memory"
        assert backend_b.stats()["total"] == 1


class TestRedisMultiProcessBehavior:
    """Multi-process safety where practical (RED until implemented)."""

    def test_concurrent_writes_do_not_lose_memories(self, clock: _FakeClock):
        """N threads writing via one shared server → all rows survive."""
        from concurrent.futures import ThreadPoolExecutor

        server = fakeredis.FakeServer()
        client = fakeredis.FakeRedis(server=server)
        backend = RedisBackend(connection=client, now=clock)

        def _write(i: int) -> str:
            return backend.store(f"thread row {i}", importance=0.5)["id"]

        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(_write, range(12)))
        assert len(set(ids)) == 12
        assert backend.stats()["total"] == 12
        for i in range(12):
            assert backend.retrieve(ids[i])["content"] == f"thread row {i}"


class TestRedisMCPIntegrationBehavior:
    """examples/mcp_memory_server.py --redis-url + five MCP tools (RED)."""

    def test_in_process_tools_delegate_to_redis(self, monkeypatch, clock: _FakeClock):
        """Tool calls route to a RedisBackend store when redis is configured.

        RED phase: RedisBackend.store raises NotImplementedError, so calling
        the memory_store tool must fail with NotImplementedError. After the
        developer implements the backend, this test exercises the real path.
        """
        monkeypatch.setattr(mcp_memory_server, "_REDIS_URL", "redis://x:6379/0")
        monkeypatch.setattr(mcp_memory_server, "_store", None)
        store = mcp_memory_server._get_store()
        assert isinstance(store.backend, RedisBackend)
        store.store("redis tool memory")  # NotImplementedError → RED


@pytest.fixture(scope="module")
def redis_server() -> int:
    """Start a real local redis-server on a free port (integration only).

    Skips when the redis-server binary is unavailable (CI without Redis).
    """
    exe = shutil.which("redis-server")
    if exe is None:
        pytest.skip(
            "redis-server binary not found — cannot run Redis integration tests"
        )

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    proc = subprocess.Popen(
        [
            exe,
            "--port",
            str(port),
            "--save",
            "",
            "--appendonly",
            "no",
            "--daemonize",
            "no",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        import redis

        deadline = time.time() + 10
        client = redis.Redis(
            host="127.0.0.1", port=port, socket_connect_timeout=0.5
        )
        while time.time() < deadline:
            try:
                if client.ping():
                    break
            except redis.exceptions.ConnectionError:
                time.sleep(0.1)
        else:
            pytest.fail("redis-server did not become ready in time")
        yield port
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


class TestRedisMCPStdioIntegration:
    """Full stdio integration: server starts with --redis-url, tools work."""

    @staticmethod
    def _server_params(port: int, tmp_path: Path) -> StdioServerParameters:
        return StdioServerParameters(
            command=sys.executable,
            args=[
                "examples/mcp_memory_server.py",
                "--redis-url",
                f"redis://127.0.0.1:{port}/0",
            ],
            env={
                **os.environ,
                "AI_VIBE_MEMORY_DB": str(tmp_path / "unused.db"),
                "PYTHONUNBUFFERED": "1",
            },
            cwd=str(_REPO_ROOT),
        )

    @pytest.mark.asyncio
    async def test_five_tools_work_against_redis(
        self, redis_server: int, tmp_path: Path
    ):
        """Store → retrieve → search → forget → stats round trip over Redis."""
        params = self._server_params(redis_server, tmp_path)
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            tools = await session.list_tools()
            assert [t.name for t in tools.tools] == MCP_TOOL_NAMES

            stored = await session.call_tool(
                "memory_store",
                {
                    "content": "redis-backed memory",
                    "metadata": {"topic": "redis"},
                    "importance": 0.9,
                },
            )
            assert not stored.isError, f"memory_store failed: {stored.content}"
            import json

            payload = json.loads(stored.content[0].text)
            memory_id = payload["id"]

            retrieved = await session.call_tool(
                "memory_retrieve", {"memory_id": memory_id}
            )
            assert not retrieved.isError, f"memory_retrieve failed: {retrieved.content}"
            assert json.loads(retrieved.content[0].text)["content"] == (
                "redis-backed memory"
            )

            searched = await session.call_tool(
                "memory_search", {"query": "redis memory", "limit": 5}
            )
            assert not searched.isError, f"memory_search failed: {searched.content}"
            assert json.loads(searched.content[0].text)["total"] >= 1

            forgotten = await session.call_tool(
                "memory_forget", {"memory_id": memory_id}
            )
            assert not forgotten.isError, f"memory_forget failed: {forgotten.content}"
            assert json.loads(forgotten.content[0].text)["forgotten"] is True

            stats = await session.call_tool("memory_stats", {})
            assert not stats.isError, f"memory_stats failed: {stats.content}"
            stats_payload = json.loads(stats.content[0].text)
            assert "total" in stats_payload
            assert stats_payload["total"] == 0

    @pytest.mark.asyncio
    async def test_env_var_redis_url_used(self, redis_server: int, tmp_path: Path):
        """AI_VIBE_MEMORY_REDIS_URL env var alone selects Redis (no flag)."""
        params = StdioServerParameters(
            command=sys.executable,
            args=["examples/mcp_memory_server.py"],
            env={
                **os.environ,
                "AI_VIBE_MEMORY_DB": str(tmp_path / "unused.db"),
                "AI_VIBE_MEMORY_REDIS_URL": f"redis://127.0.0.1:{redis_server}/0",
                "PYTHONUNBUFFERED": "1",
            },
            cwd=str(_REPO_ROOT),
        )
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            stored = await session.call_tool(
                "memory_store", {"content": "env-wired memory"}
            )
            assert not stored.isError, f"memory_store failed: {stored.content}"
