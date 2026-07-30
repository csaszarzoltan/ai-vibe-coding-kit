"""Smoke tests for cost tracking and analytics (TASK-3).

Interface tests verify API surface. Behavioral tests define the contract
for cost accumulation, thread safety, and CSV/JSON export.
"""

from __future__ import annotations

import csv
import json
import threading

import pytest

from ai_vibe_coding.cost_tracker import CostSummary, CostTracker
from ai_vibe_coding.llm_wrapper import LLMResponse

# ──────────────────────────────────────────────────────────────
# Interface smoke tests
# ──────────────────────────────────────────────────────────────


class TestInterfaceSmoke:
    """Verify that all classes and methods exist with correct signatures."""

    def test_cost_tracker_init(self):
        """CostTracker should be instantiable with no args."""
        tracker = CostTracker()
        assert tracker is not None

    def test_cost_tracker_has_methods(self):
        """CostTracker should have all required methods."""
        assert hasattr(CostTracker, "record")
        assert hasattr(CostTracker, "get_summary")
        assert hasattr(CostTracker, "export_csv")
        assert hasattr(CostTracker, "export_json")
        assert hasattr(CostTracker, "reset")

    def test_cost_summary_is_dataclass(self):
        """CostSummary should be instantiable with default values."""
        summary = CostSummary()
        assert summary.total_cost == 0.0
        assert summary.total_tokens == 0
        assert summary.per_provider == {}
        assert summary.per_model == {}
        assert summary.call_count == 0

    def test_cost_summary_has_to_dict(self):
        """CostSummary should have to_dict method."""
        assert hasattr(CostSummary, "to_dict")

    def test_cost_summary_has_to_table(self):
        """CostSummary should have to_table method."""
        assert hasattr(CostSummary, "to_table")


# ──────────────────────────────────────────────────────────────
# Behavioral pre-state tests (fail until implementation)
# ──────────────────────────────────────────────────────────────


