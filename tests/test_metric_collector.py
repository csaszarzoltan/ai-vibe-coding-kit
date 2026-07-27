"""Pre-development tests for metric_collector.py (Task P0.5-P0.7).

Interface tests verify the public API exists with correct signatures and
type hints — these must PASS immediately with the stub implementation.

Behavioral tests define the expected behaviour that the developer must
make green by implementing the stubs — these must FAIL with NotImplementedError.

pytest markers:
    @pytest.mark.unit — mocked HTTP, no real API keys needed
"""

from __future__ import annotations

import pytest

from ai_vibe_coding.metric_collector import (
    BenchmarkReport,
    MetricCollector,
    TaskMetrics,
    contains,
    evaluate,
    exact_match,
    fuzzy_match,
)

# ──────────────────────────────────────────────────────────────
# Interface smoke tests (should PASS — verify API surface exists)
# ──────────────────────────────────────────────────────────────


class TestMetricCollectorInterface:
    """Verify MetricCollector class has expected structure."""

    def test_metric_collector_init(self):
        """MetricCollector should be instantiable with no args."""
        collector = MetricCollector()
        assert collector is not None

    def test_metric_collector_has_methods(self):
        """MetricCollector should have all 6 methods."""
        assert hasattr(MetricCollector, "record_result")
        assert hasattr(MetricCollector, "record_results")
        assert hasattr(MetricCollector, "get_task_metrics")
        assert hasattr(MetricCollector, "get_report")
        assert hasattr(MetricCollector, "get_cost_summary")
        assert hasattr(MetricCollector, "reset")

    def test_metric_collector_init_internal_tracker(self):
        """MetricCollector should initialize with a CostTracker."""
        from ai_vibe_coding.cost_tracker import CostTracker

        collector = MetricCollector()
        assert hasattr(collector, "_cost_tracker")
        assert isinstance(collector._cost_tracker, CostTracker)
        assert hasattr(collector, "_results")
        assert isinstance(collector._results, list)


class TestBenchmarkReportInterface:
    """Verify BenchmarkReport dataclass and methods."""

    def test_benchmark_report_defaults(self):
        """BenchmarkReport should have sensible defaults."""
        report = BenchmarkReport()
        assert report.title == "Benchmark Report"
        assert report.timestamp == ""
        assert report.tasks == {}
        assert report.total_cost == 0.0
        assert report.total_runs == 0

    def test_benchmark_report_custom_title(self):
        """BenchmarkReport should accept a custom title."""
        report = BenchmarkReport(title="My Benchmarks")
        assert report.title == "My Benchmarks"

    def test_benchmark_report_has_methods(self):
        """BenchmarkReport should have to_dict(), to_markdown(), to_ascii_table()."""
        assert hasattr(BenchmarkReport, "to_dict")
        assert hasattr(BenchmarkReport, "to_markdown")
        assert hasattr(BenchmarkReport, "to_ascii_table")

    def test_benchmark_report_to_dict_signature(self):
        """to_dict() should take only self."""
        import inspect

        sig = inspect.signature(BenchmarkReport.to_dict)
        params = list(sig.parameters.keys())
        assert params == ["self"] or "output_path" not in params

    def test_benchmark_report_to_markdown_signature(self):
        """to_markdown() should accept optional output_path."""
        import inspect

        sig = inspect.signature(BenchmarkReport.to_markdown)
        params = list(sig.parameters.keys())
        assert "output_path" in params


