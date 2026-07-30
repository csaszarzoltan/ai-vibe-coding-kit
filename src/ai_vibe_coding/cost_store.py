"""SQLite-based cost persistence for LLM API calls.

Provides SQLite-backed storage for cost tracking with daily rollups,
pricing tables, and latency percentiles.

Public API:
    SqliteCostStore — SQLite persistence for cost records
    CostPricingTable — pricing data management
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _ensure_tables(db: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS cost_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd REAL NOT NULL DEFAULT 0.0,
            latency_ms REAL NOT NULL DEFAULT 0.0,
            session_id TEXT,
            tags TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS daily_rollup (
            date TEXT NOT NULL PRIMARY KEY,
            total_cost REAL NOT NULL DEFAULT 0.0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            request_count INTEGER NOT NULL DEFAULT 0,
            avg_latency_ms REAL NOT NULL DEFAULT 0.0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_cost_log_provider ON cost_log(provider);
        CREATE INDEX IF NOT EXISTS idx_cost_log_model ON cost_log(model);
        CREATE INDEX IF NOT EXISTS idx_cost_log_created ON cost_log(created_at);
        CREATE INDEX IF NOT EXISTS idx_cost_log_session ON cost_log(session_id);
    """)


@dataclass
class CostPricingTable:
    """Manages per-model pricing data in the cost store.

    Attributes:
        pricing: Nested dict of provider -> model -> {input, output} rates.
    """

    pricing: dict[str, dict[str, dict[str, float]]]

    def upsert_pricing(
        self, provider: str, model: str, input_rate: float, output_rate: float
    ) -> None:
        """Insert or update pricing for a provider/model combination."""
        if provider not in self.pricing:
            self.pricing[provider] = {}
        self.pricing[provider][model] = {
            "input": input_rate,
            "output": output_rate,
        }

    def get_pricing(
        self, provider: str, model: str
    ) -> dict[str, float] | None:
        """Get pricing for a specific provider/model.

        Returns {"input": float, "output": float} or None if not found.
        """
        if provider not in self.pricing:
            return None
        return self.pricing[provider].get(model)

    def seed_from_pricing_dict(
        self, pricing: dict[str, dict[str, dict[str, float]]]
    ) -> int:
        """Bulk seed pricing from a pricing dict (like llm_wrapper.PRICING).

        Returns number of pricing entries inserted.
        """
        count = 0
        for provider, models in pricing.items():
            if provider not in self.pricing:
                self.pricing[provider] = {}
            for model, rates in models.items():
                self.pricing[provider][model] = {
                    "input": rates["input"],
                    "output": rates["output"],
                }
                count += 1
        return count


