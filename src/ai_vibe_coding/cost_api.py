"""FastAPI router for cost and latency query endpoints.

Provides REST API endpoints for accessing cost store data,
budget alerts, and cost comparisons.

Public API:
    router — FastAPI APIRouter with all cost endpoints
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/costs", tags=["costs"])


@router.get("/total")
async def get_total_cost(
    start_date: str | None = None,
    end_date: str | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """Get total cost for the specified filters.

    Returns {"total_cost": float, "currency": "USD"}.
    """
    raise NotImplementedError


@router.get("/daily")
async def get_daily_costs(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Get daily cost/token breakdown.

    Returns list of dicts with date, total_cost, total_tokens, request_count.
    """
    raise NotImplementedError


@router.get("/by-provider")
async def get_costs_by_provider(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Get cost breakdown by provider."""
    raise NotImplementedError


@router.get("/by-model")
async def get_costs_by_model(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Get cost breakdown by model."""
    raise NotImplementedError


@router.get("/by-user")
async def get_costs_by_user(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Get cost breakdown by session/user."""
    raise NotImplementedError


@router.get("/latency/percentiles")
async def get_latency_percentiles(
    percentile: float = 95.0,
    start_date: str | None = None,
    end_date: str | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    """Get latency at the specified percentile.

    Returns {"percentile": float, "latency_ms": float, "metric": "latency"}.
    """
    raise NotImplementedError


@router.get("/comparison/providers")
async def compare_providers(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Compare costs across providers.

    Returns list of provider comparison dicts.
    """
    raise NotImplementedError


@router.get("/trend")
async def cost_trend(
    granularity: str = "daily",
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Get cost trend data over time."""
    raise NotImplementedError


@router.get("/budget/alerts")
async def get_alert_history(
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Get recent alert history."""
    raise NotImplementedError


@router.post("/budget/check")
async def check_budgets(
    current_spend: float | None = None,
) -> list[dict[str, Any]]:
    """Check all budgets and return any fired alerts."""
    raise NotImplementedError


__all__ = [
    "router",
]
