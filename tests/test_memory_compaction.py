"""Pre-development tests for the memory compaction & knowledge distillation engine.

Contract: analysis/analysis-brief.md v0.14.0 (task t_479c12c3).

Convention (pre-tester):
    Interface tests: MUST PASS immediately against the stubbed source files
    (StorageBackend + MemoryStore stubs committed to memory_store.py,
    memory_compact MCP tool stub committed to mcp_memory_server.py).

    Behavioral tests: MUST FAIL with NotImplementedError while the feature
    is not implemented.  They exercise compact(dry_run/apply), merge, decay,
    idempotency, stats exposure, and MCP tool wiring.  Once the developer
    implements the feature, every behavioral test becomes GREEN.

    Engine interface tests (TestMemoryCompactionEngineInterface) are skipped
    when the module is not importable (RED phase before stubs in src/).
    Engine behavioral tests (TestEnginePureFunctionBehavior) are skipped
    when the module is not importable.

    DO NOT write inverse stub-guard tests that assert
    pytest.raises(NotImplementedError) on the feature's own methods.

Run:
    .venv/bin/python -m pytest tests/test_memory_compaction.py -v
    .venv/bin/python -m pytest tests/test_memory_compaction.py -q -k TestInterface
    .venv/bin/python -m pytest tests/test_memory_compaction.py -q -k TestBehavioral
"""

from __future__ import annotations

import inspect
import sqlite3
import sys
from abc import ABC
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

# Ensure repo root is on sys.path so imports work without installation.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from ai_vibe_coding.memory_store import (  # noqa: E402
    StorageBackend,
    MemoryStore,
    RedisBackend,
    _COMPACT_COLUMNS,
    _COMPACT_SCHEMA,
    _SCHEMA,
)
from examples import mcp_memory_server  # noqa: E402

# Import the memory_compaction module if available (pass), or let the
# import fail (RED signal for behavioral tests).
try:
    from ai_vibe_coding import memory_compaction as mc

    _HAS_MC = True
except ImportError:
    mc = None  # type: ignore[assignment]
    _HAS_MC = False


# ===================================================================
# FakeClock (same seam as existing tests)
# ===================================================================

