"""SQLite-backed session store for Gemini CLI bug-investigation sessions.

Each session is keyed by a unique session_id and scoped to a bug_id,
ensuring isolation between concurrent investigations.  The store creates
the database directory if needed and handles missing sessions gracefully
(returning None / False instead of raising).

Public API:
    GeminiSessionStore — create, load, update, list, delete sessions
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any


class GeminiSessionStore:
    """SQLite persistence for Gemini CLI investigation sessions.

    Args:
        db_path: Path to the SQLite database file. Parent directories
                 are created automatically. Use ``":memory:"`` for tests.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path) if str(db_path) != ":memory:" else ":memory:"
        self._mem_conn: sqlite3.Connection | None = None
        self._init_db()

    # ── connection helpers ───────────────────────────────────

    def _init_db(self) -> None:
        parent = self.db_path.parent
        if parent != Path("."):
            parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    bug_id     TEXT NOT NULL,
                    title      TEXT NOT NULL DEFAULT '',
                    context    TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_bug
                    ON sessions(bug_id);
                """
            )

    def _conn(self) -> sqlite3.Connection:
        if self.db_path == ":memory:":
            if self._mem_conn is None:
                db = sqlite3.connect(":memory:", timeout=10)
                db.row_factory = sqlite3.Row
                self._mem_conn = db
            return self._mem_conn
        db = sqlite3.connect(str(self.db_path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        return db

    # ── row → dict helper ───────────────────────────────────

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["context"] = json.loads(d["context"])
        return d

    # ── create ──────────────────────────────────────────────

    def create_session(
        self,
        bug_id: str,
        title: str = "",
        context: dict[str, Any] | None = None,
    ) -> str:
        """Create a new session and return its session_id."""
        sid = uuid.uuid4().hex
        with self._conn() as db:
            db.execute(
                """INSERT INTO sessions (session_id, bug_id, title, context)
                   VALUES (?, ?, ?, ?)""",
                (sid, bug_id, title, json.dumps(context or {})),
            )
        return sid

    # ── load ────────────────────────────────────────────────

    def load_session(self, session_id: str) -> dict[str, Any] | None:
        """Load a session by id. Returns None if not found."""
        with self._conn() as db:
            row = db.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    # ── update ──────────────────────────────────────────────

    def update_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Update fields of an existing session. Returns False if not found."""
        with self._conn() as db:
            existing = db.execute(
                "SELECT session_id FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if existing is None:
                return False
            if title is not None:
                db.execute(
                    "UPDATE sessions SET title = ?, updated_at = datetime('now') WHERE session_id = ?",
                    (title, session_id),
                )
            if context is not None:
                db.execute(
                    "UPDATE sessions SET context = ?, updated_at = datetime('now') WHERE session_id = ?",
                    (json.dumps(context), session_id),
                )
        return True

    # ── list ────────────────────────────────────────────────

    def list_sessions(self, bug_id: str | None = None) -> list[dict[str, Any]]:
        """List sessions, optionally filtered by bug_id."""
        with self._conn() as db:
            if bug_id is not None:
                rows = db.execute(
                    "SELECT * FROM sessions WHERE bug_id = ? ORDER BY created_at DESC",
                    (bug_id,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM sessions ORDER BY created_at DESC"
                ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ── delete ──────────────────────────────────────────────

    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns False if not found."""
        with self._conn() as db:
            cursor = db.execute(
                "DELETE FROM sessions WHERE session_id = ?", (session_id,)
            )
        return cursor.rowcount > 0