class TestTaskMetricsInterface:
    """Verify TaskMetrics dataclass fields."""

    def test_task_metrics_fields(self):
        """TaskMetrics should have all specified fields."""
        import inspect

        fields = dict(inspect.getmembers(TaskMetrics, lambda m: not callable(m)))
        dataclass_fields = {f.name for f in TaskMetrics.__dataclass_fields__.values()}

        required = {
            "task_id", "task_name", "best_provider", "best_model",
            "provider_rankings", "accuracy_mean", "accuracy_std",
            "avg_latency_ms", "avg_cost_usd", "error_rate", "run_count",
        }
        assert required.issubset(dataclass_fields), (
            f"Missing fields: {required - dataclass_fields}"
        )

    def test_task_metrics_defaults(self):
        """TaskMetrics should have correct default values."""
        metrics = TaskMetrics(task_id="t1", task_name="Test")
        assert metrics.task_id == "t1"
        assert metrics.task_name == "Test"
        assert metrics.best_provider is None
        assert metrics.best_model is None
        assert metrics.provider_rankings == []
        assert metrics.accuracy_mean == 0.0
        assert metrics.accuracy_std == 0.0
        assert metrics.avg_latency_ms == 0.0
        assert metrics.avg_cost_usd == 0.0
        assert metrics.error_rate == 0.0
        assert metrics.run_count == 0


class TestEvaluatorFunctionsInterface:
    """Verify evaluator functions exist as callables."""

    def test_exact_match_is_callable(self):
        """exact_match should be a callable function."""
        assert callable(exact_match)

    def test_fuzzy_match_is_callable(self):
        """fuzzy_match should be a callable function."""
        assert callable(fuzzy_match)

    def test_contains_is_callable(self):
        """contains should be a callable function."""
        assert callable(contains)

    def test_evaluate_is_callable(self):
        """evaluate should be a callable function."""
        assert callable(evaluate)


# ──────────────────────────────────────────────────────────────
# Behavioral pre-state tests (should FAIL — NotImplementedError)
# These define the contract the developer must satisfy.
# ──────────────────────────────────────────────────────────────


class TestMetricCollectorRecordResult:
    """Behavioral tests for record_result() — fail until implemented."""

    @pytest.mark.unit
    def test_metric_collector_record_result(self):
        """record_result() should store a result and make it accessible."""
        from ai_vibe_coding.benchmark_runner import BenchmarkResult

        collector = MetricCollector()
        result = BenchmarkResult(
            task_id="qa-1", provider="openai", model="gpt-4",
            raw_response="42", latency_ms=100.0,
        )
        collector.record_result(result)
        metrics = collector.get_task_metrics("qa-1")
        assert isinstance(metrics, TaskMetrics)
        assert metrics.task_id == "qa-1"

    @pytest.mark.unit
    def test_metric_collector_record_results_batch(self):
        """record_results() should accept a list of results."""
        from ai_vibe_coding.benchmark_runner import BenchmarkResult

        collector = MetricCollector()
        results = [
            BenchmarkResult(
                task_id="qa-1", provider="openai", model="gpt-4",
                raw_response="A", latency_ms=100.0,
            ),
            BenchmarkResult(
                task_id="qa-1", provider="anthropic", model="claude-sonnet",
                raw_response="B", latency_ms=200.0,
            ),
        ]
        collector.record_results(results)

    @pytest.mark.unit
    def test_metric_collector_get_task_metrics_aggregates(self):
        """get_task_metrics() should aggregate across multiple results."""
        from ai_vibe_coding.benchmark_runner import BenchmarkResult

        collector = MetricCollector()
        for _ in range(3):
            collector.record_result(BenchmarkResult(
                task_id="qa-1", provider="openai", model="gpt-4",
                raw_response="42", latency_ms=100.0,
                accuracy_score=1.0, cost_usd=0.01,
            ))
        metrics = collector.get_task_metrics("qa-1")
        assert metrics.run_count == 3


class TestMetricCollectorGetReport:
    """Behavioral tests for get_report() — fail until implemented."""

    @pytest.mark.unit
    def test_metric_collector_get_report(self):
        """get_report() should return a complete BenchmarkReport."""
        from ai_vibe_coding.benchmark_runner import BenchmarkResult

        collector = MetricCollector()
        collector.record_result(BenchmarkResult(
            task_id="qa-1", provider="openai", model="gpt-4",
            raw_response="42", latency_ms=100.0,
        ))
        report = collector.get_report(title="Test Report")
        assert isinstance(report, BenchmarkReport)
        assert report.title == "Test Report"

    @pytest.mark.unit
    def test_metric_collector_get_report_empty(self):
        """get_report() with no results should return an empty report."""
        collector = MetricCollector()
        report = collector.get_report()
        assert isinstance(report, BenchmarkReport)
        assert report.total_runs == 0


