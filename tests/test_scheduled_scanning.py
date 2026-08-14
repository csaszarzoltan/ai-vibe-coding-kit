"""Pre-development acceptance tests for Scheduled Scanning & Monitoring.

Test categories:
  1. Interface Smoke Tests       ( 8 tests)
  2. DriftDetector Tests         (10 tests)
  3. PromptRegressionTester Tests ( 8 tests)
  4. CostAnomalyDetector Tests    (10 tests)
  5. SLAChecker Tests            (10 tests)
  6. Scheduler Tests             (10 tests)
  7. Integration Tests            ( 6 tests)
                                -----
    Total:                        62 tests
"""

from __future__ import annotations

import pytest

try:
    from ai_vibe_coding.scheduled_scanning import (
        AlertLevel,
        ComplianceStatus,
        CostAnomalyDetector,
        DriftDetector,
        DriftReport,
        PromptRegressionReport,
        PromptRegressionTester,
        ScanResult,
        ScanType,
        Scheduler,
        SLAChecker,
    )
    MODULE_EXISTS = True
except ImportError:
    MODULE_EXISTS = False


def test_scheduled_scanning_module_must_exist() -> None:
    """RED phase: scheduled_scanning.py must exist."""
    if not MODULE_EXISTS:
        pytest.fail(
            "Module 'ai_vibe_coding.scheduled_scanning' not found."
        )


# ====================================================================
# Interface Smoke Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="scheduled_scanning not impl")
class TestInterfaceSmoke:
    """Verify API surface — all classes, enums, dataclasses exist."""

    def test_drift_detector_instantiation(self) -> None:
        dd = DriftDetector(name="test")
        assert dd.name == "test"

    def test_prompt_regression_tester_instantiation(self) -> None:
        prt = PromptRegressionTester(default_threshold=0.1)
        assert prt.default_threshold == 0.1

    def test_cost_anomaly_detector_instantiation(self) -> None:
        cad = CostAnomalyDetector(deviation_threshold=1.5)
        assert cad.deviation_threshold == 1.5

    def test_sla_checker_instantiation(self) -> None:
        sla = SLAChecker()
        assert sla is not None

    def test_scheduler_instantiation(self) -> None:
        sched = Scheduler()
        assert sched.list_tasks() == []

    def test_scan_type_enum_values(self) -> None:
        assert ScanType.DRIFT.value == "drift"
        assert ScanType.REGRESSION.value == "regression"
        assert ScanType.COST_ANOMALY.value == "cost_anomaly"
        assert ScanType.SLA_CHECK.value == "sla_check"

    def test_alert_level_enum_values(self) -> None:
        assert AlertLevel.INFO.value == "info"
        assert AlertLevel.WARNING.value == "warning"
        assert AlertLevel.CRITICAL.value == "critical"

    def test_compliance_status_enum_values(self) -> None:
        assert ComplianceStatus.COMPLIANT.value == "compliant"
        assert ComplianceStatus.WARNING.value == "warning"
        assert ComplianceStatus.BREACHED.value == "breached"


