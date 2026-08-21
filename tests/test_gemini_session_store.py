"""Interface and behavioral tests for GeminiSessionStore.

Tests verify the 4 acceptance criteria from SPEC-RES-6E3C8CB0:
  1. A new session is correctly created and saved.
  2. An existing session is correctly loaded.
  3. Session data is properly isolated between different bug IDs.
  4. The store handles non-existent session files gracefully.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from ai_vibe_coding.gemini_session_store import GeminiSessionStore


# ──────────────────────────────────────────────────────────────
# Interface smoke tests — must PASS immediately
# ──────────────────────────────────────────────────────────────


class TestGeminiSessionStoreInterface:
    """Verify GeminiSessionStore class and method signatures exist."""

    def test_class_exists(self):
        assert GeminiSessionStore is not None
        assert callable(GeminiSessionStore)

    def test_constructor_takes_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = GeminiSessionStore(Path(tmp) / "test.db")
            assert store is not None

    def test_has_create_session(self):
        assert hasattr(GeminiSessionStore, "create_session")

    def test_has_load_session(self):
        assert hasattr(GeminiSessionStore, "load_session")

    def test_has_update_session(self):
        assert hasattr(GeminiSessionStore, "update_session")

    def test_has_list_sessions(self):
        assert hasattr(GeminiSessionStore, "list_sessions")

    def test_has_delete_session(self):
        assert hasattr(GeminiSessionStore, "delete_session")


# ──────────────────────────────────────────────────────────────
# AC1: A new session is correctly created and saved
# ──────────────────────────────────────────────────────────────


class TestCreateSession:
    """AC1 — new sessions are created and persisted."""

    def test_create_returns_session_id(self, tmp_path):
        store = GeminiSessionStore(tmp_path / "s.db")
        sid = store.create_session(bug_id="BUG-001", title="Fix login")
        assert isinstance(sid, str)
        assert len(sid) > 0

    def test_create_stores_bug_id(self, tmp_path):
        store = GeminiSessionStore(tmp_path / "s.db")
        sid = store.create_session(bug_id="BUG-42", title="Test")
        loaded = store.load_session(sid)
        assert loaded["bug_id"] == "BUG-42"

    def test_create_stores_title(self, tmp_path):
        store = GeminiSessionStore(tmp_path / "s.db")
        sid = store.create_session(bug_id="BUG-1", title="My Title")
        loaded = store.load_session(sid)
        assert loaded["title"] == "My Title"

    def test_create_stores_initial_context(self, tmp_path):
        store = GeminiSessionStore(tmp_path / "s.db")
        ctx = {"files": ["a.py", "b.py"], "notes": "start here"}
        sid = store.create_session(bug_id="BUG-1", title="T", context=ctx)
        loaded = store.load_session(sid)
        assert loaded["context"] == ctx

    def test_create_persists_to_disk(self, tmp_path):
        db = tmp_path / "s.db"
        store1 = GeminiSessionStore(db)
        sid = store1.create_session(bug_id="BUG-1", title="T")
        # new store instance on same file
        store2 = GeminiSessionStore(db)
        loaded = store2.load_session(sid)
        assert loaded["bug_id"] == "BUG-1"


# ──────────────────────────────────────────────────────────────
# AC2: An existing session is correctly loaded
# ──────────────────────────────────────────────────────────────


class TestLoadSession:
    """AC2 — existing sessions load with full data."""

    def test_load_returns_dict(self, tmp_path):
        store = GeminiSessionStore(tmp_path / "s.db")
        sid = store.create_session(bug_id="BUG-1", title="T")
        loaded = store.load_session(sid)
        assert isinstance(loaded, dict)

    def test_load_has_all_fields(self, tmp_path):
        store = GeminiSessionStore(tmp_path / "s.db")
        sid = store.create_session(bug_id="BUG-1", title="Title", context={"k": "v"})
        loaded = store.load_session(sid)
        for key in ("session_id", "bug_id", "title", "context", "created_at", "updated_at"):
            assert key in loaded, f"missing key: {key}"

    def test_load_preserves_context(self, tmp_path):
        store = GeminiSessionStore(tmp_path / "s.db")
        ctx = {"prompt": "explain this", "stack": ["python", "sqlite"]}
        sid = store.create_session(bug_id="BUG-1", title="T", context=ctx)
        loaded = store.load_session(sid)
        assert loaded["context"] == ctx

    def test_load_after_update_shows_new_data(self, tmp_path):
        store = GeminiSessionStore(tmp_path / "s.db")
        sid = store.create_session(bug_id="BUG-1", title="Old")
        store.update_session(sid, title="New", context={"step": 2})
        loaded = store.load_session(sid)
        assert loaded["title"] == "New"
        assert loaded["context"] == {"step": 2}


# ──────────────────────────────────────────────────────────────
# AC3: Session data is isolated between different bug IDs
# ──────────────────────────────────────────────────────────────


class TestSessionIsolation:
    """AC3 — sessions for different bug IDs do not leak data."""

    def test_different_bug_ids_different_sessions(self, tmp_path):
        store = GeminiSessionStore(tmp_path / "s.db")
        s1 = store.create_session(bug_id="BUG-10", title="Session A")
        s2 = store.create_session(bug_id="BUG-20", title="Session B")
        assert s1 != s2

    def test_isolated_contexts(self, tmp_path):
        store = GeminiSessionStore(tmp_path / "s.db")
        s1 = store.create_session(bug_id="BUG-10", title="A", context={"secret": "aaa"})
        s2 = store.create_session(bug_id="BUG-20", title="B", context={"secret": "bbb"})
        assert store.load_session(s1)["context"]["secret"] == "aaa"
        assert store.load_session(s2)["context"]["secret"] == "bbb"

    def test_update_one_does_not_affect_other(self, tmp_path):
        store = GeminiSessionStore(tmp_path / "s.db")
        s1 = store.create_session(bug_id="BUG-10", title="A")
        s2 = store.create_session(bug_id="BUG-20", title="B")
        store.update_session(s1, title="Changed")
        assert store.load_session(s1)["title"] == "Changed"
        assert store.load_session(s2)["title"] == "B"

    def test_list_sessions_shows_only_own(self, tmp_path):
        store = GeminiSessionStore(tmp_path / "s.db")
        store.create_session(bug_id="BUG-10", title="A")
        store.create_session(bug_id="BUG-10", title="A2")
        store.create_session(bug_id="BUG-20", title="B")
        bug10 = [s for s in store.list_sessions() if s["bug_id"] == "BUG-10"]
        bug20 = [s for s in store.list_sessions() if s["bug_id"] == "BUG-20"]
        assert len(bug10) == 2
        assert len(bug20) == 1

    def test_delete_one_does_not_affect_other(self, tmp_path):
        store = GeminiSessionStore(tmp_path / "s.db")
        s1 = store.create_session(bug_id="BUG-10", title="A")
        s2 = store.create_session(bug_id="BUG-20", title="B")
        store.delete_session(s1)
        assert store.load_session(s2)["bug_id"] == "BUG-20"


# ──────────────────────────────────────────────────────────────
# AC4: The store handles non-existent session files gracefully
# ──────────────────────────────────────────────────────────────


class TestGracefulMissingSession:
    """AC4 — loading a non-existent session does not crash."""

    def test_load_nonexistent_returns_none(self, tmp_path):
        store = GeminiSessionStore(tmp_path / "s.db")
        result = store.load_session("nonexistent-id-xyz")
        assert result is None

    def test_update_nonexistent_returns_false(self, tmp_path):
        store = GeminiSessionStore(tmp_path / "s.db")
        result = store.update_session("nonexistent-id-xyz", title="X")
        assert result is False

    def test_delete_nonexistent_returns_false(self, tmp_path):
        store = GeminiSessionStore(tmp_path / "s.db")
        result = store.delete_session("nonexistent-id-xyz")
        assert result is False

    def test_store_on_missing_file_creates_db(self, tmp_path):
        db_path = tmp_path / "new_dir" / "s.db"
        store = GeminiSessionStore(db_path)
        sid = store.create_session(bug_id="BUG-1", title="T")
        assert store.load_session(sid)["bug_id"] == "BUG-1"