def _make_response(
    provider: str = "openai",
    model: str = "gpt-4",
    cost: float = 0.001,
    tokens: int = 100,
    input_tokens: int = 40,
    output_tokens: int = 60,
) -> LLMResponse:
    """Helper: create a minimal LLMResponse for cost tracking tests."""
    return LLMResponse(
        content="test",
        provider=provider,
        model=model,
        tokens_used=tokens,
        cost_usd=cost,
        latency_ms=50.0,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


class TestRecordAndSummary:
    """Behavioral tests for record() and get_summary() — fail until implemented."""

    @pytest.mark.unit
    def test_record_single_response(self):
        """record() should store cost data from an LLMResponse."""
        tracker = CostTracker()
        tracker.record(_make_response(cost=0.05, tokens=200))
        summary = tracker.get_summary()
        assert summary.total_cost == pytest.approx(0.05)
        assert summary.total_tokens == 200
        assert summary.call_count == 1

    @pytest.mark.unit
    def test_record_multiple_responses(self):
        """record() should accumulate costs across multiple responses."""
        tracker = CostTracker()
        tracker.record(_make_response(provider="openai", cost=0.01, tokens=100))
        tracker.record(_make_response(provider="anthropic", cost=0.02, tokens=150))
        tracker.record(_make_response(provider="openai", cost=0.03, tokens=200))
        summary = tracker.get_summary()
        assert summary.total_cost == pytest.approx(0.06)
        assert summary.total_tokens == 450
        assert summary.call_count == 3

    @pytest.mark.unit
    def test_per_provider_breakdown(self):
        """get_summary() should break down costs by provider."""
        tracker = CostTracker()
        tracker.record(_make_response(provider="openai", cost=0.01))
        tracker.record(_make_response(provider="openai", cost=0.02))
        tracker.record(_make_response(provider="anthropic", cost=0.05))
        summary = tracker.get_summary()
        assert summary.per_provider["openai"] == pytest.approx(0.03)
        assert summary.per_provider["anthropic"] == pytest.approx(0.05)

    @pytest.mark.unit
    def test_per_model_breakdown(self):
        """get_summary() should break down costs by model."""
        tracker = CostTracker()
        tracker.record(_make_response(model="gpt-4", cost=0.01))
        tracker.record(_make_response(model="gpt-4", cost=0.02))
        tracker.record(_make_response(model="gpt-5", cost=0.04))
        summary = tracker.get_summary()
        assert summary.per_model["gpt-4"] == pytest.approx(0.03)
        assert summary.per_model["gpt-5"] == pytest.approx(0.04)


class TestThreadSafety:
    """Thread safety tests — fail until implemented."""

    @pytest.mark.unit
    def test_concurrent_record_no_data_loss(self):
        """100 concurrent record() calls should not lose data."""
        tracker = CostTracker()
        threads = []

        def record_one():
            tracker.record(_make_response(cost=0.001, tokens=10))

        for _ in range(100):
            t = threading.Thread(target=record_one)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        summary = tracker.get_summary()
        assert summary.call_count == 100
        assert summary.total_cost == pytest.approx(0.1, rel=0.01)


class TestExport:
    """Behavioral tests for export_csv() and export_json() — fail until implemented."""

    @pytest.mark.unit
    def test_export_csv_creates_valid_file(self, tmp_path):
        """export_csv() should create a CSV readable by csv module."""
        tracker = CostTracker()
        tracker.record(
            _make_response(provider="openai", model="gpt-4", cost=0.01, tokens=100)
        )
        tracker.record(
            _make_response(
                provider="anthropic", model="claude-4", cost=0.02, tokens=200
            )
        )

        csv_path = tmp_path / "costs.csv"
        tracker.export_csv(str(csv_path))

        assert csv_path.exists()
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        assert "provider" in rows[0]
        assert "model" in rows[0]
        assert "cost_usd" in rows[0]
        assert "tokens_in" in rows[0]
        assert "tokens_out" in rows[0]

    @pytest.mark.unit
    def test_export_json_creates_valid_file(self, tmp_path):
        """export_json() should create valid JSON with per-provider structure."""
        tracker = CostTracker()
        tracker.record(_make_response(provider="openai", cost=0.01))
        tracker.record(_make_response(provider="anthropic", cost=0.02))

        json_path = tmp_path / "costs.json"
        tracker.export_json(str(json_path))

        assert json_path.exists()
        with open(json_path) as f:
            data = json.load(f)
        assert "total_cost" in data
        assert "per_provider" in data
        assert "openai" in data["per_provider"]


class TestSummaryOutput:
    """Tests for CostSummary.to_dict() and to_table() — fail until implemented."""

    @pytest.mark.unit
    def test_to_dict_returns_serializable(self):
        """to_dict() should return a JSON-serializable dict."""
        summary = CostSummary(
            total_cost=0.10,
            total_tokens=500,
            per_provider={"openai": 0.10},
            per_model={"gpt-4": 0.10},
            call_count=2,
        )
        d = summary.to_dict()
        assert d["total_cost"] == 0.10
        assert d["call_count"] == 2
        # Should be JSON serializable
        json.dumps(d)

    @pytest.mark.unit
    def test_to_table_returns_aligned_string(self):
        """to_table() should return an ASCII table string."""
        summary = CostSummary(
            total_cost=0.10,
            total_tokens=500,
            per_provider={"openai": 0.06, "anthropic": 0.04},
            call_count=2,
        )
        table = summary.to_table()
        assert isinstance(table, str)
        assert "openai" in table
        assert "anthropic" in table
        assert "0.10" in table or "0.1" in table


class TestReset:
    """Behavioral tests for reset() — fail until implemented."""

    @pytest.mark.unit
    def test_reset_clears_all(self):
        """reset() should clear all recorded costs."""
        tracker = CostTracker()
        tracker.record(_make_response(cost=0.01))
        tracker.reset()
        summary = tracker.get_summary()
        assert summary.call_count == 0
        assert summary.total_cost == 0.0


# ──────────────────────────────────────────────────────────────
# Interface tests for extended CostTracker methods (P0-B)
# ──────────────────────────────────────────────────────────────


class TestCostTrackerExtensionInterface:
    """Verify new methods added by P0-B extension exist."""

    def test_init_accepts_db_path(self):
        """CostTracker should accept optional db_path parameter."""
        tracker = CostTracker(db_path=":memory:")
        assert tracker is not None

    def test_init_without_db_path(self):
        """CostTracker should still work without db_path (backward compat)."""
        tracker = CostTracker()
        assert tracker is not None

    def test_has_set_store(self):
        """CostTracker should have set_store method."""
        assert hasattr(CostTracker, "set_store")

    def test_has_get_store(self):
        """CostTracker should have get_store method."""
        assert hasattr(CostTracker, "get_store")

    def test_has_get_daily_cost(self):
        """CostTracker should have get_daily_cost method."""
        assert hasattr(CostTracker, "get_daily_cost")

    def test_has_get_latency_percentiles(self):
        """CostTracker should have get_latency_percentiles method."""
        assert hasattr(CostTracker, "get_latency_percentiles")


# ──────────────────────────────────────────────────────────────
# Behavioral tests for extended CostTracker methods — must FAIL
# ──────────────────────────────────────────────────────────────


class TestCostTrackerExtensionBehavior:
    """Behavioral tests for new methods."""

    @pytest.mark.unit
    def test_set_store_accepts_store(self):
        """set_store() should accept a store instance."""
        from ai_vibe_coding.cost_store import SqliteCostStore

        tracker = CostTracker()
        store = SqliteCostStore(":memory:")
        tracker.set_store(store)
        assert tracker.get_store() is store

    @pytest.mark.unit
    def test_get_store_returns_store(self):
        """get_store() should return the current store."""
        from ai_vibe_coding.cost_store import SqliteCostStore

        tracker = CostTracker()
        store = SqliteCostStore(":memory:")
        tracker.set_store(store)
        result = tracker.get_store()
        assert result is store

    @pytest.mark.unit
    def test_get_daily_cost_returns_list(self):
        """get_daily_cost() should return a list of dicts."""
        tracker = CostTracker()
        tracker.record(_make_response(cost=0.01, tokens=100))
        result = tracker.get_daily_cost()
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_get_daily_cost_with_date_filter(self):
        """get_daily_cost() should accept date range filters."""
        tracker = CostTracker(db_path=":memory:")
        tracker.record(_make_response(cost=0.01, tokens=100))
        result = tracker.get_daily_cost(
            start_date="2026-07-01",
            end_date="2026-07-31",
        )
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_get_latency_percentiles_returns_float(self):
        """get_latency_percentiles() should return a float."""
        tracker = CostTracker()
        tracker.record(_make_response(cost=0.01, tokens=100))
        result = tracker.get_latency_percentiles(percentile=95.0)
        assert isinstance(result, float)

    @pytest.mark.unit
    def test_get_latency_percentiles_with_filters(self):
        """get_latency_percentiles() should accept all filters."""
        tracker = CostTracker(db_path=":memory:")
        tracker.record(_make_response())
        result = tracker.get_latency_percentiles(
            percentile=99.0,
            start_date="2026-07-01",
            end_date="2026-07-31",
            provider="openai",
        )
        assert isinstance(result, float)
