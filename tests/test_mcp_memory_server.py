"""Pre-development tests for the MCP agent memory server.

Contract: analysis/memory-architecture.md (parent task t_9605b236).

Convention (pre-tester):
    - Interface tests: MUST PASS immediately (module structure, imports,
      constants, signatures, FastMCP registration) against the stub modules.
    - Behavioral tests: MUST FAIL with NotImplementedError until the developer
      implements the real server per the spec. They assert the full contract
      (CRUD, semantic search, TTL, eviction, persistence, MCP handshake).

Stubs (raise NotImplementedError):
    src/ai_vibe_coding/memory_store.py
    src/ai_vibe_coding/memory_embedding.py
    examples/mcp_memory_server.py
    examples/memory_client_example.py

Run:
    .venv/bin/python -m pytest tests/test_mcp_memory_server.py -v
    .venv/bin/python -m pytest tests/test_mcp_memory_server.py -q -k TestInterface
    .venv/bin/python -m pytest tests/test_mcp_memory_server.py -q -k TestBehavioral
"""

from __future__ import annotations

import inspect
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Ensure repo root is on sys.path so `import examples.mcp_memory_server` works
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ai_vibe_coding.memory_embedding import (  # noqa: E402
    FALLBACK_DIM,
    MODEL_NAME,
    cosine_similarity,
    deserialize_vector,
    embed_text,
    serialize_vector,
)
from ai_vibe_coding.memory_store import (  # noqa: E402
    DEFAULT_DB_PATH,
    DEFAULT_MAX_ROWS,
    MemoryNotFoundError,
    MemoryStore,
)
from examples import mcp_memory_server  # noqa: E402
from examples.memory_client_example import main, run_demo  # noqa: E402

MCP_TOOL_NAMES = [
    "memory_store",
    "memory_retrieve",
    "memory_search",
    "memory_forget",
    "memory_stats",
    "memory_compact",
]
_EMBEDDING_SOURCES = ("sentence-transformers", "hash-fallback")


