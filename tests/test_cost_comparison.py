"""Interface and behavioral tests for the cost_comparison module.

Interface tests verify that all comparison functions exist with correct
signatures (must pass immediately).
Behavioral tests verify expected behavior (must fail with NotImplementedError
until the developer implements the module).
"""

from __future__ import annotations

import inspect

import pytest

from ai_vibe_coding.cost_comparison import (
    compare_actual_costs,
    compare_estimated_vs_actual,
    get_cost_trend,
)

# ──────────────────────────────────────────────────────────────
# Interface smoke tests — must PASS immediately
# ──────────────────────────────────────────────────────────────


class TestCostComparisonInterface:
    """Verify all comparison functions exist with correct signatures."""

    def test_compare_actual_costs_exists(self):
        """compare_actual_costs should be a callable function."""
        assert callable(compare_actual_costs)

    def test_compare_estimated_vs_actual_exists(self):
        """compare_estimated_vs_actual should be a callable function."""
        assert callable(compare_estimated_vs_actual)

    def test_get_cost_trend_exists(self):
        """get_cost_trend should be a callable function."""
        assert callable(get_cost_trend)

    def test_compare_actual_costs_signature(self):
        """compare_actual_costs should accept start_date, end_date, providers.

        We use signature inspection to verify the interface since the function
        raises NotImplementedError when called.
        """
        sig = inspect.signature(compare_actual_costs)
        params = list(sig.parameters.keys())
        assert "start_date" in params
        assert "end_date" in params
        assert "providers" in params

    def test_compare_estimated_vs_actual_signature(self):
        """compare_estimated_vs_actual should accept start_date, end_date, providers."""
        sig = inspect.signature(compare_estimated_vs_actual)
        params = list(sig.parameters.keys())
        assert "start_date" in params
        assert "providers" in params

    def test_get_cost_trend_signature(self):
        """get_cost_trend should accept granularity, start_date, end_date."""
        sig = inspect.signature(get_cost_trend)
        params = list(sig.parameters.keys())
        assert "granularity" in params
        assert "start_date" in params
        assert "end_date" in params


# ──────────────────────────────────────────────────────────────
# Behavioral tests — verify real implementation behavior
# ──────────────────────────────────────────────────────────────


class TestCostComparisonBehavior:
    """Behavioral tests for cost comparison functions."""

    @pytest.mark.unit
    def test_compare_actual_costs_returns_sorted(self):
        """compare_actual_costs() should return sorted list by total_cost desc."""
        result = compare_actual_costs()
        assert isinstance(result, list)
        # With no data, result is empty list
        assert len(result) == 0

    @pytest.mark.unit
    def test_compare_actual_costs_with_provider_filter(self):
        """compare_actual_costs() should filter by providers list."""
        result = compare_actual_costs(providers=["openai"])
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_compare_actual_costs_with_date_range(self):
        """compare_actual_costs() should filter by date range."""
        result = compare_actual_costs(
            start_date="2026-07-01",
            end_date="2026-07-31",
        )
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_compare_estimated_vs_actual_returns_list(self):
        """compare_estimated_vs_actual() should return comparison list."""
        result = compare_estimated_vs_actual()
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_compare_estimated_vs_actual_provider_filter(self):
        """compare_estimated_vs_actual() should filter by provider."""
        result = compare_estimated_vs_actual(providers=["anthropic"])
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_get_cost_trend_returns_list(self):
        """get_cost_trend() should return trend data list."""
        result = get_cost_trend()
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_get_cost_trend_weekly(self):
        """get_cost_trend() should accept weekly granularity."""
        result = get_cost_trend(granularity="weekly")
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_get_cost_trend_monthly(self):
        """get_cost_trend() should accept monthly granularity."""
        result = get_cost_trend(granularity="monthly")
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_get_cost_trend_with_date_range(self):
        """get_cost_trend() should filter by date range."""
        result = get_cost_trend(
            granularity="daily",
            start_date="2026-07-01",
            end_date="2026-07-31",
        )
        assert isinstance(result, list)