class SqliteCostStore:
    """SQLite-backed persistence for LLM cost records.

    Manages the cost_log table and provides time-windowed queries.

    For :memory: databases, keeps a single persistent connection so that
    all queries within the same instance see the same data. For file-based
    databases, opens a fresh connection per query for simplicity.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialize the store with a SQLite database path."""
        self.db_path = Path(db_path) if str(db_path) != ":memory:" else ":memory:"
        self._mem_conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """Ensure the database and tables exist."""
        with self._conn() as db:
            _ensure_tables(db)

    def _conn(self) -> sqlite3.Connection:
        """Open a connection.

        For :memory: databases, reuse a single persistent connection.
        For file-based databases, open a fresh connection per call.
        """
        if self.db_path == ":memory:":
            if self._mem_conn is None:
                db = sqlite3.connect(":memory:", timeout=10)
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA journal_mode=WAL")
                self._mem_conn = db
            return self._mem_conn
        db = sqlite3.connect(str(self.db_path), timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def record_request(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        latency_ms: float,
        session_id: str | None = None,
        tags: dict[str, Any] | None = None,
    ) -> int:
        """Record an LLM request in the database.

        Returns the row id of the inserted record.
        """
        with self._conn() as db:
            cursor = db.execute(
                """INSERT INTO cost_log
                   (provider, model, input_tokens, output_tokens,
                    cost_usd, latency_ms, session_id, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    provider,
                    model,
                    input_tokens,
                    output_tokens,
                    cost_usd,
                    latency_ms,
                    session_id,
                    json.dumps(tags) if tags else None,
                ),
            )
            # Return the inserted row id
            return cursor.lastrowid  # type: ignore[return-value]

    def get_daily_rollup(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> list[dict[str, Any]]:
        """Get daily aggregated cost/token data.

        Returns list of dicts with keys: date, total_cost, total_tokens,
        request_count, avg_latency_ms.
        """
        query = """
            SELECT
                date(created_at) AS date,
                SUM(cost_usd) AS total_cost,
                SUM(input_tokens + output_tokens) AS total_tokens,
                COUNT(*) AS request_count,
                AVG(latency_ms) AS avg_latency_ms
            FROM cost_log
            WHERE 1=1
        """
        params: list[Any] = []
        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND created_at <= ?"
            params.append(f"{end_date}T23:59:59")
        query += " GROUP BY date(created_at) ORDER BY date ASC"
        with self._conn() as db:
            rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_total_cost(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        provider: str | None = None,
    ) -> float:
        """Get total cost for the given filters."""
        query = "SELECT COALESCE(SUM(cost_usd), 0.0) AS total FROM cost_log WHERE 1=1"
        params: list[Any] = []
        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND created_at <= ?"
            params.append(f"{end_date}T23:59:59")
        if provider:
            query += " AND provider = ?"
            params.append(provider)
        with self._conn() as db:
            row = db.execute(query, params).fetchone()
        return float(row["total"]) if row else 0.0

    def get_latency_percentiles(
        self,
        percentile: float = 95.0,
        start_date: str | None = None,
        end_date: str | None = None,
        provider: str | None = None,
    ) -> float:
        """Get latency at the given percentile.

        Fetches all matching latencies and computes the percentile in Python.

        Args:
            percentile: Percentile to compute (e.g. 95.0 for p95).
            start_date: Optional start date filter (ISO format).
            end_date: Optional end date filter (ISO format).
            provider: Optional provider filter.

        Returns:
            Latency value in milliseconds at the requested percentile.
        """
        query = "SELECT latency_ms FROM cost_log WHERE 1=1"
        params: list[Any] = []
        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND created_at <= ?"
            params.append(f"{end_date}T23:59:59")
        if provider:
            query += " AND provider = ?"
            params.append(provider)
        query += " ORDER BY latency_ms ASC"
        with self._conn() as db:
            rows = db.execute(query, params).fetchall()
        if not rows:
            return 0.0
        values = [r["latency_ms"] for r in rows]
        if percentile >= 100.0:
            return values[-1]
        if percentile <= 0.0:
            return values[0]
        idx = int(len(values) * percentile / 100.0)
        idx = min(idx, len(values) - 1)
        return values[idx]

    def _run_query_with_filters(
        self,
        group_col: str,
        select_cols: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run a grouped cost query with optional date filters."""
        query = f"""
            SELECT
                {select_cols}
            FROM cost_log
            WHERE 1=1
        """
        params: list[Any] = []
        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND created_at <= ?"
            params.append(f"{end_date}T23:59:59")
        query += f" GROUP BY {group_col} ORDER BY total_cost DESC"
        with self._conn() as db:
            rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_cost_by_model(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get cost breakdown by model.

        Returns list of dicts with keys: model, total_cost, total_tokens,
        request_count.
        """
        return self._run_query_with_filters(
            group_col="model",
            select_cols="""model,
                           COALESCE(SUM(cost_usd), 0.0) AS total_cost,
                           COALESCE(SUM(input_tokens + output_tokens),
                                    0) AS total_tokens,
                           COUNT(*) AS request_count""",
            start_date=start_date,
            end_date=end_date,
        )

    def get_cost_by_provider(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get cost breakdown by provider.

        Returns list of dicts with keys: provider, total_cost, total_tokens,
        request_count.
        """
        return self._run_query_with_filters(
            group_col="provider",
            select_cols="""provider,
                           COALESCE(SUM(cost_usd), 0.0) AS total_cost,
                           COALESCE(SUM(input_tokens + output_tokens),
                                    0) AS total_tokens,
                           COUNT(*) AS request_count""",
            start_date=start_date,
            end_date=end_date,
        )

    def get_cost_by_user(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get cost breakdown by session/user (via session_id).

        Returns list of dicts with keys: session_id, total_cost,
        total_tokens, request_count.
        """
        return self._run_query_with_filters(
            group_col="session_id",
            select_cols="""COALESCE(session_id, 'unknown') AS session_id,
                           COALESCE(SUM(cost_usd), 0.0) AS total_cost,
                           COALESCE(SUM(input_tokens + output_tokens),
                                    0) AS total_tokens,
                           COUNT(*) AS request_count""",
            start_date=start_date,
            end_date=end_date,
        )

    def run_daily_rollup(self) -> dict[str, Any]:
        """Run daily rollup computation and cache results.

        Aggregates today's cost_log data into the daily_rollup table.

        Returns summary dict of the rollup operation.
        """
        with self._conn() as db:
            today = time.strftime("%Y-%m-%d")
            rows = db.execute(
                """SELECT
                       date(created_at) AS date,
                       SUM(cost_usd) AS total_cost,
                       SUM(input_tokens + output_tokens) AS total_tokens,
                       COUNT(*) AS request_count,
                       AVG(latency_ms) AS avg_latency_ms
                   FROM cost_log
                   GROUP BY date(created_at)"""
            ).fetchall()

            inserted = 0
            for row in rows:
                db.execute(
                    """INSERT OR REPLACE INTO daily_rollup
                       (date, total_cost, total_tokens, request_count,
                        avg_latency_ms, updated_at)
                       VALUES (?, ?, ?, ?, ?, datetime('now'))""",
                    (
                        row["date"],
                        row["total_cost"],
                        row["total_tokens"],
                        row["request_count"],
                        row["avg_latency_ms"],
                    ),
                )
                inserted += 1

        return {
            "date": today,
            "records_processed": len(rows),
            "dates_rolled_up": inserted,
        }


__all__ = [
    "CostPricingTable",
    "SqliteCostStore",
]
