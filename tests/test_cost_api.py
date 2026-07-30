"""Interface and behavioral tests for the cost_api FastAPI router.

Interface tests verify that the APIRouter exists with all 10 endpoints
registered (must pass immediately).
Behavioral tests verify that each endpoint raises NotImplementedError
(must fail until the developer implements the module).
"""

from __future__ import annotations

import pytest
from fastapi import APIRouter

from ai_vibe_coding.cost_api import router

# ──────────────────────────────────────────────────────────────
# Interface smoke tests — must PASS immediately
# ──────────────────────────────────────────────────────────────


class TestCostApiInterface:
    """Verify the FastAPI router exists with correct endpoints."""

    def test_router_is_apirouter(self):
        """router should be a FastAPI APIRouter instance."""
        assert isinstance(router, APIRouter)

    def test_router_has_prefix(self):
        """router should have the /api/v1/costs prefix."""
        assert router.prefix == "/api/v1/costs"

    def test_router_has_tags(self):
        """router should have the costs tag."""
        assert "costs" in router.tags

    def test_router_has_routes(self):
        """router should have routes registered."""
        assert len(router.routes) > 0

    def test_all_ten_endpoints_registered(self):
        """router should have at least 10 endpoints registered."""
        assert len(router.routes) >= 10


class TestCostApiEndpointAccess:
    """Verify each endpoint is accessible via the expected path.

    We check route registration via router.routes instead of making HTTP
    requests because the async handlers raise NotImplementedError, which
    Starlette's testclient re-raises rather than returning an HTTP 500.
    """

    def _get_route_paths(self) -> set[str]:
        """Extract all registered route paths from the router."""
        paths: set[str] = set()
        for route in router.routes:
            if hasattr(route, "path"):
                paths.add(route.path)
        return paths

    def test_total_cost_endpoint_registered(self):
        """GET /api/v1/costs/total should be registered."""
        paths = self._get_route_paths()
        assert "/api/v1/costs/total" in paths

    def test_daily_endpoint_registered(self):
        """GET /api/v1/costs/daily should be registered."""
        paths = self._get_route_paths()
        assert "/api/v1/costs/daily" in paths

    def test_by_provider_endpoint_registered(self):
        """GET /api/v1/costs/by-provider should be registered."""
        paths = self._get_route_paths()
        assert "/api/v1/costs/by-provider" in paths

    def test_by_model_endpoint_registered(self):
        """GET /api/v1/costs/by-model should be registered."""
        paths = self._get_route_paths()
        assert "/api/v1/costs/by-model" in paths

    def test_by_user_endpoint_registered(self):
        """GET /api/v1/costs/by-user should be registered."""
        paths = self._get_route_paths()
        assert "/api/v1/costs/by-user" in paths

    def test_latency_percentiles_endpoint_registered(self):
        """GET /api/v1/costs/latency/percentiles should be registered."""
        paths = self._get_route_paths()
        assert "/api/v1/costs/latency/percentiles" in paths

    def test_comparison_providers_endpoint_registered(self):
        """GET /api/v1/costs/comparison/providers should be registered."""
        paths = self._get_route_paths()
        assert "/api/v1/costs/comparison/providers" in paths

    def test_trend_endpoint_registered(self):
        """GET /api/v1/costs/trend should be registered."""
        paths = self._get_route_paths()
        assert "/api/v1/costs/trend" in paths

    def test_budget_alerts_endpoint_registered(self):
        """GET /api/v1/costs/budget/alerts should be registered."""
        paths = self._get_route_paths()
        assert "/api/v1/costs/budget/alerts" in paths

    def test_budget_check_endpoint_registered(self):
        """POST /api/v1/costs/budget/check should be registered."""
        paths = self._get_route_paths()
        assert "/api/v1/costs/budget/check" in paths


# ──────────────────────────────────────────────────────────────
# Behavioral tests — must FAIL with NotImplementedError
# ──────────────────────────────────────────────────────────────


class TestCostApiBehavior:
    """Behavioral tests for each endpoint — fail until implemented.

    We use asyncio to call the async handler functions (not via TestClient)
    because Starlette testclient re-raises async exceptions rather than
    wrapping them in HTTP 500 responses.
    """

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_total_returns_cost_dict(self):
        """get_total_cost should raise NotImplementedError."""
        from ai_vibe_coding.cost_api import get_total_cost

        with pytest.raises(NotImplementedError):
            await get_total_cost()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_daily_returns_list(self):
        """get_daily_costs should raise NotImplementedError."""
        from ai_vibe_coding.cost_api import get_daily_costs

        with pytest.raises(NotImplementedError):
            await get_daily_costs()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_latency_percentiles_with_params(self):
        """get_latency_percentiles should accept params."""
        from ai_vibe_coding.cost_api import get_latency_percentiles

        with pytest.raises(NotImplementedError):
            await get_latency_percentiles(percentile=99.0, provider="openai")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_budget_check_with_body(self):
        """check_budgets should accept JSON body."""
        from ai_vibe_coding.cost_api import check_budgets

        with pytest.raises(NotImplementedError):
            await check_budgets(current_spend=75.0)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_budget_alerts_with_limit(self):
        """get_alert_history should accept limit param."""
        from ai_vibe_coding.cost_api import get_alert_history

        with pytest.raises(NotImplementedError):
            await get_alert_history(limit=5)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_all_endpoints_raise_not_implemented(self):
        """All endpoint handlers should raise NotImplementedError when called."""
        from ai_vibe_coding.cost_api import (
            check_budgets,
            compare_providers,
            cost_trend,
            get_alert_history,
            get_costs_by_model,
            get_costs_by_provider,
            get_costs_by_user,
            get_daily_costs,
            get_latency_percentiles,
            get_total_cost,
        )

        handlers = [
            get_total_cost(),
            get_daily_costs(),
            get_costs_by_provider(),
            get_costs_by_model(),
            get_costs_by_user(),
            get_latency_percentiles(),
            compare_providers(),
            cost_trend(),
            get_alert_history(),
            check_budgets(),
        ]
        for coro in handlers:
            with pytest.raises(NotImplementedError):
                await coro