class TestMetricCollectorGetCostSummary:
    """Behavioral tests for get_cost_summary() — fail until implemented."""

    @pytest.mark.unit
    def test_metric_collector_get_cost_summary(self):
        """get_cost_summary() should delegate to internal CostTracker."""
        from ai_vibe_coding.cost_tracker import CostSummary

        collector = MetricCollector()
        summary = collector.get_cost_summary()
        assert isinstance(summary, CostSummary)


class TestMetricCollectorReset:
    """Behavioral tests for reset() — fail until implemented."""

    @pytest.mark.unit
    def test_metric_collector_reset_clears(self):
        """reset() should clear all recorded results."""
        from ai_vibe_coding.benchmark_runner import BenchmarkResult

        collector = MetricCollector()
        collector.record_result(BenchmarkResult(
            task_id="qa-1", provider="openai", model="gpt-4",
            raw_response="42", latency_ms=100.0,
        ))
        collector.reset()
        report = collector.get_report()
        assert report.total_runs == 0


class TestExactMatch:
    """Behavioral tests for exact_match() — fail until implemented."""

    @pytest.mark.unit
    def test_exact_match_correct(self):
        """exact_match returns 1.0 for identical strings."""
        score = exact_match("Paris", "Paris")
        assert score == 1.0

    @pytest.mark.unit
    def test_exact_match_incorrect(self):
        """exact_match returns 0.0 for different strings."""
        score = exact_match("London", "Paris")
        assert score == 0.0

    @pytest.mark.unit
    def test_exact_match_normalized(self):
        """exact_match should handle whitespace and case normalization."""
        score = exact_match("  Hello World  ", "hello world")
        assert score == 1.0


class TestFuzzyMatch:
    """Behavioral tests for fuzzy_match() — fail until implemented."""

    @pytest.mark.unit
    def test_fuzzy_match_range(self):
        """fuzzy_match returns a float between 0.0 and 1.0."""
        score = fuzzy_match("Paris is nice", "Paris is lovely")
        assert 0.0 <= score <= 1.0

    @pytest.mark.unit
    def test_fuzzy_match_identical(self):
        """fuzzy_match returns 1.0 for identical strings."""
        score = fuzzy_match("Hello World", "Hello World")
        assert score == 1.0

    @pytest.mark.unit
    def test_fuzzy_match_completely_different(self):
        """fuzzy_match returns 0.0 for completely different strings."""
        score = fuzzy_match("Hello", "Goodbye")
        assert score == 0.0


class TestContains:
    """Behavioral tests for contains() — fail until implemented."""

    @pytest.mark.unit
    def test_contains_match(self):
        """contains returns 1.0 when expected is a substring of response."""
        score = contains("The capital of France is Paris.", "Paris")
        assert score == 1.0

    @pytest.mark.unit
    def test_contains_no_match(self):
        """contains returns 0.0 when substring not found."""
        score = contains("Hello World", "Python")
        assert score == 0.0


class TestEvaluate:
    """Behavioral tests for evaluate() — fail until implemented."""

    @pytest.mark.unit
    def test_evaluate_dispatches_exact_match(self):
        """evaluate('exact_match') delegates to exact_match."""
        score = evaluate("Paris", "Paris", "exact_match")
        assert score == 1.0

    @pytest.mark.unit
    def test_evaluate_dispatches_fuzzy_match(self):
        """evaluate('fuzzy_match') delegates to fuzzy_match."""
        score = evaluate("Paris", "Paris", "fuzzy_match")
        assert 0.0 <= score <= 1.0

    @pytest.mark.unit
    def test_evaluate_dispatches_contains(self):
        """evaluate('contains') delegates to contains."""
        score = evaluate("Hello Paris", "Paris", "contains")
        assert score == 1.0

    @pytest.mark.unit
    def test_evaluate_unknown_raises(self):
        """Unknown evaluator type should raise ValueError."""
        with pytest.raises(ValueError):
            evaluate("test", "test", "unknown_evaluator")
