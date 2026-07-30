"""Interface and behavioral tests for the cost_store module.

Interface tests verify that SqliteCostStore and CostPricingTable exist
with correct signatures (must pass immediately).
Behavioral tests verify expected behavior (must fail with NotImplementedError
until the developer implements the module).
"""

from __future__ import annotations

import pytest

from ai_vibe_coding.cost_store import CostPricingTable, SqliteCostStore

# ──────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────

SAMPLE_PRICING = {
    "openai": {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    },
    "anthropic": {
        "claude-4-sonnet": {"input": 0.003, "output": 0.015},
    },
}


# ──────────────────────────────────────────────────────────────
# Interface smoke tests — must PASS immediately
# ──────────────────────────────────────────────────────────────


class TestSqliteCostStoreInterface:
    """Verify SqliteCostStore class and method signatures exist."""

    def test_class_exists(self):
        """SqliteCostStore should be importable and instantiable."""
        assert SqliteCostStore is not None
        assert callable(SqliteCostStore)

    def test_constructor_takes_db_path(self):
        """SqliteCostStore should accept a str or Path db_path."""
        store = SqliteCostStore(":memory:")
        assert store is not None

    def test_has_record_request(self):
        """SqliteCostStore should have record_request method."""
        assert hasattr(SqliteCostStore, "record_request")

    def test_has_get_daily_rollup(self):
        """SqliteCostStore should have get_daily_rollup method."""
        assert hasattr(SqliteCostStore, "get_daily_rollup")

    def test_has_get_total_cost(self):
        """SqliteCostStore should have get_total_cost method."""
        assert hasattr(SqliteCostStore, "get_total_cost")

    def test_has_get_latency_percentiles(self):
        """SqliteCostStore should have get_latency_percentiles method."""
        assert hasattr(SqliteCostStore, "get_latency_percentiles")

    def test_has_get_cost_by_model(self):
        """SqliteCostStore should have get_cost_by_model method."""
        assert hasattr(SqliteCostStore, "get_cost_by_model")

    def test_has_get_cost_by_provider(self):
        """SqliteCostStore should have get_cost_by_provider method."""
        assert hasattr(SqliteCostStore, "get_cost_by_provider")

    def test_has_get_cost_by_user(self):
        """SqliteCostStore should have get_cost_by_user method."""
        assert hasattr(SqliteCostStore, "get_cost_by_user")

    def test_has_run_daily_rollup(self):
        """SqliteCostStore should have run_daily_rollup method."""
        assert hasattr(SqliteCostStore, "run_daily_rollup")


class TestCostPricingTableInterface:
    """Verify CostPricingTable dataclass and methods exist."""

    def test_class_exists(self):
        """CostPricingTable should be importable and instantiable."""
        assert CostPricingTable is not None

    def test_constructor_takes_pricing(self):
        """CostPricingTable should accept a pricing dict."""
        table = CostPricingTable(pricing=SAMPLE_PRICING)
        assert table.pricing is not None

    def test_has_upsert_pricing(self):
        """CostPricingTable should have upsert_pricing method."""
        assert hasattr(CostPricingTable, "upsert_pricing")

    def test_has_get_pricing(self):
        """CostPricingTable should have get_pricing method."""
        assert hasattr(CostPricingTable, "get_pricing")

    def test_has_seed_from_pricing_dict(self):
        """CostPricingTable should have seed_from_pricing_dict method."""
        assert hasattr(CostPricingTable, "seed_from_pricing_dict")


# ──────────────────────────────────────────────────────────────
# Behavioral tests — verify real implementation behavior
# ──────────────────────────────────────────────────────────────