# ====================================================================
# DriftDetector Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="scheduled_scanning not impl")
class TestDriftDetector:
    """Test DriftDetector — baseline computation and drift detection."""

    def test_compute_baseline_from_samples(self) -> None:
        dd = DriftDetector(name="test")
        samples = [{"response_length": i * 10} for i in range(50)]
        baseline = dd.compute_baseline(samples, metric="response_length")
        assert "mean" in baseline
        assert "std" in baseline

    def test_compute_baseline_raises_on_empty(self) -> None:
        dd = DriftDetector()
        with pytest.raises(ValueError, match="empty"):
            dd.compute_baseline([], metric="response_length")

    def test_compute_baseline_raises_on_few_samples(self) -> None:
        dd = DriftDetector()
        with pytest.raises(ValueError, match="at least 2"):
            dd.compute_baseline([{"x": 1}], metric="x")

    def test_detect_drift_true_when_beyond_threshold(self) -> None:
        dd = DriftDetector(name="test", deviation_threshold=2.0)
        samples = [{"val": i} for i in range(100)]  # mean=49.5, std≈29.0
        dd.compute_baseline(samples, metric="val")
        report = dd.detect("val", 1000.0)  # way beyond threshold
        assert report.is_drifted is True

    def test_detect_drift_false_when_within_threshold(self) -> None:
        dd = DriftDetector(name="test", deviation_threshold=3.0)
        samples = [{"val": i} for i in range(100)]
        dd.compute_baseline(samples, metric="val")
        report = dd.detect("val", 50.0)  # close to mean
        assert report.is_drifted is False

    def test_detect_returns_drifted_when_no_baseline(self) -> None:
        dd = DriftDetector(name="test")
        report = dd.detect("missing_metric", 100.0)
        assert report.is_drifted is True
        assert "No baseline" in report.details

    def test_set_baseline_manually(self) -> None:
        dd = DriftDetector(name="test")
        dd.set_baseline("latency", mean=100.0, std=20.0)
        report = dd.detect("latency", 200.0)
        assert report.is_drifted is True

    def test_get_baseline(self) -> None:
        dd = DriftDetector(name="test")
        dd.set_baseline("metric_x", mean=50.0, std=5.0)
        bl = dd.get_baseline("metric_x")
        assert bl is not None
        assert bl["mean"] == 50.0

    def test_get_baseline_returns_none_for_unknown(self) -> None:
        dd = DriftDetector(name="test")
        assert dd.get_baseline("nonexistent") is None

    def test_reset_clears_baselines(self) -> None:
        dd = DriftDetector(name="test")
        dd.set_baseline("m", mean=1.0, std=0.1)
        dd.reset()
        assert dd.get_baseline("m") is None

    def test_drift_report_dataclass(self) -> None:
        r = DriftReport(
            detector_name="test", metric="latency",
            drift_score=3.5, is_drifted=True,
        )
        assert r.detector_name == "test"
        assert r.is_drifted is True