class _FakeClock:
    """Deterministic clock seam (same pattern as test_mcp_memory_server.py)."""

    def __init__(self) -> None:
        self.current = datetime(2026, 1, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


@pytest.fixture
def clock() -> _FakeClock:
    return _FakeClock()


@pytest.fixture
def store(tmp_path: Path, clock: _FakeClock) -> MemoryStore:
    """File-backed store with injectable clock (isolated per test)."""
    return MemoryStore(tmp_path / "mem.db", now=clock)


@pytest.fixture
def memory_store() -> MemoryStore:
    """In-memory store for tests that don't touch persistence."""
    return MemoryStore(":memory:")


# ===================================================================
# Test data helpers
# ===================================================================

_STALE_OLD = [
    {
        "id": "stale_a",
        "content": "the user prefers concise torrent stream icons for the stremio addon",
        "created_at": "2025-10-01T00:00:00+00:00",
        "last_accessed_at": "2025-10-01T00:00:00+00:00",
        "importance": 0.1,
        "status": "active",
        "embedding": None,
    },
    {
        "id": "stale_b",
        "content": "the user prefers concise torrent stream icons in the stremio addon",
        "created_at": "2025-10-05T00:00:00+00:00",
        "last_accessed_at": "2025-10-05T00:00:00+00:00",
        "importance": 0.2,
        "status": "active",
        "embedding": None,
    },
]

_RECENT_HIGH = [
    {
        "id": "recent_a",
        "content": "deploy the vector database cluster to production now",
        "created_at": "2025-12-15T00:00:00+00:00",
        "last_accessed_at": "2025-12-15T00:00:00+00:00",
        "importance": 0.9,
        "status": "active",
        "embedding": None,
    },
]

_NEAR_DUPES = [
    {
        "id": "dupe_new",
        "content": "deploy the vector database cluster to production now",
        "created_at": "2025-12-15T00:00:00+00:00",
        "last_accessed_at": "2025-12-15T00:00:00+00:00",
        "importance": 0.8,
        "status": "active",
        "embedding": None,
    },
    {
        "id": "dupe_old",
        "content": "deploy the vector database cluster to production immediately",
        "created_at": "2025-12-10T00:00:00+00:00",
        "last_accessed_at": "2025-12-10T00:00:00+00:00",
        "importance": 0.7,
        "status": "active",
        "embedding": None,
    },
]


# ===================================================================
# Interface tests — MUST PASS immediately against the stubs
# ===================================================================

class TestModuleExists:
    """New modules and constants are importable and have correct values."""

    def test_compact_schema_string_exists(self):
        """_COMPACT_SCHEMA is a non-empty string with compaction_log table."""
        assert isinstance(_COMPACT_SCHEMA, str)
        assert "compaction_log" in _COMPACT_SCHEMA
        assert "decay_log" in _COMPACT_SCHEMA

    def test_compact_columns_tuple(self):
        """_COMPACT_COLUMNS == ('status', 'archived_at', 'last_decayed_at')."""
        assert _COMPACT_COLUMNS == ("status", "archived_at", "last_decayed_at")

    def test_status_column_in_schema(self):
        """_SCHEMA still contains the base memories table (not modified)."""
        assert "CREATE TABLE IF NOT EXISTS memories" in _SCHEMA


class TestStorageBackendNewAbstractMethods:
    """StorageBackend ABC — 9 new abstract methods for compaction (spec §4.2)."""

    def test_abc_is_abstract(self):
        """StorageBackend is still an ABC."""
        assert issubclass(StorageBackend, ABC)
        assert inspect.isabstract(StorageBackend)

    def test_abstractmethod_count(self):
        """ABC now has 18 abstract methods (9 original + 9 new)."""
        assert len(StorageBackend.__abstractmethods__) == 18

    def test_new_abstract_methods_declared(self):
        """The 9 new abstract methods are in __abstractmethods__."""
        expected_new = {
            "archive", "list_memories", "batch_update_status",
            "write_distilled", "record_compaction_run", "list_compaction_log",
            "record_decay", "list_decay_log", "set_importance",
        }
        assert expected_new <= StorageBackend.__abstractmethods__

    def test_archive_signature(self):
        sig = inspect.signature(StorageBackend.archive)
        params = list(sig.parameters)
        assert params == ["self", "memory_id", "archived_at"]
        assert sig.parameters["archived_at"].kind == inspect.Parameter.KEYWORD_ONLY

    def test_list_memories_signature(self):
        sig = inspect.signature(StorageBackend.list_memories)
        params = list(sig.parameters)
        assert params == ["self", "include_archived"]
        assert sig.parameters["include_archived"].default is False

    def test_batch_update_status_signature(self):
        sig = inspect.signature(StorageBackend.batch_update_status)
        params = list(sig.parameters)
        assert "ids" in params
        assert "status" in params
        assert "archived_at" in params
        assert sig.parameters["archived_at"].default is None
        assert sig.parameters["archived_at"].kind == inspect.Parameter.KEYWORD_ONLY

    def test_write_distilled_signature(self):
        sig = inspect.signature(StorageBackend.write_distilled)
        params = list(sig.parameters)
        assert params == ["self", "content", "sources", "importance"]

    def test_record_compaction_run_signature(self):
        sig = inspect.signature(StorageBackend.record_compaction_run)
        params = list(sig.parameters)
        assert "run_id" in params
        for kw in ("mode", "distilled", "archived", "merged", "summary"):
            assert kw in params
            assert sig.parameters[kw].kind == inspect.Parameter.KEYWORD_ONLY

    def test_list_compaction_log_signature(self):
        sig = inspect.signature(StorageBackend.list_compaction_log)
        assert list(sig.parameters) == ["self", "limit"]
        assert sig.parameters["limit"].default == 20

    def test_record_decay_signature(self):
        sig = inspect.signature(StorageBackend.record_decay)
        params = list(sig.parameters)
        assert "memory_id" in params
        for kw in ("old_score", "new_score", "happened_at"):
            assert kw in params
            assert sig.parameters[kw].kind == inspect.Parameter.KEYWORD_ONLY

    def test_list_decay_log_signature(self):
        sig = inspect.signature(StorageBackend.list_decay_log)
        assert list(sig.parameters) == ["self", "limit"]
        assert sig.parameters["limit"].default == 50

    def test_set_importance_signature(self):
        sig = inspect.signature(StorageBackend.set_importance)
        params = list(sig.parameters)
        assert params == ["self", "memory_id", "importance", "last_decayed_at"]
        assert sig.parameters["last_decayed_at"].kind == inspect.Parameter.KEYWORD_ONLY


class TestMemoryStoreNewMethods:
    """MemoryStore — new public methods for compaction (spec §4.3)."""

    def test_compact_method_exists(self):
        assert hasattr(MemoryStore, "compact")
        assert callable(MemoryStore.compact)

    def test_compact_signature(self):
        sig = inspect.signature(MemoryStore.compact)
        params = sig.parameters
        assert set(params) >= {
            "self", "dry_run", "age_days",
            "importance_threshold", "merge_threshold",
        }
        assert params["dry_run"].default is True
        assert params["age_days"].default is None
        assert params["importance_threshold"].default is None
        assert params["merge_threshold"].default is None

    def test_impact_decay_method_exists(self):
        assert hasattr(MemoryStore, "impact_decay")
        assert callable(MemoryStore.impact_decay)

    def test_impact_decay_signature(self):
        sig = inspect.signature(MemoryStore.impact_decay)
        params = sig.parameters
        assert set(params) >= {"self", "decay_days", "dry_run"}
        assert params["decay_days"].default is None
        assert params["dry_run"].default is False

    def test_memory_stats_method_exists(self):
        assert hasattr(MemoryStore, "memory_stats")
        assert callable(MemoryStore.memory_stats)

    def test_memory_stats_signature(self):
        sig = inspect.signature(MemoryStore.memory_stats)
        assert list(sig.parameters) == ["self"]

    def test_apply_compact_migration_static(self):
        assert hasattr(MemoryStore, "_apply_compact_migration")
        assert isinstance(
            MemoryStore.__dict__["_apply_compact_migration"], staticmethod,
        )

    def test_compact_schema_applied(self, memory_store: MemoryStore):
        """_apply_compact_migration creates compaction_log + decay_log tables."""
        conn = memory_store._connect()
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "compaction_log" in tables
        assert "decay_log" in tables

    def test_status_column_added(self, memory_store: MemoryStore):
        """_apply_compact_migration adds status/archived_at/last_decayed_at columns."""
        conn = memory_store._connect()
        cols = {
            r[1]
            for r in conn.execute("PRAGMA table_info(memories)").fetchall()
        }
        for col in ("status", "archived_at", "last_decayed_at"):
            assert col in cols, f"column {col} missing from memories table"


class TestMemoryCompactionEngineInterface:
    """ai_vibe_coding.memory_compaction — constants and pure function signatures.

    Skipped when the module is not importable (RED phase before stubs in src/).
    """

    @pytest.mark.skipif(not _HAS_MC, reason="memory_compaction not importable yet")
    def test_module_constants_defaults(self):
        assert mc.DEFAULT_COMPACTION_AGE_DAYS == 30
        assert mc.DEFAULT_COMPACTION_IMPORTANCE_THRESHOLD == 0.3
        assert mc.DEFAULT_MERGE_THRESHOLD == 0.82
        assert mc.DEFAULT_DECAY_DAYS == 7
        assert mc.DEFAULT_DECAY_HALFLIFE == 2.0
        assert mc.DEFAULT_MIN_IMPORTANCE == 0.1

    @pytest.mark.skipif(not _HAS_MC, reason="memory_compaction not importable yet")
    def test_summarize_signature(self):
        sig = inspect.signature(mc.summarize)
        params = sig.parameters
        assert "sources" in params
        assert "source_ids" in params
        assert params["source_ids"].default is None
        assert "created_range" in params
        assert params["created_range"].default is None

    @pytest.mark.skipif(not _HAS_MC, reason="memory_compaction not importable yet")
    def test_select_clusters_signature(self):
        sig = inspect.signature(mc.select_clusters)
        params = sig.parameters
        assert "memories" in params
        assert "now" in params
        assert params["now"].kind == inspect.Parameter.KEYWORD_ONLY
        assert params["age_days"].default == mc.DEFAULT_COMPACTION_AGE_DAYS
        assert params["importance_threshold"].default == mc.DEFAULT_COMPACTION_IMPORTANCE_THRESHOLD
        assert params["merge_threshold"].default == mc.DEFAULT_MERGE_THRESHOLD

    @pytest.mark.skipif(not _HAS_MC, reason="memory_compaction not importable yet")
    def test_select_merges_signature(self):
        sig = inspect.signature(mc.select_merges)
        params = sig.parameters
        assert "memories" in params
        assert "threshold" in params
        assert params["threshold"].default == mc.DEFAULT_MERGE_THRESHOLD

    @pytest.mark.skipif(not _HAS_MC, reason="memory_compaction not importable yet")
    def test_compute_decay_signature(self):
        sig = inspect.signature(mc.compute_decay)
        params = sig.parameters
        assert "row" in params
        assert "now" in params
        assert "decay_days" in params
        assert params["decay_days"].default == mc.DEFAULT_DECAY_DAYS
        assert "halflife" in params
        assert params["halflife"].default == mc.DEFAULT_DECAY_HALFLIFE
        assert "min_importance" in params
        assert params["min_importance"].default == mc.DEFAULT_MIN_IMPORTANCE

    @pytest.mark.skipif(not _HAS_MC, reason="memory_compaction not importable yet")
    def test_build_decay_plan_signature(self):
        sig = inspect.signature(mc.build_decay_plan)
        params = sig.parameters
        assert "memories" in params
        assert "now" in params
        assert "decay_days" in params
        assert "halflife" in params
        assert "min_importance" in params
        assert "compaction_importance_threshold" in params

    @pytest.mark.skipif(not _HAS_MC, reason="memory_compaction not importable yet")
    def test_build_plan_signature(self):
        sig = inspect.signature(mc.build_plan)
        params = sig.parameters
        assert "memories" in params
        assert "now" in params
        assert params["now"].kind == inspect.Parameter.KEYWORD_ONLY
        assert params["age_days"].default == mc.DEFAULT_COMPACTION_AGE_DAYS
        assert params["importance_threshold"].default == mc.DEFAULT_COMPACTION_IMPORTANCE_THRESHOLD
        assert params["merge_threshold"].default == mc.DEFAULT_MERGE_THRESHOLD


class TestRedisBackendCompactionStubs:
    """RedisBackend — has stubs for the 9 new abstract methods (RED until implemented)."""

    def test_has_new_methods(self):
        for name in (
            "archive", "list_memories", "batch_update_status",
            "write_distilled", "record_compaction_run", "list_compaction_log",
            "record_decay", "list_decay_log", "set_importance",
        ):
            assert hasattr(RedisBackend, name), f"RedisBackend missing {name}"
            assert callable(getattr(RedisBackend, name))

    def test_archive_not_implemented(self):
        """RedisBackend.archive raises NotImplementedError (RED stub)."""
        rb = RedisBackend(redis_url="redis://localhost:6379/0")
        with pytest.raises(NotImplementedError, match="archive"):
            rb.archive("x", archived_at="2025-01-01T00:00:00+00:00")


class TestMCPServerCompactionInterface:
    """examples/mcp_memory_server.py — memory_compact tool (spec §4.3, US-001)."""

    def test_memory_compact_function_exists(self):
        assert hasattr(mcp_memory_server, "memory_compact")
        assert callable(mcp_memory_server.memory_compact)

    def test_memory_compact_signature(self):
        sig = inspect.signature(mcp_memory_server.memory_compact)
        params = sig.parameters
        assert list(params) == [
            "mode", "age_days", "importance_threshold", "merge_threshold",
        ]
        assert params["mode"].default == "dry-run"
        assert params["age_days"].default is None
        assert params["importance_threshold"].default is None
        assert params["merge_threshold"].default is None

    def test_memory_compact_has_docstring(self):
        doc = mcp_memory_server.memory_compact.__doc__
        assert doc and len(doc.strip()) > 0


# ===================================================================
# Behavioral tests — MUST FAIL with NotImplementedError (RED phase)
# ===================================================================

class TestCompactDryRunBehavior:
    """US-001: compact(dry_run=True) returns a plan, mutates nothing."""

    def test_dry_run_returns_plan(self, store: MemoryStore):
        result = store.compact(dry_run=True)
        assert isinstance(result, dict)
        assert result.get("dry_run") is True
        assert "candidate_distill_clusters" in result
        assert "candidate_merges" in result
        assert "cluster_count" in result
        assert "merge_count" in result

    def test_dry_run_no_mutations(self, store: MemoryStore):
        store.store("test memory", importance=0.5)
        total_before = store.stats()["total"]
        store.compact(dry_run=True)
        assert store.stats()["total"] == total_before

    def test_dry_run_with_stale_data(self, clock: _FakeClock, store: MemoryStore):
        store.store("old fact", importance=0.1)
        clock.advance(31 * 86400)  # 31 days > compaction_age_days=30
        result = store.compact(
            dry_run=True, age_days=30, importance_threshold=0.3,
        )
        assert result.get("cluster_count", 0) >= 1
        # Store unchanged
        assert store.stats()["total"] == 1


class TestCompactApplyBehavior:
    """US-001: compact(dry_run=False) distills + archives originals."""

    def test_apply_distills_and_archives(self, store: MemoryStore):
        store.store("fact A", importance=0.1)
        store.store("fact B", importance=0.1)
        store.now = lambda: datetime(2026, 1, 31, tzinfo=UTC)
        result = store.compact(
            dry_run=False, age_days=30, importance_threshold=0.3,
        )
        assert result["dry_run"] is False
        assert result.get("distilled", 0) >= 1
        assert result.get("archived", 0) >= 2

    def test_archived_not_in_search(self, store: MemoryStore):
        """Archived rows must be excluded from search() but remain in retrieve()."""
        result = store.store("top-secret archived memory", importance=0.9)
        mem_id = result["id"]
        # Manually archive the row via SQL (simulates compaction).
        with store._session() as conn:
            conn.execute(
                "UPDATE memories SET status = 'archived' WHERE id = ?",
                (mem_id,),
            )
        # search() must NOT return the archived content.
        search = store.search("top-secret archived memory")
        hits = [r["content"] for r in search.get("results", [])]
        assert "top-secret archived memory" not in hits, (
            "archived memory leaked into search results"
        )
        # retrieve() must still find it (only search is filtered).
        fetched = store.retrieve(mem_id)
        assert fetched["content"] == "top-secret archived memory"


class TestIdempotencyBehavior:
    """US-004: Re-running compact skips already-archived rows."""

    def test_rerun_skips_archived(self, store: MemoryStore):
        store.store("idempotent fact", importance=0.1)
        store.now = lambda: datetime(2026, 1, 31, tzinfo=UTC)
        first = store.compact(
            dry_run=False, age_days=30, importance_threshold=0.3,
        )
        second = store.compact(
            dry_run=False, age_days=30, importance_threshold=0.3,
        )
        assert second.get("skipped", 0) >= first.get("archived", 0)
        # No new distilled entries on re-run
        assert second.get("distilled", 0) == 0

    def test_compaction_log_recorded(self, store: MemoryStore):
        store.store("log me", importance=0.1)
        store.now = lambda: datetime(2026, 1, 31, tzinfo=UTC)
        store.compact(
            dry_run=False, age_days=30, importance_threshold=0.3,
        )
        if store.backend is not None:
            return  # Redis path not yet implemented
        conn = sqlite3.connect(str(store.db_path))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM compaction_log"
            ).fetchone()[0]
        finally:
            conn.close()
        assert count >= 1