class _FakeClock:
    """Deterministic clock seam (spec §12.1): MemoryStore(..., now=clock)."""

    def __init__(self) -> None:
        self.current = datetime(2026, 1, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def clock() -> _FakeClock:
    return _FakeClock()


@pytest.fixture
def store(tmp_path: Path, clock: _FakeClock) -> MemoryStore:
    """File-backed store with an injectable clock (isolated per test)."""
    return MemoryStore(tmp_path / "mem.db", now=clock)


@pytest.fixture
def memory_store() -> MemoryStore:
    """In-memory store for tests that don't touch persistence."""
    return MemoryStore(":memory:")


# ===================================================================
# Interface tests — must PASS immediately against the stubs
# ===================================================================

class TestMemoryStoreInterface:
    """ai_vibe_coding.memory_store — imports, constants, signatures."""

    def test_module_imports(self):
        """The public names import cleanly."""
        assert MemoryStore is not None
        assert MemoryNotFoundError is not None

    def test_default_max_rows_constant(self):
        """DEFAULT_MAX_ROWS == 10_000 (spec §6.1)."""
        assert DEFAULT_MAX_ROWS == 10_000

    def test_default_db_path_constant(self):
        """DEFAULT_DB_PATH is ~/.ai_vibe_coding/memory.db (spec §6.1)."""
        assert isinstance(DEFAULT_DB_PATH, Path)
        assert DEFAULT_DB_PATH.name == "memory.db"
        assert DEFAULT_DB_PATH.parent.name == ".ai_vibe_coding"

    def test_memory_not_found_error_is_keyerror(self):
        """MemoryNotFoundError subclasses KeyError (spec §6.1)."""
        assert issubclass(MemoryNotFoundError, KeyError)

    def test_init_signature(self):
        """__init__(db_path, max_rows, now) with spec defaults (§6.2)."""
        sig = inspect.signature(MemoryStore.__init__)
        params = sig.parameters
        assert set(params) >= {"self", "db_path", "max_rows", "now"}
        assert params["db_path"].default is DEFAULT_DB_PATH
        assert params["max_rows"].default is DEFAULT_MAX_ROWS
        assert params["now"].default is None

    def test_store_signature(self):
        """store(content, metadata=None, ttl_seconds=None, importance=0.5)."""
        sig = inspect.signature(MemoryStore.store)
        params = sig.parameters
        assert list(params) == [
            "self",
            "content",
            "metadata",
            "ttl_seconds",
            "importance",
        ]
        assert params["metadata"].default is None
        assert params["ttl_seconds"].default is None
        assert params["importance"].default == 0.5
        assert params["content"].default is inspect.Parameter.empty

    def test_retrieve_signature(self):
        """retrieve(memory_id) — memory_id required."""
        sig = inspect.signature(MemoryStore.retrieve)
        assert list(sig.parameters) == ["self", "memory_id"]
        assert sig.parameters["memory_id"].default is inspect.Parameter.empty

    def test_search_signature(self):
        """search(query, limit=5, min_score=0.0)."""
        sig = inspect.signature(MemoryStore.search)
        params = sig.parameters
        assert list(params) == ["self", "query", "limit", "min_score"]
        assert params["limit"].default == 5
        assert params["min_score"].default == 0.0

    def test_forget_signature(self):
        """forget(memory_id) — memory_id required."""
        sig = inspect.signature(MemoryStore.forget)
        assert list(sig.parameters) == ["self", "memory_id"]
        assert sig.parameters["memory_id"].default is inspect.Parameter.empty

    def test_stats_signature(self):
        """stats() — no parameters beyond self."""
        sig = inspect.signature(MemoryStore.stats)
        assert list(sig.parameters) == ["self"]

    def test_close_signature(self):
        """close() — no parameters beyond self."""
        sig = inspect.signature(MemoryStore.close)
        assert list(sig.parameters) == ["self"]

    def test_construct_memory_store(self):
        """A MemoryStore can be constructed with :memory: (no side effects)."""
        ms = MemoryStore(":memory:")
        assert ms.db_path == ":memory:"
        assert ms.max_rows == DEFAULT_MAX_ROWS


class TestMemoryEmbeddingInterface:
    """ai_vibe_coding.memory_embedding — constants and signatures."""

    def test_module_constants(self):
        """MODEL_NAME and FALLBACK_DIM match the spec (§5)."""
        assert MODEL_NAME == "all-MiniLM-L6-v2"
        assert FALLBACK_DIM == 256

    def test_embed_text_signature(self):
        """embed_text(text) -> tuple[list[float], str]."""
        sig = inspect.signature(embed_text)
        assert list(sig.parameters) == ["text"]
        assert sig.parameters["text"].default is inspect.Parameter.empty

    def test_cosine_similarity_signature(self):
        """cosine_similarity(a, b) -> float."""
        sig = inspect.signature(cosine_similarity)
        assert list(sig.parameters) == ["a", "b"]
        for name in ("a", "b"):
            assert sig.parameters[name].default is inspect.Parameter.empty

    def test_serialize_vector_signature(self):
        """serialize_vector(vec) -> bytes."""
        sig = inspect.signature(serialize_vector)
        assert list(sig.parameters) == ["vec"]

    def test_deserialize_vector_signature(self):
        """deserialize_vector(blob) -> list[float]."""
        sig = inspect.signature(deserialize_vector)
        assert list(sig.parameters) == ["blob"]

    def test_serialize_deserialize_roundtrip_same_signature_shape(self):
        """serialize/deserialize are inverse-shaped (one arg each)."""
        assert len(inspect.signature(serialize_vector).parameters) == 1
        assert len(inspect.signature(deserialize_vector).parameters) == 1


class TestMCPServerInterface:
    """examples.mcp_memory_server — FastMCP shell contract (§7)."""

    def test_module_imports(self):
        """Importing the module is side-effect-free (no DB created)."""
        assert mcp_memory_server.mcp is not None

    def test_server_name(self):
        """SERVER_NAME == 'ai-vibe-memory' (§7.1)."""
        assert mcp_memory_server.SERVER_NAME == "ai-vibe-memory"

    def test_mcp_is_fastmcp_instance(self):
        """mcp is a FastMCP instance (importable, runnable over stdio)."""
        from mcp.server.fastmcp import FastMCP

        assert isinstance(mcp_memory_server.mcp, FastMCP)

    def test_all_tool_functions_exist(self):
        """All five @mcp.tool() functions are importable and callable."""
        for name in MCP_TOOL_NAMES:
            fn = getattr(mcp_memory_server, name, None)
            assert fn is not None, f"{name} not found in module"
            assert callable(fn), f"{name} is not callable"

    def test_all_tools_have_docstrings(self):
        """Each tool function has a non-empty docstring."""
        for name in MCP_TOOL_NAMES:
            doc = getattr(mcp_memory_server, name).__doc__
            assert doc, f"{name} is missing a docstring"
            assert len(doc.strip()) > 0, f"{name} docstring is empty"

    def test_memory_store_tool_signature(self):
        """memory_store(content, metadata=None, ttl_seconds=None, importance=0.5)."""
        sig = inspect.signature(mcp_memory_server.memory_store)
        params = sig.parameters
        assert list(params) == ["content", "metadata", "ttl_seconds", "importance"]
        assert params["metadata"].default is None
        assert params["ttl_seconds"].default is None
        assert params["importance"].default == 0.5

    def test_memory_retrieve_tool_signature(self):
        """memory_retrieve(memory_id)."""
        sig = inspect.signature(mcp_memory_server.memory_retrieve)
        assert list(sig.parameters) == ["memory_id"]

    def test_memory_search_tool_signature(self):
        """memory_search(query, limit=5, min_score=0.0)."""
        sig = inspect.signature(mcp_memory_server.memory_search)
        params = sig.parameters
        assert list(params) == ["query", "limit", "min_score"]
        assert params["limit"].default == 5
        assert params["min_score"].default == 0.0

    def test_memory_forget_tool_signature(self):
        """memory_forget(memory_id)."""
        sig = inspect.signature(mcp_memory_server.memory_forget)
        assert list(sig.parameters) == ["memory_id"]

    def test_memory_stats_tool_signature(self):
        """memory_stats() — no parameters."""
        sig = inspect.signature(mcp_memory_server.memory_stats)
        assert list(sig.parameters) == []

    @pytest.mark.asyncio
    async def test_mcp_tool_registration_order(self):
        """tools/list order: store, retrieve, search, forget, stats (§7.2)."""
        tools = await mcp_memory_server.mcp.list_tools()
        names = [t.name for t in tools]
        assert names == MCP_TOOL_NAMES


class TestMemoryClientInterface:
    """examples.memory_client_example — cross-session demo contract (§8)."""

    def test_run_demo_exists(self):
        """run_demo is importable and callable."""
        assert callable(run_demo)

    def test_run_demo_signature(self):
        """run_demo(db_path=DEFAULT_DB_PATH) -> dict."""
        sig = inspect.signature(run_demo)
        params = sig.parameters
        assert list(params) == ["db_path"]
        assert params["db_path"].default is DEFAULT_DB_PATH

    def test_main_exists(self):
        """main is importable and callable."""
        assert callable(main)


# ===================================================================
# Behavioral tests — MUST FAIL with NotImplementedError until implemented
# ===================================================================

class TestCRUDBehavior:
    """(1) memory_store / memory_retrieve / memory_forget round-trip (§10 #1)."""

    def test_store_retrieve_roundtrip(self, store: MemoryStore):
        """store('hello') -> id; retrieve(id)['content'] == 'hello'."""
        result = store.store("hello")
        assert result["stored"] is True
        assert len(result["id"]) == 32
        assert all(c in "0123456789abcdef" for c in result["id"])
        assert result["embedding_source"] in _EMBEDDING_SOURCES
        assert "created_at" in result

        retrieved = store.retrieve(result["id"])
        assert retrieved["id"] == result["id"]
        assert retrieved["content"] == "hello"
        assert retrieved["metadata"] == {}
        assert retrieved["ttl_seconds"] is None
        assert retrieved["importance"] == 0.5

    def test_store_metadata_roundtrip(self, store: MemoryStore):
        """Metadata dict survives store -> retrieve."""
        result = store.store("sqlite note", metadata={"topic": "sqlite"})
        retrieved = store.retrieve(result["id"])
        assert retrieved["metadata"] == {"topic": "sqlite"}

    def test_forget_removes_memory(self, store: MemoryStore):
        """forget(id) -> {forgotten: True}; retrieve then raises."""
        result = store.store("to be forgotten")
        forgotten = store.forget(result["id"])
        assert forgotten == {"id": result["id"], "forgotten": True}
        with pytest.raises(MemoryNotFoundError):
            store.retrieve(result["id"])

    def test_forget_is_idempotent(self, store: MemoryStore):
        """forget of a missing id returns forgotten: False (never raises)."""
        result = store.store("gone soon")
        store.forget(result["id"])
        again = store.forget(result["id"])
        assert again == {"id": result["id"], "forgotten": False}

    def test_retrieve_missing_raises(self, store: MemoryStore):
        """retrieve of an unknown id raises MemoryNotFoundError."""
        with pytest.raises(MemoryNotFoundError):
            store.retrieve("00000000000000000000000000000000")


class TestSemanticSearchBehavior:
    """(2) Real semantic search with cosine similarity (§10 #2)."""

    def test_search_returns_related_memory(self, store: MemoryStore):
        """Searching 'embedding storage' finds a 'vector databases' memory."""
        stored = store.store("vector databases index embeddings")
        result = store.search("embedding storage")
        assert result["query"] == "embedding storage"
        assert result["total"] >= 1
        hit = next(r for r in result["results"] if r["id"] == stored["id"])
        assert isinstance(hit["score"], float)
        assert 0.0 <= hit["score"] <= 1.0
        # Real MiniLM cosine for this pair is well above 0.3 (spec §10 #2);
        # the hash-fallback mode is lexical, so only require a real score there.
        if stored["embedding_source"] == "sentence-transformers":
            assert hit["score"] >= 0.3

    def test_search_positive_score_with_overlapping_tokens(self, store: MemoryStore):
        """Real cosine > 0.0 for overlapping-token pairs in BOTH modes."""
        stored = store.store("vector databases index embeddings")
        result = store.search("embeddings vector databases")
        hit = next(r for r in result["results"] if r["id"] == stored["id"])
        assert hit["score"] > 0.0

    def test_search_empty_store(self, memory_store: MemoryStore):
        """search on an empty store returns total == 0, results == []."""
        result = memory_store.search("anything")
        assert result["total"] == 0
        assert result["results"] == []

    def test_search_result_shape(self, store: MemoryStore):
        """Each result row carries the spec keys (§6.6)."""
        store.store("shape check")
        result = store.search("shape")
        assert result["total"] >= 1
        row = result["results"][0]
        for key in (
            "id",
            "content",
            "metadata",
            "score",
            "importance",
            "created_at",
            "last_accessed_at",
            "ttl_seconds",
        ):
            assert key in row, f"result row missing key {key}"


class TestTTLBehavior:
    """(3) TTL expiry via the injectable clock (no sleep) (§10 #3)."""

    def test_ttl_expired_memory_gone_from_search(
        self, store: MemoryStore, clock: _FakeClock
    ):
        """A ttl_seconds=1 memory is purged after the clock advances 2s."""
        stored = store.store("temporary fact", ttl_seconds=1)
        clock.advance(2)
        result = store.search("temporary")
        ids = [r["id"] for r in result["results"]]
        assert stored["id"] not in ids

    def test_ttl_expired_retrieve_raises(
        self, store: MemoryStore, clock: _FakeClock
    ):
        """retrieve of an expired id raises MemoryNotFoundError (purge-on-read)."""
        stored = store.store("short lived", ttl_seconds=1)
        clock.advance(2)
        with pytest.raises(MemoryNotFoundError):
            store.retrieve(stored["id"])

    def test_ttl_purged_row_physically_deleted(
        self, store: MemoryStore, clock: _FakeClock, tmp_path: Path
    ):
        """The expired row is physically removed from the SQLite table."""
        stored = store.store("disposable", ttl_seconds=1)
        clock.advance(2)
        store.search("disposable")  # triggers the TTL purge
        conn = sqlite3.connect(str(tmp_path / "mem.db"))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE id = ?", (stored["id"],)
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == 0

    def test_ttl_purge_updates_stats(
        self, store: MemoryStore, clock: _FakeClock
    ):
        """stats reflects the purge: expired counter and evicted_total bump."""
        store.store("ephemeral", ttl_seconds=1)
        clock.advance(2)
        store.search("ephemeral")  # purge happens at search start
        stats = store.stats()
        assert "expired" in stats and isinstance(stats["expired"], int)
        # TTL purge increments evicted_total per spec §6.4
        assert stats["evicted"] >= 1

    def test_ttl_never_expires_without_ttl(
        self, store: MemoryStore, clock: _FakeClock
    ):
        """ttl_seconds=None means the memory survives clock advances."""
        stored = store.store("permanent", ttl_seconds=None)
        clock.advance(3600 * 24 * 30)  # a month later
        assert store.retrieve(stored["id"])["content"] == "permanent"


class TestEvictionBehavior:
    """(4) Importance × recency eviction under a row budget (§10 #4, §6.7)."""

    def test_low_importance_evicted_first(
        self, tmp_path: Path, clock: _FakeClock
    ):
        """max_rows=2, three rows (0.1/0.5/1.0): the 0.1 row is evicted."""
        store = MemoryStore(tmp_path / "evict.db", max_rows=2, now=clock)
        low = store.store("low", importance=0.1)
        mid = store.store("mid", importance=0.5)
        high = store.store("high", importance=1.0)

        assert store.stats()["total"] == 2
        assert store.stats()["evicted"] == 1
        with pytest.raises(MemoryNotFoundError):
            store.retrieve(low["id"])
        assert store.retrieve(mid["id"])["content"] == "mid"
        assert store.retrieve(high["id"])["content"] == "high"

    def test_no_eviction_under_budget(
        self, tmp_path: Path, clock: _FakeClock
    ):
        """Under the row budget, nothing is evicted."""
        store = MemoryStore(tmp_path / "roomy.db", max_rows=10, now=clock)
        for i in range(3):
            store.store(f"row {i}", importance=0.1)
        assert store.stats()["total"] == 3
        assert store.stats()["evicted"] == 0

    def test_eviction_ties_broken_by_created_at(
        self, tmp_path: Path, clock: _FakeClock
    ):
        """Equal importance: the older row is evicted first (§6.7)."""
        store = MemoryStore(tmp_path / "ties.db", max_rows=2, now=clock)
        first = store.store("old", importance=0.5)
        second = store.store("new", importance=0.5)
        clock.advance(10)
        third = store.store("newest", importance=0.5)
        assert store.stats()["total"] == 2
        with pytest.raises(MemoryNotFoundError):
            store.retrieve(first["id"])
        assert store.retrieve(second["id"])["content"] == "new"
        assert store.retrieve(third["id"])["content"] == "newest"


class TestPersistenceBehavior:
    """(5) Memories survive closing and reopening the SQLite DB (§10 #5)."""

    def test_memory_survives_restart(self, tmp_path: Path):
        """store -> close() -> reopen -> retrieve returns the same content."""
        db = tmp_path / "persist.db"
        store = MemoryStore(db)
        stored = store.store("persistent memory")
        store.close()

        reopened = MemoryStore(db)
        assert reopened.retrieve(stored["id"])["content"] == "persistent memory"
        reopened.close()

    def test_memory_store_does_not_persist(self):
        """:memory: stores are volatile across instances."""
        store = MemoryStore(":memory:")
        store.store("volatile")
        store.close()

        fresh = MemoryStore(":memory:")
        assert fresh.stats()["total"] == 0
        fresh.close()


class TestValidationBehavior:
    """Validation rules (§6.5) — ValueError on invalid arguments."""

    @pytest.mark.parametrize("bad_content", ["", "   ", 123, None])
    def test_store_rejects_bad_content(self, memory_store: MemoryStore, bad_content):
        """content must be a non-empty string."""
        with pytest.raises(ValueError):
            memory_store.store(bad_content)  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad_importance", [-0.1, 1.5, 2.0, "high"])
    def test_store_rejects_bad_importance(
        self, memory_store: MemoryStore, bad_importance
    ):
        """importance must be a float in [0.0, 1.0] (no clamping)."""
        with pytest.raises(ValueError):
            memory_store.store("x", importance=bad_importance)  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad_ttl", [0, -5, 1.5, "1"])
    def test_store_rejects_bad_ttl(self, memory_store: MemoryStore, bad_ttl):
        """ttl_seconds must be None or an int >= 1."""
        with pytest.raises(ValueError):
            memory_store.store("x", ttl_seconds=bad_ttl)  # type: ignore[arg-type]

    def test_constructor_rejects_bad_max_rows(self):
        """max_rows must be >= 1."""
        with pytest.raises(ValueError):
            MemoryStore(":memory:", max_rows=0)
        with pytest.raises(ValueError):
            MemoryStore(":memory:", max_rows=-1)

    @pytest.mark.parametrize("bad_score", [-1.5, 1.5, "high"])
    def test_search_rejects_bad_min_score(
        self, memory_store: MemoryStore, bad_score
    ):
        """min_score must be a float in [-1.0, 1.0]."""
        with pytest.raises(ValueError):
            memory_store.search("x", min_score=bad_score)  # type: ignore[arg-type]

    def test_cosine_rejects_dimension_mismatch(self):
        """cosine_similarity raises ValueError when lengths differ (§5.2)."""
        with pytest.raises(ValueError):
            cosine_similarity([0.1, 0.2, 0.3], [0.1, 0.2])

    def test_serialize_deserialize_roundtrip(self):
        """deserialize(serialize(v)) reproduces v (float32 precision ok)."""
        vec = [0.1, 0.2, 0.3, -0.5, 1.0]
        blob = serialize_vector(vec)
        assert isinstance(blob, bytes)
        assert deserialize_vector(blob) == pytest.approx(vec, abs=1e-6)


class TestMCPHandshakeBehavior:
    """(6) MCP initialize/handshake over stdio (§7.4, §10 #6)."""

    @staticmethod
    def _server_params(db_path: Path) -> StdioServerParameters:
        return StdioServerParameters(
            command=sys.executable,
            args=["examples/mcp_memory_server.py"],
            env={
                **os.environ,
                "AI_VIBE_MEMORY_DB": str(db_path),
                "PYTHONUNBUFFERED": "1",
            },
            cwd=str(_REPO_ROOT),
        )

    @pytest.mark.asyncio
    async def test_initialize_handshake(self, tmp_path: Path):
        """initialize returns server info and tool capabilities (§7.4).

        Note: the negotiated protocolVersion is SDK-version-dependent — the
        mcp client sends its LATEST_PROTOCOL_VERSION (2025-11-25 for mcp 1.28)
        and the server echoes a mutually supported one. We assert it is a
        non-empty string rather than the spec's example pin (2024-11-05), which
        only holds for a raw client explicitly requesting that version.
        """
        params = self._server_params(tmp_path / "handshake.db")
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            init = await session.initialize()
            assert isinstance(init.protocolVersion, str)
            assert len(init.protocolVersion) > 0
            assert init.serverInfo.name == "ai-vibe-memory"
            # Spec §7.4 pins the app version; the server must advertise it
            # (FastMCP(..., version="0.12.0")) rather than the SDK version.
            assert init.serverInfo.version == "0.13.0"
            assert init.capabilities.tools is not None

    @pytest.mark.asyncio
    async def test_tools_list_five_tools(self, tmp_path: Path):
        """tools/list exposes exactly the five memory tools in order."""
        params = self._server_params(tmp_path / "tools.db")
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            assert names == MCP_TOOL_NAMES

    @pytest.mark.asyncio
    async def test_tools_call_memory_stats(self, tmp_path: Path):
        """tools/call memory_stats returns a JSON text block with 'total'."""
        params = self._server_params(tmp_path / "stats.db")
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            result = await session.call_tool("memory_stats", {})
            assert not result.isError, f"memory_stats failed: {result.content}"
            assert result.content
            assert result.content[0].type == "text"
            payload = json.loads(result.content[0].text)
            assert "total" in payload
            assert "max_rows" in payload
            assert "db_path" in payload

    @pytest.mark.asyncio
    async def test_tools_call_unknown_tool_errors(self, tmp_path: Path):
        """An unknown tool name yields an error result (FastMCP default).

        FastMCP answers unknown tools at the framework level (isError=True with
        an 'Unknown tool' text block) — no client-side exception is raised.
        """
        params = self._server_params(tmp_path / "unknown.db")
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            result = await session.call_tool("not_a_real_tool", {})
            assert result.isError is True
            assert result.content
            assert result.content[0].type == "text"
            assert "not_a_real_tool" in result.content[0].text  # type: ignore[union-attr]


class TestClientExampleBehavior:
    """examples.memory_client_example.run_demo — cross-session demo (§8)."""

    def test_run_demo_returns_summary_dict(self, tmp_path: Path):
        """run_demo(tmp_db) returns a dict summarizing the demo."""
        summary = run_demo(tmp_path / "demo.db")
        assert isinstance(summary, dict)
        assert "stored" in summary or "retrieved" in summary
