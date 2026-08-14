"""Example: Scheduled Scanning & Monitoring.

Demonstrates drift detection, prompt regression testing, cost anomaly
detection, SLA compliance checking, and the scheduler.
"""

from __future__ import annotations

from ai_vibe_coding.scheduled_scanning import (
    AlertLevel,
    CostAnomalyDetector,
    DriftDetector,
    PromptRegressionTester,
    ScanResult,
    ScanType,
    Scheduler,
    SLAChecker,
)


def drift_detection_example() -> None:
    """Drift detection on model response metrics."""
    print("=== DriftDetector Example ===")

    detector = DriftDetector(name="response-length", deviation_threshold=2.5)

    # Build baseline from historical samples
    samples = [{"response_length": 100 + i * 2} for i in range(100)]
    baseline = detector.compute_baseline(samples, metric="response_length")
    print(f"  Baseline: mean={baseline['mean']:.1f}, std={baseline['std']:.1f}")

    # Normal observation
    report = detector.detect("response_length", 200.0)
    print(f"  Normal observation (200): drifted={report.is_drifted}, "
          f"z-score={report.drift_score:.2f}")

    # Drifted observation
    report = detector.detect("response_length", 500.0)
    print(f"  Drifted observation (500): drifted={report.is_drifted}, "
          f"z-score={report.drift_score:.2f}")


def prompt_regression_example() -> None:
    """Prompt regression testing over time."""
    print("\n=== PromptRegressionTester Example ===")

    tester = PromptRegressionTester(default_threshold=0.1)

    # First evaluation (no previous score - uses 0.0)
    report = tester.evaluate("code-review-prompt", 0.85)
    print(f"  Initial: score={report.current_score:.2f}, "
          f"regression={report.is_regression}")

    # Improved score
    report = tester.evaluate("code-review-prompt", 0.92)
    print(f"  Improved: score={report.current_score:.2f}, "
          f"Δ={report.score_change:+.4f}, regression={report.is_regression}")

    # Regression
    report = tester.evaluate("code-review-prompt", 0.65)
    print(f"  Regression: score={report.current_score:.2f}, "
          f"Δ={report.score_change:+.4f}, regression={report.is_regression}")

    print(f"  All scores: {tester.get_scores('code-review-prompt')}")


def cost_anomaly_example() -> None:
    """Cost anomaly detection."""
    print("\n=== CostAnomalyDetector Example ===")

    detector = CostAnomalyDetector(deviation_threshold=1.5)

    detector.set_baseline("openai", 50.0)  # $50/day baseline

    # Normal day
    detector.record_daily_cost("openai", 45.0)
    report = detector.check("openai")
    print(f"  Normal day ($45): anomalous={report.is_anomalous}, "
          f"ratio={report.deviation_ratio:.2f}")

    # Spike day
    detector.record_daily_cost("openai", 150.0)
    report = detector.check("openai")
    print(f"  Spike day ($150): anomalous={report.is_anomalous}, "
          f"ratio={report.deviation_ratio:.2f}")


def sla_checking_example() -> None:
    """SLA compliance monitoring."""
    print("\n=== SLAChecker Example ===")

    checker = SLAChecker()

    # Good latency
    for _ in range(10):
        checker.record_latency("openai", 200.0)
    report = checker.check_latency("openai", max_latency_ms=2000.0)
    print(f"  Latency: {report.compliance_status.value}, "
          f"avg={report.actual_value:.0f}ms")

    # Bad uptime
    for _ in range(3):
        checker.record_uptime("openai", False)
    checker.record_uptime("openai", True)
    report = checker.check_uptime("openai", min_uptime=0.95)
    print(f"  Uptime: {report.compliance_status.value}, "
          f"rate={report.actual_value:.2%}")


def scheduler_example() -> None:
    """Scheduler with multiple scanning tasks."""
    print("\n=== Scheduler Example ===")

    detector = DriftDetector(name="prod", deviation_threshold=2.0)
    samples = [{"val": i * 3} for i in range(50)]
    detector.compute_baseline(samples, metric="val")

    def drift_scan() -> ScanResult:
        """Drift scanning task."""
        report = detector.detect("val", 200.0)
        return ScanResult(
            scan_type=ScanType.DRIFT,
            reports=[report],
            alert_level=AlertLevel.WARNING if report.is_drifted else AlertLevel.INFO,
            summary=f"drift_check: drifted={report.is_drifted}",
        )

    def sla_scan() -> ScanResult:
        """SLA checking task."""
        checker = SLAChecker()
        checker.record_latency("openai", 150.0)
        checker.record_uptime("openai", True)
        lat_report = checker.check_latency("openai", max_latency_ms=1000.0)
        up_report = checker.check_uptime("openai", min_uptime=0.99)
        return ScanResult(
            scan_type=ScanType.SLA_CHECK,
            reports=[lat_report, up_report],
        )

    # Set up scheduler
    sched = Scheduler()
    sched.add_task("drift-check", ScanType.DRIFT, drift_scan, interval_seconds=3600.0)
    sched.add_task("sla-check", ScanType.SLA_CHECK, sla_scan, interval_seconds=300.0)

    print("  Registered tasks:")
    for t in sched.list_tasks():
        print(f"    {t['name']} ({t['scan_type']}) every {t['interval_seconds']}s")

    # Run all immediately
    results = sched.run_all()
    for r in results:
        print(f"  Ran: {r.summary}")
        print(f"    Success: {r.success}, Reports: {len(r.reports)}")


def integration_with_cost_calculator() -> None:
    """Integration with cost_calculator from v0.8.0."""
    print("\n=== Integration with Cost Calculator ===")

    from ai_vibe_coding.cost_calculator import calculate_cost, compare_all

    # Cost check for different providers
    costs = compare_all(1000, 500, providers=["openai", "anthropic", "deepseek"])
    print("  Cost comparison (1000 in / 500 out tokens):")
    for c in costs:
        cpt = c['cost_per_1k_tokens']
        total = c['total_cost']
        print(f"    {c['provider']:12s} {c['model']:20s} "
              f"${total:.6f} total (${cpt:.6f}/1K)")

    # Use with cost anomaly detector
    detector = CostAnomalyDetector(deviation_threshold=1.5)
    openai_cost = calculate_cost(1_000_000, 500_000, "openai", "gpt-4")
    detector.set_baseline("openai", openai_cost)

    # Later, check if current cost is anomalous
    current_cost = calculate_cost(2_500_000, 1_000_000, "openai", "gpt-4")
    detector.record_daily_cost("openai", current_cost)
    report = detector.check("openai")
    print("\n  Cost anomaly for openai:")
    print(f"    Baseline: ${report.baseline_daily_cost:.4f}/day")
    print(f"    Current:  ${report.current_daily_cost:.4f}/day")
    print(f"    Ratio:    {report.deviation_ratio:.2f}x")
    print(f"    Anomaly:  {report.is_anomalous}")


if __name__ == "__main__":
    drift_detection_example()
    prompt_regression_example()
    cost_anomaly_example()
    sla_checking_example()
    scheduler_example()
    integration_with_cost_calculator()