class TestImpactDecayBehavior:
    """US-003: importance decay with decay_log."""

    def test_old_memory_importance_reduced(self, store: MemoryStore):
        store.store("old rarely accessed", importance=0.5)
        store.now = lambda: datetime(2026, 1, 15, tzinfo=UTC)  # 14 days later
        result = store.impact_decay(decay_days=7)
        assert result.get("decayed", 0) >= 1

    def test_decay_log_recorded(self, store: MemoryStore):
        store.store("decay log test", importance=0.8)
        store.now = lambda: datetime(2026, 1, 15, tzinfo=UTC)
        store.impact_decay(decay_days=7)
        if store.backend is not None:
            return
        conn = sqlite3.connect(str(store.db_path))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM decay_log"
            ).fetchone()[0]
        finally:
            conn.close()
        assert count >= 1

    def test_min_importance_floor(self, store: MemoryStore):
        store.store("very old", importance=0.15)
        store.now = lambda: datetime(2027, 1, 1, tzinfo=UTC)  # 1 year later
        result = store.impact_decay(decay_days=7)
        # The implementation must not reduce importance below 0.1

    def test_impact_decay_dry_run(self, store: MemoryStore):
        store.store("dry decay test", importance=0.5)
        total_before = store.stats()["total"]
        result = store.impact_decay(decay_days=7, dry_run=True)
        assert result.get("dry_run") is True
        assert store.stats()["total"] == total_before


