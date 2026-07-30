"""Cost tracking and analytics for LLM API calls.

Provides thread-safe cost accumulation, per-provider/per-model breakdowns,
and CSV/JSON export.

Public API:
    CostTracker  — accumulate costs from LLMResponse objects
    CostSummary  — summary dataclass with to_dict() and to_table()
"""

from __future__ import annotations

import csv
import json
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_vibe_coding.llm_wrapper import LLMResponse


@dataclass
class CostSummary:
    """Summary of accumulated LLM costs.

    Attributes:
        total_cost: Total cost in USD across all calls.
        total_tokens: Total tokens consumed across all calls.
        per_provider: Cost breakdown by provider name.
        per_model: Cost breakdown by model name.
        call_count: Number of LLM calls recorded.
    """

    total_cost: float = 0.0
    total_tokens: int = 0
    per_provider: dict[str, float] = field(default_factory=dict)
    per_model: dict[str, float] = field(default_factory=dict)
    call_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to a JSON-serializable dict."""
        return {
            "total_cost": round(self.total_cost, 6),
            "total_tokens": self.total_tokens,
            "per_provider": dict(self.per_provider),
            "per_model": dict(self.per_model),
            "call_count": self.call_count,
        }

    def to_table(self) -> str:
        """Return an aligned ASCII table string of the summary."""
        lines = []
        lines.append("=" * 50)
        lines.append("Cost Summary")
        lines.append("=" * 50)
        lines.append(f"  Total Cost:   ${self.total_cost:.4f}")
        lines.append(f"  Total Tokens: {self.total_tokens}")
        lines.append(f"  Call Count:   {self.call_count}")
        lines.append("-" * 50)
        lines.append("  Per-Provider:")
        for provider, cost in sorted(self.per_provider.items()):
            lines.append(f"    {provider:20s} ${cost:.4f}")
        lines.append("-" * 50)
        lines.append("  Per-Model:")
        for model, cost in sorted(self.per_model.items()):
            lines.append(f"    {model:20s} ${cost:.4f}")
        lines.append("=" * 50)
        return "\n".join(lines)


class CostTracker:
    """Thread-safe cost tracker for LLM API calls.

    Records LLMResponse objects and provides summary/export methods.
    Thread-safe for concurrent async calls.

    Example:
        tracker = CostTracker()
        tracker.record(response)
        summary = tracker.get_summary()
        print(summary.to_table())
        tracker.export_csv("costs.csv")
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._lock = threading.Lock()
        self._records: list[dict[str, Any]] = []
        self._store: Any = None
        self._db_path: str | Path | None = db_path

    def record(self, response: LLMResponse) -> None:
        """Record an LLMResponse and accumulate its cost."""
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "provider": response.provider,
            "model": response.model,
            "tokens_in": response.input_tokens,
            "tokens_out": response.output_tokens,
            "tokens_used": response.tokens_used,
            "cost_usd": response.cost_usd,
            "latency_ms": response.latency_ms,
            "session_id": response.session_id,
            "tags": response.tags,
        }
        with self._lock:
            self._records.append(entry)

    def get_summary(self) -> CostSummary:
        """Return a CostSummary aggregating all recorded responses."""
        with self._lock:
            records = list(self._records)
        total_cost = 0.0
        total_tokens = 0
        per_provider: dict[str, float] = {}
        per_model: dict[str, float] = {}
        for r in records:
            total_cost += r["cost_usd"]
            total_tokens += r["tokens_used"]
            prov = r["provider"]
            model = r["model"]
            per_provider[prov] = per_provider.get(prov, 0.0) + r["cost_usd"]
            per_model[model] = per_model.get(model, 0.0) + r["cost_usd"]
        return CostSummary(
            total_cost=round(total_cost, 6),
            total_tokens=total_tokens,
            per_provider=per_provider,
            per_model=per_model,
            call_count=len(records),
        )

    def export_csv(self, path: str | Path) -> None:
        """Export recorded costs to a CSV file."""
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            records = list(self._records)
        with open(output, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp", "provider", "model",
                    "tokens_in", "tokens_out", "cost_usd",
                ],
            )
            writer.writeheader()
            for r in records:
                writer.writerow(
                    {
                        "timestamp": r["timestamp"],
                        "provider": r["provider"],
                        "model": r["model"],
                        "tokens_in": r["tokens_in"],
                        "tokens_out": r["tokens_out"],
                        "cost_usd": r["cost_usd"],
                    }
                )

    def export_json(self, path: str | Path) -> None:
        """Export summary to a JSON file with nested per-provider structure."""
        summary = self.get_summary()
        with self._lock:
            records = list(self._records)
        data = {
            **summary.to_dict(),
            "records": records,
        }
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            json.dump(data, f, indent=2)

    def set_store(self, store: Any) -> None:
        """Set the SQLite cost store for persistence.

        Args:
            store: An SqliteCostStore instance for persistent storage.
        """
        self._store = store

    def get_store(self) -> Any:
        """Get the current SQLite cost store, if any."""
        return self._store

    def get_daily_cost(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get daily cost breakdown via the cost store.

        Args:
            start_date: Optional start date filter (ISO format).
            end_date: Optional end date filter (ISO format).

        Returns:
            List of dicts with keys: date, total_cost, total_tokens,
            request_count.
        """
        if self._store is not None:
            return self._store.get_daily_rollup(
                start_date=start_date, end_date=end_date
            )
        # Fallback: aggregate from in-memory records
        with self._lock:
            records = list(self._records)
        daily: dict[str, dict[str, Any]] = {}
        for r in records:
            day = r["timestamp"][:10]
            if day not in daily:
                daily[day] = {
                    "date": day,
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "request_count": 0,
                    "avg_latency_ms": 0.0,
                }
            daily[day]["total_cost"] += r["cost_usd"]
            daily[day]["total_tokens"] += r["tokens_in"] + r["tokens_out"]
            daily[day]["request_count"] += 1
        result = sorted(daily.values(), key=lambda d: d["date"])
        # Compute averages
        for d in result:
            if d["request_count"] > 0:
                d["avg_latency_ms"] = (
                    sum(
                        r.get("latency_ms", 0.0)
                        for r in records
                        if r["timestamp"][:10] == d["date"]
                    )
                    / d["request_count"]
                )
        return result

    def get_latency_percentiles(
        self,
        percentile: float = 95.0,
        start_date: str | None = None,
        end_date: str | None = None,
        provider: str | None = None,
    ) -> float:
        """Get latency at the specified percentile via the cost store.

        Args:
            percentile: Percentile to compute (e.g. 95.0 for p95).
            start_date: Optional start date filter (ISO format).
            end_date: Optional end date filter (ISO format).
            provider: Optional provider filter.

        Returns:
            Latency value in milliseconds at the requested percentile.
        """
        if self._store is not None:
            return self._store.get_latency_percentiles(
                percentile=percentile,
                start_date=start_date,
                end_date=end_date,
                provider=provider,
            )
        # Fallback: compute from in-memory records
        with self._lock:
            records = list(self._records)
        values = [
            r.get("latency_ms", 0.0)
            for r in records
            if (start_date is None or r["timestamp"][:10] >= start_date[:10])
            and (end_date is None or r["timestamp"][:10] <= end_date[:10])
            and (provider is None or r["provider"] == provider)
        ]
        if not values:
            return 0.0
        values.sort()
        if percentile >= 100.0:
            return values[-1]
        if percentile <= 0.0:
            return values[0]
        idx = int(len(values) * percentile / 100.0)
        idx = min(idx, len(values) - 1)
        return values[idx]

    def reset(self) -> None:
        """Clear all recorded costs."""
        with self._lock:
            self._records.clear()


__all__ = [
    "CostSummary",
    "CostTracker",
]