class TestSqliteCostStoreBehavior:
    """Behavioral tests for SqliteCostStore."""

    @pytest.mark.unit
    def test_record_request_returns_int(self):
        """record_request() should return the inserted row id."""
        store = SqliteCostStore(":memory:")
        row_id = store.record_request(
            provider="openai",
            model="gpt-4",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.006,
            latency_ms=120.0,
        )
        assert isinstance(row_id, int)
        assert row_id > 0

    @pytest.mark.unit
    def test_record_request_with_session_id(self):
        """record_request() should accept optional session_id and tags."""
        store = SqliteCostStore(":memory:")
        row_id = store.record_request(
            provider="openai",
            model="gpt-4",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.006,
            latency_ms=120.0,
            session_id="sess-001",
            tags={"project": "test"},
        )
        assert isinstance(row_id, int)
        assert row_id > 0

    @pytest.mark.unit
    def test_get_daily_rollup_returns_list(self):
        """get_daily_rollup() should return a list of dicts."""
        store = SqliteCostStore(":memory:")
        store.record_request(
            provider="openai", model="gpt-4",
            input_tokens=100, output_tokens=50,
            cost_usd=0.006, latency_ms=120.0,
        )
        result = store.get_daily_rollup()
        assert isinstance(result, list)
        if result:
            assert "date" in result[0]
            assert "total_cost" in result[0]

    @pytest.mark.unit
    def test_get_daily_rollup_with_date_filter(self):
        """get_daily_rollup() should accept date range filters."""
        store = SqliteCostStore(":memory:")
        store.record_request(
            provider="openai", model="gpt-4",
            input_tokens=100, output_tokens=50,
            cost_usd=0.006, latency_ms=120.0,
        )
        result = store.get_daily_rollup(
            start_date="2026-07-01", end_date="2026-07-31"
        )
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_get_total_cost_returns_float(self):
        """get_total_cost() should return a float."""
        store = SqliteCostStore(":memory:")
        store.record_request(
            provider="openai", model="gpt-4",
            input_tokens=100, output_tokens=50,
            cost_usd=0.006, latency_ms=120.0,
        )
        result = store.get_total_cost()
        assert isinstance(result, float)
        assert result == pytest.approx(0.006)

    @pytest.mark.unit
    def test_get_total_cost_with_filters(self):
        """get_total_cost() should accept provider and date filters."""
        store = SqliteCostStore(":memory:")
        store.record_request(
            provider="openai", model="gpt-4",
            input_tokens=100, output_tokens=50,
            cost_usd=0.006, latency_ms=120.0,
        )
        result = store.get_total_cost(
            start_date="2026-07-01",
            end_date="2026-07-31",
            provider="openai",
        )
        assert isinstance(result, float)

    @pytest.mark.unit
    def test_get_latency_percentiles_returns_float(self):
        """get_latency_percentiles() should return a float."""
        store = SqliteCostStore(":memory:")
        store.record_request(
            provider="openai", model="gpt-4",
            input_tokens=100, output_tokens=50,
            cost_usd=0.006, latency_ms=120.0,
        )
        result = store.get_latency_percentiles(percentile=95.0)
        assert isinstance(result, float)

    @pytest.mark.unit
    def test_get_latency_percentiles_with_filters(self):
        """get_latency_percentiles() should accept all filters."""
        store = SqliteCostStore(":memory:")
        store.record_request(
            provider="openai", model="gpt-4",
            input_tokens=100, output_tokens=50,
            cost_usd=0.006, latency_ms=120.0,
        )
        result = store.get_latency_percentiles(
            percentile=99.0,
            start_date="2026-07-01",
            end_date="2026-07-31",
            provider="anthropic",
        )
        assert isinstance(result, float)

    @pytest.mark.unit
    def test_get_cost_by_model_returns_list(self):
        """get_cost_by_model() should return a list of dicts."""
        store = SqliteCostStore(":memory:")
        store.record_request(
            provider="openai", model="gpt-4",
            input_tokens=100, output_tokens=50,
            cost_usd=0.006, latency_ms=120.0,
        )
        result = store.get_cost_by_model()
        assert isinstance(result, list)
        if result:
            assert "model" in result[0]

    @pytest.mark.unit
    def test_get_cost_by_provider_returns_list(self):
        """get_cost_by_provider() should return a list of dicts."""
        store = SqliteCostStore(":memory:")
        store.record_request(
            provider="openai", model="gpt-4",
            input_tokens=100, output_tokens=50,
            cost_usd=0.006, latency_ms=120.0,
        )
        result = store.get_cost_by_provider()
        assert isinstance(result, list)
        if result:
            assert "provider" in result[0]

    @pytest.mark.unit
    def test_get_cost_by_user_returns_list(self):
        """get_cost_by_user() should return a list of dicts by session_id."""
        store = SqliteCostStore(":memory:")
        store.record_request(
            provider="openai", model="gpt-4",
            input_tokens=100, output_tokens=50,
            cost_usd=0.006, latency_ms=120.0,
            session_id="sess-001",
        )
        result = store.get_cost_by_user()
        assert isinstance(result, list)
        if result:
            assert "session_id" in result[0]

    @pytest.mark.unit
    def test_run_daily_rollup_returns_dict(self):
        """run_daily_rollup() should return a summary dict."""
        store = SqliteCostStore(":memory:")
        store.record_request(
            provider="openai", model="gpt-4",
            input_tokens=100, output_tokens=50,
            cost_usd=0.006, latency_ms=120.0,
        )
        result = store.run_daily_rollup()
        assert isinstance(result, dict)
        assert "date" in result
        assert "records_processed" in result


class TestCostPricingTableBehavior:
    """Behavioral tests for CostPricingTable."""

    @pytest.mark.unit
    def test_upsert_pricing_adds_entry(self):
        """upsert_pricing() should add a new pricing entry."""
        table = CostPricingTable(pricing={})
        table.upsert_pricing(
            provider="openai",
            model="gpt-4",
            input_rate=0.03,
            output_rate=0.06,
        )
        assert "openai" in table.pricing
        assert "gpt-4" in table.pricing["openai"]
        assert table.pricing["openai"]["gpt-4"]["input"] == 0.03
        assert table.pricing["openai"]["gpt-4"]["output"] == 0.06

    @pytest.mark.unit
    def test_get_pricing_returns_dict(self):
        """get_pricing() should return pricing dict or None."""
        table = CostPricingTable(pricing=SAMPLE_PRICING)
        result = table.get_pricing(provider="openai", model="gpt-4")
        assert isinstance(result, dict)
        assert result["input"] == 0.03

    @pytest.mark.unit
    def test_seed_from_pricing_dict_returns_int(self):
        """seed_from_pricing_dict() should return count of inserted entries."""
        table = CostPricingTable(pricing={})
        count = table.seed_from_pricing_dict(SAMPLE_PRICING)
        assert isinstance(count, int)
        # 2 openai models + 1 anthropic model = 3 entries
        assert count == 3