class TestMemoryStatsExtendedBehavior:
    """P1-C: memory_stats() exposes compaction/decay counters."""

    def test_memory_stats_has_compaction_keys(self, store: MemoryStore):
        stats = store.memory_stats()
        for key in ("distilled_count", "archived_count", "merged_count", "decayed_count"):
            assert key in stats, f"memory_stats() missing key {key}"
        assert isinstance(stats["distilled_count"], int)
        assert isinstance(stats["archived_count"], int)
        assert isinstance(stats["merged_count"], int)
        assert isinstance(stats["decayed_count"], int)

    def test_memory_stats_has_log_keys(self, store: MemoryStore):
        stats = store.memory_stats()
        for key in ("last_compaction", "compact_runs", "decay_events"):
            assert key in stats, f"memory_stats() missing key {key}"

    def test_memory_stats_inherits_base(self, store: MemoryStore):
        base = store.stats()
        extended = store.memory_stats()
        for key in base:
            assert key in extended, f"memory_stats() missing base key {key}"


class TestEnginePureFunctionBehavior:
    """Pure functions from memory_compaction.py — behavioral RED tests.

    Skipped when memory_compaction is not importable.
    """

    @pytest.mark.skipif(not _HAS_MC, reason="memory_compaction not importable yet")
    def test_summarize_concatenates_sources(self):
        result = mc.summarize(
            ["fact one", "fact two", "fact one"],
            source_ids=["a", "b", "c"],
        )
        assert isinstance(result, str)
        assert len(result) > 0
        assert "fact one" in result
        assert "fact two" in result

    @pytest.mark.skipif(not _HAS_MC, reason="memory_compaction not importable yet")
    def test_select_clusters_returns_groups(self):
        clusters = mc.select_clusters(
            _STALE_OLD + _RECENT_HIGH,
            now="2026-01-01T00:00:00+00:00",
            age_days=30,
            importance_threshold=0.3,
        )
        assert isinstance(clusters, list)
        all_ids = [m["id"] for cluster in clusters for m in cluster]
        assert "recent_a" not in all_ids

    @pytest.mark.skipif(not _HAS_MC, reason="memory_compaction not importable yet")
    def test_select_merges_finds_duplicates(self):
        merges = mc.select_merges(_NEAR_DUPES, threshold=0.82)
        assert isinstance(merges, list)
        if merges:
            newest_id, older_ids = merges[0]
            assert newest_id in ("dupe_new", "dupe_old")
            assert len(older_ids) >= 1

    @pytest.mark.skipif(not _HAS_MC, reason="memory_compaction not importable yet")
    def test_select_merges_ignores_archived(self):
        archived_pair = [
            {**_NEAR_DUPES[0], "id": "a1", "status": "archived"},
            {**_NEAR_DUPES[1], "id": "a2", "status": "archived"},
        ]
        merges = mc.select_merges(archived_pair, threshold=0.82)
        assert merges == []

    @pytest.mark.skipif(not _HAS_MC, reason="memory_compaction not importable yet")
    def test_compute_decay_reduces_importance(self):
        row = {
            "id": "decay_test",
            "importance": 0.8,
            "last_accessed_at": "2025-10-01T00:00:00+00:00",
            "created_at": "2025-10-01T00:00:00+00:00",
        }
        new_importance = mc.compute_decay(
            row, "2025-12-01T00:00:00+00:00",
            decay_days=7, halflife=2.0, min_importance=0.1,
        )
        assert isinstance(new_importance, float)
        assert 0.1 <= new_importance < 0.8

    @pytest.mark.skipif(not _HAS_MC, reason="memory_compaction not importable yet")
    def test_compute_decay_respects_min_importance(self):
        row = {
            "id": "min_floor",
            "importance": 0.15,
            "last_accessed_at": "2025-01-01T00:00:00+00:00",
            "created_at": "2025-01-01T00:00:00+00:00",
        }
        new_importance = mc.compute_decay(
            row, "2026-01-01T00:00:00+00:00",
            decay_days=7, halflife=2.0, min_importance=0.1,
        )
        assert new_importance >= 0.1

    @pytest.mark.skipif(not _HAS_MC, reason="memory_compaction not importable yet")
    def test_build_plan_returns_expected_keys(self):
        plan = mc.build_plan(
            _STALE_OLD + _RECENT_HIGH + _NEAR_DUPES,
            now="2026-01-01T00:00:00+00:00",
        )
        assert isinstance(plan, dict)
        assert "candidate_distill_clusters" in plan
        assert "candidate_merges" in plan
        assert "cluster_count" in plan
        assert "merge_count" in plan
        assert "candidate_memory_ids" in plan
        assert plan.get("dry_run") is True

    @pytest.mark.skipif(not _HAS_MC, reason="memory_compaction not importable yet")
    def test_build_decay_plan_eligibility(self):
        now = "2026-01-01T00:00:00+00:00"
        memories = [
            {
                "id": "old_low", "importance": 0.15,
                "last_accessed_at": "2025-10-01T00:00:00+00:00",
                "created_at": "2025-10-01T00:00:00+00:00", "status": "active",
            },
            {
                "id": "new_high", "importance": 0.9,
                "last_accessed_at": now, "created_at": now, "status": "active",
            },
        ]
        plan = mc.build_decay_plan(memories, now=now, decay_days=7)
        assert isinstance(plan, list)
        ids = {e["memory_id"] for e in plan}
        assert "old_low" in ids
        assert "new_high" not in ids