# ====================================================================
# PromptRegressionTester Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="scheduled_scanning not impl")
class TestPromptRegressionTester:
    """Test PromptRegressionTester — score tracking and regression detection."""

    def test_record_score_stores_value(self) -> None:
        prt = PromptRegressionTester()
        prt.record_score("prompt-1", 0.85)
        assert prt.get_scores("prompt-1") == [0.85]

    def test_get_last_score_returns_most_recent(self) -> None:
        prt = PromptRegressionTester()
        prt.record_score("p1", 0.5)
        prt.record_score("p1", 0.8)
        assert prt.get_last_score("p1") == 0.8

    def test_get_last_score_returns_none_when_no_scores(self) -> None:
        prt = PromptRegressionTester()
        assert prt.get_last_score("unknown") is None

    def test_evaluate_detects_regression(self) -> None:
        prt = PromptRegressionTester(default_threshold=0.1)
        prt.record_score("p1", 0.9)  # previous score: 0.9
        report = prt.evaluate("p1", 0.5)  # current score: 0.5
        assert report.is_regression is True
        assert report.score_change < 0

    def test_evaluate_no_regression_when_score_improves(self) -> None:
        prt = PromptRegressionTester(default_threshold=0.1)
        prt.record_score("p1", 0.5)
        report = prt.evaluate("p1", 0.9)
        assert report.is_regression is False
        assert report.score_change > 0

    def test_evaluate_with_custom_threshold(self) -> None:
        prt = PromptRegressionTester(default_threshold=0.2)
        prt.record_score("p1", 0.8)
        report = prt.evaluate("p1", 0.7, threshold=0.05)
        assert report.is_regression is True  # -0.1 < -0.05

    def test_evaluate_raises_on_invalid_score(self) -> None:
        prt = PromptRegressionTester()
        with pytest.raises(ValueError, match="score"):
            prt.evaluate("p1", 1.5)

    def test_raises_on_invalid_default_threshold(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            PromptRegressionTester(default_threshold=0)

    def test_prompt_regression_report_dataclass(self) -> None:
        r = PromptRegressionReport(
            test_name="t1", prompt_id="p1",
            previous_score=0.9, current_score=0.5,
            score_change=-0.4, is_regression=True,
            threshold=0.1,
        )
        assert r.score_change == -0.4
        assert r.is_regression is True


# ====================================================================
# CostAnomalyDetector Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="scheduled_scanning not impl")
class TestCostAnomalyDetector:
    """Test CostAnomalyDetector — baseline cost and anomaly detection."""

    def test_set_baseline(self) -> None:
        cad = CostAnomalyDetector()
        cad.set_baseline("openai", 50.0)
        assert cad.get_baseline("openai") == 50.0

    def test_get_baseline_returns_none_for_unknown(self) -> None:
        cad = CostAnomalyDetector()
        assert cad.get_baseline("unknown") is None

    def test_set_baseline_raises_on_non_positive(self) -> None:
        cad = CostAnomalyDetector()
        with pytest.raises(ValueError, match="positive"):
            cad.set_baseline("openai", 0)

    def test_record_daily_cost(self) -> None:
        cad = CostAnomalyDetector()
        cad.record_daily_cost("openai", 75.0)
        assert cad.get_daily_costs("openai") == [75.0]

    def test_record_daily_cost_raises_on_negative(self) -> None:
        cad = CostAnomalyDetector()
        with pytest.raises(ValueError, match="non-negative"):
            cad.record_daily_cost("openai", -10.0)

    def test_check_returns_anomalous_when_over_threshold(self) -> None:
        cad = CostAnomalyDetector(deviation_threshold=1.5)
        cad.set_baseline("openai", 100.0)
        cad.record_daily_cost("openai", 200.0)  # ratio=2.0 > 1.5
        report = cad.check("openai")
        assert report.is_anomalous is True

    def test_check_returns_not_anomalous_when_within_threshold(self) -> None:
        cad = CostAnomalyDetector(deviation_threshold=2.0)
        cad.set_baseline("openai", 100.0)
        cad.record_daily_cost("openai", 120.0)  # ratio=1.2 < 2.0
        report = cad.check("openai")
        assert report.is_anomalous is False

    def test_check_uses_default_budget_when_no_baseline(self) -> None:
        cad = CostAnomalyDetector(default_daily_budget=100.0, deviation_threshold=1.5)
        cad.record_daily_cost("new-provider", 200.0)
        report = cad.check("new-provider")
        assert report.baseline_daily_cost == 100.0

    def test_check_zero_cost(self) -> None:
        cad = CostAnomalyDetector()
        cad.set_baseline("openai", 50.0)
        cad.record_daily_cost("openai", 0.0)
        report = cad.check("openai")
        assert report.is_anomalous is False  # ratio=0, not > threshold

    def test_reset_clears_data(self) -> None:
        cad = CostAnomalyDetector()
        cad.set_baseline("openai", 50.0)
        cad.record_daily_cost("openai", 100.0)
        cad.reset()
        assert cad.get_baseline("openai") is None
        assert cad.get_daily_costs("openai") == []


# ====================================================================
# SLAChecker Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="scheduled_scanning not impl")
class TestSLAChecker:
    """Test SLAChecker — latency, error rate, and uptime compliance."""

    def test_record_latency(self) -> None:
        sla = SLAChecker()
        sla.record_latency("openai", 100.0)
        report = sla.check_latency("openai", max_latency_ms=5000.0)
        assert report.provider == "openai"

    def test_check_latency_compliant(self) -> None:
        sla = SLAChecker()
        sla.record_latency("openai", 100.0)
        sla.record_latency("openai", 200.0)
        report = sla.check_latency("openai", max_latency_ms=500.0)
        assert report.compliance_status == ComplianceStatus.COMPLIANT

    def test_check_latency_breached(self) -> None:
        sla = SLAChecker()
        for _ in range(5):
            sla.record_latency("openai", 6000.0)
        report = sla.check_latency("openai", max_latency_ms=5000.0)
        assert report.compliance_status == ComplianceStatus.BREACHED

    def test_check_latency_warning(self) -> None:
        sla = SLAChecker()
        for _ in range(3):
            sla.record_latency("openai", 4500.0)  # 80% of 5000 = 4000
        report = sla.check_latency("openai", max_latency_ms=5000.0)
        assert report.compliance_status in (
            ComplianceStatus.COMPLIANT, ComplianceStatus.WARNING,
        )

    def test_check_latency_no_data(self) -> None:
        sla = SLAChecker()
        report = sla.check_latency("unknown", max_latency_ms=5000.0)
        assert report.compliance_status == ComplianceStatus.COMPLIANT

    def test_record_error(self) -> None:
        sla = SLAChecker()
        sla.record_error("openai")
        report = sla.check_error_rate("openai", max_error_rate=0.05)
        assert report.provider == "openai"

    def test_check_error_rate_breached(self) -> None:
        sla = SLAChecker()
        for _ in range(10):
            sla.record_error("openai")
        report = sla.check_error_rate("openai", max_error_rate=0.05)
        assert report.compliance_status == ComplianceStatus.BREACHED

    def test_record_uptime(self) -> None:
        sla = SLAChecker()
        sla.record_uptime("openai", True)
        report = sla.check_uptime("openai", min_uptime=0.99)
        assert report.provider == "openai"

    def test_check_uptime_compliant(self) -> None:
        sla = SLAChecker()
        for _ in range(100):
            sla.record_uptime("openai", True)
        report = sla.check_uptime("openai", min_uptime=0.99)
        assert report.compliance_status == ComplianceStatus.COMPLIANT

    def test_reset_clears_all(self) -> None:
        sla = SLAChecker()
        sla.record_latency("openai", 100.0)
        sla.record_error("openai")
        sla.record_uptime("openai", True)
        sla.reset()
        report = sla.check_latency("openai")
        assert report.compliance_status == ComplianceStatus.COMPLIANT


# ====================================================================
# Scheduler Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="scheduled_scanning not impl")
class TestScheduler:
    """Test Scheduler — task registration and due-task execution."""

    def test_add_task(self) -> None:
        sched = Scheduler()
        sched.add_task(
            "t1", ScanType.DRIFT, lambda: ScanResult(), interval_seconds=60.0
        )
        task = sched.get_task("t1")
        assert task is not None
        assert task["scan_type"] == "drift"

    def test_get_task_returns_none_for_unknown(self) -> None:
        sched = Scheduler()
        assert sched.get_task("unknown") is None

    def test_add_task_raises_on_duplicate(self) -> None:
        sched = Scheduler()
        sched.add_task("t1", ScanType.DRIFT, lambda: ScanResult())
        with pytest.raises(ValueError, match="already registered"):
            sched.add_task("t1", ScanType.DRIFT, lambda: ScanResult())

    def test_add_task_raises_on_non_positive_interval(self) -> None:
        sched = Scheduler()
        with pytest.raises(ValueError, match="positive"):
            sched.add_task(
                "t1", ScanType.DRIFT, lambda: ScanResult(), interval_seconds=0
            )

    def test_remove_task(self) -> None:
        sched = Scheduler()
        sched.add_task("t1", ScanType.DRIFT, lambda: ScanResult())
        sched.remove_task("t1")
        assert sched.get_task("t1") is None

    def test_list_tasks(self) -> None:
        sched = Scheduler()
        sched.add_task("t1", ScanType.DRIFT, lambda: ScanResult())
        sched.add_task("t2", ScanType.REGRESSION, lambda: ScanResult())
        tasks = sched.list_tasks()
        assert len(tasks) == 2

    def test_run_due_runs_expired_tasks(self) -> None:
        call_count: list[int] = [0]

        def callback() -> ScanResult:
            call_count[0] += 1
            return ScanResult()

        sched = Scheduler()
        tiny_interval = 0.001
        sched.add_task("t1", ScanType.DRIFT, callback, interval_seconds=tiny_interval)
        # Sleep briefly so the task is due
        import time as _time
        _time.sleep(0.01)
        results = sched.run_due()
        assert call_count[0] >= 1
        assert len(results) >= 1

    def test_run_all_runs_all_tasks(self) -> None:
        call_count: list[int] = [0]

        def callback() -> ScanResult:
            call_count[0] += 1
            return ScanResult()

        sched = Scheduler()
        sched.add_task("t1", ScanType.DRIFT, callback, interval_seconds=3600.0)
        sched.add_task("t2", ScanType.COST_ANOMALY, callback, interval_seconds=3600.0)
        results = sched.run_all()
        assert call_count[0] == 2
        assert len(results) == 2

    def test_run_due_handles_callback_exception(self) -> None:
        def failing_callback() -> ScanResult:
            msg = "Simulated failure"
            raise RuntimeError(msg)

        sched = Scheduler()
        tiny_interval = 0.001
        sched.add_task(
            "fail", ScanType.DRIFT, failing_callback,
            interval_seconds=tiny_interval,
        )
        import time as _time
        _time.sleep(0.01)
        results = sched.run_due()
        assert len(results) == 1
        assert results[0].success is False
        assert results[0].alert_level == AlertLevel.CRITICAL

    def test_start_stop_scheduler(self) -> None:
        sched = Scheduler()
        sched.start()
        assert sched.is_running is True
        sched.stop()
        assert sched.is_running is False


# ====================================================================
# Integration Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="scheduled_scanning not impl")
class TestIntegration:
    """Integration tests combining scanning components."""

    def test_drift_detector_with_scheduler(self) -> None:
        dd = DriftDetector(name="integration", deviation_threshold=2.0)
        samples = [{"val": i} for i in range(50)]
        dd.compute_baseline(samples, metric="val")


        def drift_scan() -> ScanResult:
            report = dd.detect("val", 100.0)
            return ScanResult(
                scan_type=ScanType.DRIFT,
                reports=[report],
                alert_level=(
                    AlertLevel.WARNING if report.is_drifted else AlertLevel.INFO
                ),
            )

        sched = Scheduler()
        sched.add_task("drift-check", ScanType.DRIFT, drift_scan, interval_seconds=60.0)
        results = sched.run_all()
        assert len(results) == 1
        assert len(results[0].reports) == 1
        assert results[0].reports[0].is_drifted is True

    def test_cost_anomaly_with_detector(self) -> None:
        cad = CostAnomalyDetector(deviation_threshold=1.5)
        cad.set_baseline("openai", 100.0)
        cad.record_daily_cost("openai", 200.0)

        def cost_scan() -> ScanResult:
            report = cad.check("openai")
            return ScanResult(
                scan_type=ScanType.COST_ANOMALY,
                reports=[report],
                summary=f"openai anomaly: {report.is_anomalous}",
            )

        sched = Scheduler()
        sched.add_task("cost-check", ScanType.COST_ANOMALY, cost_scan)
        results = sched.run_all()
        assert results[0].reports[0].is_anomalous is True

    def test_sla_checker_integration(self) -> None:
        sla = SLAChecker()
        for _ in range(10):
            sla.record_latency("openai", 100.0)
            sla.record_uptime("openai", True)

        def sla_scan() -> ScanResult:
            lat_report = sla.check_latency("openai", max_latency_ms=500.0)
            uptime_report = sla.check_uptime("openai", min_uptime=0.99)
            return ScanResult(
                scan_type=ScanType.SLA_CHECK,
                reports=[lat_report, uptime_report],
            )

        sched = Scheduler()
        sched.add_task("sla-check", ScanType.SLA_CHECK, sla_scan)
        results = sched.run_all()
        assert all(
            r.compliance_status == ComplianceStatus.COMPLIANT
            for r in results[0].reports
        )

    def test_prompt_regression_with_tester(self) -> None:
        prt = PromptRegressionTester(default_threshold=0.1)
        prt.record_score("prompt-a", 0.9)

        def regression_scan() -> ScanResult:
            report = prt.evaluate("prompt-a", 0.6)
            return ScanResult(
                scan_type=ScanType.REGRESSION,
                reports=[report],
                alert_level=(
                    AlertLevel.CRITICAL
                    if report.is_regression
                    else AlertLevel.INFO
                ),
            )

        sched = Scheduler()
        sched.add_task("regression-check", ScanType.REGRESSION, regression_scan)
        results = sched.run_all()
        assert results[0].reports[0].is_regression is True

    def test_scheduler_run_due_respects_interval(self) -> None:
        call_count: list[int] = [0]

        def infrequent() -> ScanResult:
            call_count[0] += 1
            return ScanResult()

        sched = Scheduler()
        sched.add_task("slow", ScanType.DRIFT, infrequent, interval_seconds=3600.0)
        # First run_all should trigger
        sched.run_all()
        c1 = call_count[0]
        # Immediate second run_all should NOT trigger (not due yet)
        results2 = sched.run_due()
        assert call_count[0] == c1  # no additional calls
        assert len(results2) == 0

    def test_scheduler_preserves_task_metadata(self) -> None:
        sched = Scheduler()
        sched.add_task(
            "m1", ScanType.DRIFT, lambda: ScanResult(),
            interval_seconds=300.0, name="my-scan",
        )
        sched.run_all()
        task = sched.get_task("m1")
        assert task is not None
        assert task["run_count"] == 1
        assert task["name"] == "my-scan"
