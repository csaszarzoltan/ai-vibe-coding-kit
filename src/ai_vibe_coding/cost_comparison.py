"""Cost comparison utilities for LLM provider analysis.

Provides functions to compare actual costs across providers,
compare estimated vs actual costs, and generate cost trend data.

Public API:
    compare_actual_costs — compare actual costs across providers
    compare_estimated_vs_actual — compare estimates against real costs
    get_cost_trend — generate time-series cost data
"""

from __future__ import annotations

from typing import Any

from ai_vibe_coding.cost_store import SqliteCostStore
from ai_vibe_coding.llm_wrapper import PRICING


def _get_store(
    db_path: str | None = None,
) -> SqliteCostStore:
    """Get a SqliteCostStore instance, using :memory: as default."""
    return SqliteCostStore(db_path or ":memory:")


def compare_actual_costs(
    start_date: str | None = None,
    end_date: str | None = None,
    providers: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Compare actual costs across providers for a date range.

    Args:
        start_date: Optional start date filter (ISO format).
        end_date: Optional end date filter (ISO format).
        providers: Optional list of providers to include.
                  If None, includes all providers.

    Returns:
        List of dicts sorted by total_cost descending, with keys:
        provider, total_cost, total_tokens, request_count,
        avg_latency_ms, cost_per_1k_tokens.
    """
    store = _get_store()
    rows = store.get_cost_by_provider(
        start_date=start_date, end_date=end_date
    )

    results: list[dict[str, Any]] = []
    for row in rows:
        prov = row["provider"]
        if providers and prov not in providers:
            continue
        total_cost = row["total_cost"]
        total_tokens = row["total_tokens"]
        req_count = row["request_count"]
        cost_per_1k = (
            (total_cost / total_tokens * 1000) if total_tokens > 0 else 0.0
        )
        results.append(
            {
                "provider": prov,
                "total_cost": total_cost,
                "total_tokens": total_tokens,
                "request_count": req_count,
                "avg_latency_ms": row.get("avg_latency_ms", 0.0),
                "cost_per_1k_tokens": cost_per_1k,
            }
        )

    results.sort(key=lambda r: r["total_cost"], reverse=True)
    return results


def compare_estimated_vs_actual(
    start_date: str | None = None,
    end_date: str | None = None,
    providers: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Compare estimated vs actual costs for each provider.

    Estimates use the pricing dict (per-1K-token rates); actuals come
    from the cost store.

    Args:
        start_date: Optional start date filter.
        end_date: Optional end date filter.
        providers: Optional list of providers to include.

    Returns:
        List of dicts with keys: provider, estimated_cost, actual_cost,
        difference, difference_pct, total_tokens.
    """
    store = _get_store()
    rows = store.get_cost_by_provider(
        start_date=start_date, end_date=end_date
    )

    results: list[dict[str, Any]] = []
    for row in rows:
        prov = row["provider"]
        if providers and prov not in providers:
            continue

        actual_cost = row["total_cost"]
        total_tokens = row["total_tokens"]

        # Estimate cost from pricing dict
        estimated_cost = 0.0
        if prov in PRICING:
            # Use the first available model's pricing as a rough estimate
            first_model = next(iter(PRICING[prov].values()), None)
            if first_model and total_tokens > 0:
                # Assume 50/50 input/output split for estimation
                input_est = total_tokens * 0.5 / 1000 * first_model["input"]
                output_est = total_tokens * 0.5 / 1000 * first_model["output"]
                estimated_cost = input_est + output_est

        difference = actual_cost - estimated_cost
        difference_pct = (
            (difference / estimated_cost * 100) if estimated_cost > 0 else 0.0
        )

        results.append(
            {
                "provider": prov,
                "estimated_cost": round(estimated_cost, 6),
                "actual_cost": round(actual_cost, 6),
                "difference": round(difference, 6),
                "difference_pct": round(difference_pct, 4),
                "total_tokens": total_tokens,
            }
        )

    return results


def get_cost_trend(
    granularity: str = "daily",
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Get cost trend data over time.

    Args:
        granularity: "daily", "weekly", or "monthly".
        start_date: Optional start date filter.
        end_date: Optional end date filter.

    Returns:
        List of dicts with keys: period, total_cost, total_tokens,
        request_count, avg_latency_ms.
    """
    store = _get_store()
    rows = store.get_daily_rollup(start_date=start_date, end_date=end_date)

    if granularity == "daily":
        # Already daily
        result = []
        for row in rows:
            result.append(
                {
                    "period": row["date"],
                    "total_cost": row["total_cost"],
                    "total_tokens": row["total_tokens"],
                    "request_count": row["request_count"],
                    "avg_latency_ms": row["avg_latency_ms"],
                }
            )
        return result

    import datetime

    # Aggregate into weekly or monthly buckets
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        dt = datetime.date.fromisoformat(row["date"])
        if granularity == "weekly":
            # ISO week: YYYY-Www
            period = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
        elif granularity == "monthly":
            period = dt.strftime("%Y-%m")
        else:
            period = row["date"]

        if period not in buckets:
            buckets[period] = {
                "period": period,
                "total_cost": 0.0,
                "total_tokens": 0,
                "request_count": 0,
                "avg_latency_ms": 0.0,
            }
        b = buckets[period]
        b["total_cost"] += row["total_cost"]
        b["total_tokens"] += row["total_tokens"]
        b["request_count"] += row["request_count"]
        # Weighted average for latency
        total_prev = b["request_count"] - row["request_count"]
        if b["request_count"] > 0 and total_prev > 0:
            b["avg_latency_ms"] = (
                b["avg_latency_ms"] * total_prev
                + row["avg_latency_ms"] * row["request_count"]
            ) / b["request_count"]
        elif b["request_count"] > 0:
            b["avg_latency_ms"] = row["avg_latency_ms"]

    return [buckets[k] for k in sorted(buckets)]


__all__ = [
    "compare_actual_costs",
    "compare_estimated_vs_actual",
    "get_cost_trend",
]
