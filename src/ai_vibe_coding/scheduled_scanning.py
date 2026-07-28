"""Scheduled Scanning & Monitoring for LLM Pipelines.

Provides drift detection, prompt regression testing, cost anomaly
detection, SLA compliance checking, and a scheduler for periodic
execution.

Integrates with cost_calculator for cost tracking.
"""

from __future__ import annotations

import enum
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ======================================================================
# Enums
# ======================================================================


class AlertLevel(enum.Enum):
    """Severity level for scanning alerts."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ComplianceStatus(enum.Enum):
    """SLA compliance status."""

    COMPLIANT = "compliant"
    WARNING = "warning"
    BREACHED = "breached"


class ScanType(enum.Enum):
    """Types of scanning tasks."""

    DRIFT = "drift"
    REGRESSION = "regression"
    COST_ANOMALY = "cost_anomaly"
    SLA_CHECK = "sla_check"


# ======================================================================
# Data classes
# ======================================================================


@dataclass
class DriftReport:
    """Result of a drift detection scan."""

    detector_name: str = ""
    model_id: str = ""
    baseline_version: str = ""
    current_version: str = ""
    drift_score: float = 0.0
    is_drifted: bool = False
    metric: str = ""
    details: str = ""


@dataclass
class PromptRegressionReport:
    """Result of a prompt regression test."""

    test_name: str = ""
    prompt_id: str = ""
    previous_score: float = 0.0
    current_score: float = 0.0
    score_change: float = 0.0
    is_regression: bool = False
    threshold: float = 0.0
    details: str = ""


@dataclass
class CostAnomalyReport:
    """Result of a cost anomaly check."""

    provider: str = ""
    baseline_daily_cost: float = 0.0
    current_daily_cost: float = 0.0
    deviation_ratio: float = 0.0
    is_anomalous: bool = False
    threshold: float = 0.0
    details: str = ""


@dataclass
class SLAReport:
    """Result of an SLA compliance check."""

    provider: str = ""
    check_name: str = ""
    compliance_status: ComplianceStatus = ComplianceStatus.COMPLIANT
    actual_value: float = 0.0
    threshold: float = 0.0
    window_duration_seconds: float = 0.0
    details: str = ""


@dataclass
class ScanResult:
    """Generic result from any scanning task."""

    scan_type: ScanType = ScanType.DRIFT
    timestamp: float = 0.0
    success: bool = True
    reports: list[Any] = field(default_factory=list)
    alert_level: AlertLevel = AlertLevel.INFO
    summary: str = ""


# ======================================================================
# DriftDetector
# ======================================================================


class DriftDetector:
    """Detects statistical drift in model responses compared to a baseline.

    Supports comparison of response metrics (e.g. response length, token count,
    sentiment scores) against computed baselines using configurable deviation
    thresholds.
    """

    def __init__(
        self,
        name: str = "default",
        deviation_threshold: float = 2.0,
        window_size: int = 100,
    ) -> None:
        if deviation_threshold <= 0:
            raise ValueError("deviation_threshold must be positive")
        if window_size <= 0:
            raise ValueError("window_size must be positive")
        self._name = name
        self._deviation_threshold = deviation_threshold
        self._window_size = window_size
        self._baseline: dict[str, Any] = {}
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self._name

    @property
    def deviation_threshold(self) -> float:
        return self._deviation_threshold

    def compute_baseline(
        self,
        samples: list[dict[str, Any]],
        metric: str = "response_length",
    ) -> dict[str, float]:
        """Compute a statistical baseline from sample data.

        Args:
            samples: List of dicts containing metric values.
            metric: The metric key to extract from each sample.

        Returns:
            A dict with "mean", "std", "count", and "metric" keys.
        """
        if not samples:
            raise ValueError("Cannot compute baseline from empty samples")

        with self._lock:
            values = [s[metric] for s in samples if metric in s]
            if len(values) < 2:
                raise ValueError(
                    f"Need at least 2 valid samples for metric '{metric}', "
                    f"got {len(values)}"
                )

            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
            std = math.sqrt(variance)

            baseline = {
                "mean": mean,
                "std": std,
                "count": len(values),
                "metric": metric,
            }
            # Store as versioned baseline
            version = str(int(time.time()))
            self._baseline[metric] = {
                **baseline,
                "version": version,
            }
            return baseline

    def set_baseline(
        self,
        metric: str,
        mean: float,
        std: float,
        version: str = "manual",
    ) -> None:
        """Manually set a baseline for a metric."""
        with self._lock:
            self._baseline[metric] = {
                "mean": mean,
                "std": std,
                "version": version,
            }

    def get_baseline(self, metric: str) -> dict[str, Any] | None:
        """Get the stored baseline for a metric."""
        return self._baseline.get(metric)

    def detect(self, metric: str, value: float) -> DriftReport:
        """Detect drift in a single metric value against the baseline.

        Args:
            metric: The metric name to check.
            value: The current observed value.

        Returns:
            A DriftReport indicating whether drift was detected.
        """
        with self._lock:
            if metric not in self._baseline:
                return DriftReport(
                    detector_name=self._name,
                    metric=metric,
                    is_drifted=True,
                    details=f"No baseline for metric '{metric}'",
                )

            baseline = self._baseline[metric]
            mean = baseline["mean"]
            std = baseline["std"]
            version = baseline["version"]

            if std == 0:
                # If std is 0, any deviation from mean is drift
                drift_score = value - mean if value != mean else 0.0
                is_drifted = value != mean
            else:
                # Z-score: how many standard deviations from the mean
                drift_score = (value - mean) / std
                is_drifted = abs(drift_score) > self._deviation_threshold

            details_parts = [
                f"value={value:.2f}, mean={mean:.2f}, std={std:.2f}",
                f"z-score={drift_score:.2f}",
                f"threshold={self._deviation_threshold:.2f}",
            ]

            return DriftReport(
                detector_name=self._name,
                metric=metric,
                baseline_version=version,
                current_version=f"v{int(time.time())}",
                drift_score=drift_score,
                is_drifted=is_drifted,
                details="; ".join(details_parts),
            )

    def reset(self) -> None:
        """Clear all stored baselines."""
        with self._lock:
            self._baseline.clear()


# ======================================================================
# PromptRegressionTester
# ======================================================================


class PromptRegressionTester:
    """Evaluates prompts over time to detect score regression.

    Tracks previous and current quality scores for prompts and flags
    regressions exceeding a configurable threshold.
    """

    def __init__(
        self,
        default_threshold: float = 0.1,
    ) -> None:
        if default_threshold <= 0:
            raise ValueError("default_threshold must be positive")
        self._default_threshold = default_threshold
        self._scores: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    @property
    def default_threshold(self) -> float:
        return self._default_threshold

    def record_score(self, prompt_id: str, score: float) -> None:
        """Record a quality score for a prompt."""
        if not 0.0 <= score <= 1.0:
            raise ValueError("score must be in [0.0, 1.0]")
        with self._lock:
            if prompt_id not in self._scores:
                self._scores[prompt_id] = []
            self._scores[prompt_id].append(score)

    def get_scores(self, prompt_id: str) -> list[float]:
        """Get all recorded scores for a prompt."""
        with self._lock:
            return list(self._scores.get(prompt_id, []))

    def get_last_score(self, prompt_id: str) -> float | None:
        """Get the most recently recorded score."""
        with self._lock:
            scores = self._scores.get(prompt_id, [])
            return scores[-1] if scores else None

    def evaluate(
        self,
        prompt_id: str,
        current_score: float,
        threshold: float | None = None,
    ) -> PromptRegressionReport:
        """Evaluate a new score against the previous one.

        Args:
            prompt_id: The prompt identifier.
            current_score: The current evaluation score (0.0–1.0).
            threshold: Override the default regression threshold.

        Returns:
            A PromptRegressionReport with the comparison.
        """
        if not 0.0 <= current_score <= 1.0:
            raise ValueError("current_score must be in [0.0, 1.0]")

        effective_threshold = threshold or self._default_threshold

        with self._lock:
            previous_score = (
                self._scores[prompt_id][-1]
                if prompt_id in self._scores and self._scores[prompt_id]
                else 0.0
            )

        score_change = current_score - previous_score
        is_regression = score_change < -effective_threshold

        report = PromptRegressionReport(
            test_name=f"regression-test-{prompt_id}",
            prompt_id=prompt_id,
            previous_score=previous_score,
            current_score=current_score,
            score_change=round(score_change, 4),
            is_regression=is_regression,
            threshold=effective_threshold,
            details=(
                f"Score changed from {previous_score:.2f} to {current_score:.2f} "
                f"(Δ={score_change:+.4f}, threshold={effective_threshold})"
            ),
        )

        # Record the new score
        self.record_score(prompt_id, current_score)
        return report


# ======================================================================
# CostAnomalyDetector
# ======================================================================


class CostAnomalyDetector:
    """Detects anomalous cost patterns based on baseline profiles.

    Tracks daily costs per provider and flags deviations exceeding a
    configurable threshold ratio.
    """

    def __init__(
        self,
        deviation_threshold: float = 1.5,
        default_daily_budget: float = 100.0,
    ) -> None:
        if deviation_threshold <= 0:
            raise ValueError("deviation_threshold must be positive")
        if default_daily_budget <= 0:
            raise ValueError("default_daily_budget must be positive")
        self._deviation_threshold = deviation_threshold
        self._default_daily_budget = default_daily_budget
        self._daily_costs: dict[str, list[float]] = {}
        self._baselines: dict[str, float] = {}
        self._lock = threading.Lock()

    @property
    def deviation_threshold(self) -> float:
        return self._deviation_threshold

    def set_baseline(self, provider: str, baseline_daily_cost: float) -> None:
        """Set the expected daily cost baseline for a provider."""
        if baseline_daily_cost <= 0:
            raise ValueError("baseline_daily_cost must be positive")
        with self._lock:
            self._baselines[provider] = baseline_daily_cost

    def get_baseline(self, provider: str) -> float | None:
        """Get the baseline daily cost for a provider."""
        return self._baselines.get(provider)

    def record_daily_cost(self, provider: str, cost: float) -> None:
        """Record a daily cost observation for a provider."""
        if cost < 0:
            raise ValueError("cost must be non-negative")
        with self._lock:
            if provider not in self._daily_costs:
                self._daily_costs[provider] = []
            self._daily_costs[provider].append(cost)

    def get_daily_costs(self, provider: str) -> list[float]:
        """Get all recorded daily costs for a provider."""
        with self._lock:
            return list(self._daily_costs.get(provider, []))

    def check(self, provider: str) -> CostAnomalyReport:
        """Check if the current daily cost is anomalous for a provider.

        If no baseline exists for the provider, uses the default_daily_budget.
        If no current cost has been recorded, assumes zero.
        """
        with self._lock:
            baseline_daily = self._baselines.get(
                provider, self._default_daily_budget
            )
            costs = self._daily_costs.get(provider, [])
            current_cost = costs[-1] if costs else 0.0

            if baseline_daily == 0:
                deviation_ratio = 0.0
                is_anomalous = True
                details = "No baseline cost set; flagging as anomalous"
            else:
                deviation_ratio = current_cost / baseline_daily
                is_anomalous = deviation_ratio > self._deviation_threshold
                details = (
                    f"Current cost ${current_cost:.2f} vs "
                    f"baseline ${baseline_daily:.2f}/day "
                    f"(ratio={deviation_ratio:.2f}, "
                    f"threshold={self._deviation_threshold})"
                )

            return CostAnomalyReport(
                provider=provider,
                baseline_daily_cost=baseline_daily,
                current_daily_cost=current_cost,
                deviation_ratio=deviation_ratio,
                is_anomalous=is_anomalous,
                threshold=self._deviation_threshold,
                details=details,
            )

    def reset(self) -> None:
        """Clear all stored baselines and cost data."""
        with self._lock:
            self._daily_costs.clear()
            self._baselines.clear()


# ======================================================================
# SLAChecker
# ======================================================================


class SLAChecker:
    """Checks SLA compliance for latency, error rate, and uptime.

    Tracks metrics within sliding windows and compares against
    configurable thresholds.
    """

    def __init__(self) -> None:
        self._latency_samples: dict[str, list[tuple[float, float]]] = {}
        self._error_counts: dict[str, list[tuple[float, int]]] = {}
        self._uptime_records: dict[str, list[tuple[float, bool]]] = {}
        self._lock = threading.Lock()

    def record_latency(self, provider: str, latency_ms: float) -> None:
        """Record a latency sample for a provider."""
        with self._lock:
            if provider not in self._latency_samples:
                self._latency_samples[provider] = []
            self._latency_samples[provider].append((time.time(), latency_ms))

    def record_error(self, provider: str) -> None:
        """Record an error occurrence for a provider."""
        with self._lock:
            if provider not in self._error_counts:
                self._error_counts[provider] = []
            self._error_counts[provider].append((time.time(), 1))

    def record_uptime(self, provider: str, is_up: bool) -> None:
        """Record an uptime check result for a provider."""
        with self._lock:
            if provider not in self._uptime_records:
                self._uptime_records[provider] = []
            self._uptime_records[provider].append((time.time(), is_up))

    def check_latency(
        self,
        provider: str,
        max_latency_ms: float = 5000.0,
        window_seconds: float = 300.0,
    ) -> SLAReport:
        """Check if average latency for a provider is within SLA.

        Args:
            provider: Provider to check.
            max_latency_ms: Maximum allowed average latency.
            window_seconds: Look-back window for latency samples.

        Returns:
            An SLAReport with the compliance status.
        """
        cutoff = time.time() - window_seconds
        with self._lock:
            samples = self._latency_samples.get(provider, [])
            recent = [lat for ts, lat in samples if ts >= cutoff]
            if not recent:
                return SLAReport(
                    provider=provider,
                    check_name="latency-sla",
                    compliance_status=ComplianceStatus.COMPLIANT,
                    actual_value=0.0,
                    threshold=max_latency_ms,
                    window_duration_seconds=window_seconds,
                    details="No latency samples in window",
                )

            avg_latency = sum(recent) / len(recent)
            status = ComplianceStatus.COMPLIANT
            if avg_latency > max_latency_ms:
                status = ComplianceStatus.BREACHED
            elif avg_latency > max_latency_ms * 0.8:
                status = ComplianceStatus.WARNING

            return SLAReport(
                provider=provider,
                check_name="latency-sla",
                compliance_status=status,
                actual_value=avg_latency,
                threshold=max_latency_ms,
                window_duration_seconds=window_seconds,
                details=(
                    f"Average latency {avg_latency:.1f}ms "
                    f"(threshold {max_latency_ms}ms) over {len(recent)} samples"
                ),
            )

    def check_error_rate(
        self,
        provider: str,
        max_error_rate: float = 0.05,
        window_seconds: float = 300.0,
    ) -> SLAReport:
        """Check if the error rate for a provider is within SLA.

        Args:
            provider: Provider to check.
            max_error_rate: Maximum allowed error rate (0.0–1.0).
            window_seconds: Look-back window.

        Returns:
            An SLAReport with the compliance status.
        """
        cutoff = time.time() - window_seconds
        with self._lock:
            errors = [
                cnt for ts, cnt in self._error_counts.get(provider, []) if ts >= cutoff
            ]
            total_errors = sum(errors)
            uptime = [
                is_up
                for ts, is_up in self._uptime_records.get(provider, [])
                if ts >= cutoff
            ]

            total_checks = len(uptime) + len(errors)
            if total_checks == 0:
                return SLAReport(
                    provider=provider,
                    check_name="error-rate-sla",
                    compliance_status=ComplianceStatus.COMPLIANT,
                    actual_value=0.0,
                    threshold=max_error_rate,
                    window_duration_seconds=window_seconds,
                    details="No error data in window",
                )

            actual_rate = total_errors / total_checks
            status = ComplianceStatus.COMPLIANT
            if actual_rate > max_error_rate:
                status = ComplianceStatus.BREACHED
            elif actual_rate > max_error_rate * 0.8:
                status = ComplianceStatus.WARNING

            return SLAReport(
                provider=provider,
                check_name="error-rate-sla",
                compliance_status=status,
                actual_value=actual_rate,
                threshold=max_error_rate,
                window_duration_seconds=window_seconds,
                details=(
                    f"Error rate {actual_rate:.4f} "
                    f"(threshold {max_error_rate}) over {total_checks} checks"
                ),
            )

    def check_uptime(
        self,
        provider: str,
        min_uptime: float = 0.99,
        window_seconds: float = 300.0,
    ) -> SLAReport:
        """Check if uptime for a provider meets the SLA.

        Args:
            provider: Provider to check.
            min_uptime: Minimum acceptable uptime ratio (0.0–1.0).
            window_seconds: Look-back window.

        Returns:
            An SLAReport with the compliance status.
        """
        cutoff = time.time() - window_seconds
        with self._lock:
            records = self._uptime_records.get(provider, [])
            recent = [is_up for ts, is_up in records if ts >= cutoff]

            if not recent:
                return SLAReport(
                    provider=provider,
                    check_name="uptime-sla",
                    compliance_status=ComplianceStatus.COMPLIANT,
                    actual_value=1.0,
                    threshold=min_uptime,
                    window_duration_seconds=window_seconds,
                    details="No uptime data in window",
                )

            uptime_ratio = sum(1 for r in recent if r) / len(recent)
            status = ComplianceStatus.COMPLIANT
            if uptime_ratio < min_uptime:
                status = ComplianceStatus.BREACHED
            elif uptime_ratio < min_uptime * 1.01:
                status = ComplianceStatus.WARNING

            return SLAReport(
                provider=provider,
                check_name="uptime-sla",
                compliance_status=status,
                actual_value=uptime_ratio,
                threshold=min_uptime,
                window_duration_seconds=window_seconds,
                details=(
                    f"Uptime {uptime_ratio:.4f} "
                    f"(threshold {min_uptime}) over {len(recent)} checks"
                ),
            )

    def reset(self) -> None:
        """Clear all recorded data."""
        with self._lock:
            self._latency_samples.clear()
            self._error_counts.clear()
            self._uptime_records.clear()


# ======================================================================
# Scheduler
# ======================================================================


class Scheduler:
    """Cron/interval-based scheduler for periodic scanning tasks.

    Manages a list of scheduled tasks, each with a defined interval,
    and runs them at the appropriate times.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    def add_task(
        self,
        task_id: str,
        scan_type: ScanType,
        callback: Callable[[], ScanResult],
        interval_seconds: float = 3600.0,
        name: str = "",
    ) -> None:
        """Register a scheduled task.

        Args:
            task_id: Unique identifier for the task.
            scan_type: Type of scan to perform.
            callback: Function to call when the task runs.
            interval_seconds: How often to run the task (seconds).
            name: Optional human-readable name.
        """
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")

        with self._lock:
            if task_id in self._tasks:
                raise ValueError(f"Task '{task_id}' already registered")

            self._tasks[task_id] = {
                "task_id": task_id,
                "scan_type": scan_type,
                "callback": callback,
                "interval_seconds": interval_seconds,
                "name": name or task_id,
                "last_run": 0.0,
                "next_run": time.time() + interval_seconds,
                "run_count": 0,
                "last_result": None,
            }

    def remove_task(self, task_id: str) -> None:
        """Remove a scheduled task."""
        with self._lock:
            self._tasks.pop(task_id, None)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Get task details."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            return {
                "task_id": task["task_id"],
                "scan_type": task["scan_type"].value,
                "name": task["name"],
                "interval_seconds": task["interval_seconds"],
                "last_run": task["last_run"],
                "next_run": task["next_run"],
                "run_count": task["run_count"],
            }

    def list_tasks(self) -> list[dict[str, Any]]:
        """List all registered tasks."""
        with self._lock:
            return [
                {
                    "task_id": t["task_id"],
                    "scan_type": t["scan_type"].value,
                    "name": t["name"],
                    "interval_seconds": t["interval_seconds"],
                    "last_run": t["last_run"],
                    "next_run": t["next_run"],
                    "run_count": t["run_count"],
                }
                for t in self._tasks.values()
            ]

    def run_due(self) -> list[ScanResult]:
        """Run all tasks whose interval has elapsed.

        Returns a list of ScanResult from executed tasks.
        """
        now = time.time()
        results: list[ScanResult] = []

        with self._lock:
            due: list[dict[str, Any]] = [
                t
                for t in self._tasks.values()
                if t["next_run"] <= now
            ]

        for task in due:
            try:
                result = task["callback"]()
                result.scan_type = task["scan_type"]
                result.timestamp = time.time()
                result.summary = f"{task['name']}: {len(result.reports)} reports"
            except Exception as e:
                result = ScanResult(
                    scan_type=task["scan_type"],
                    timestamp=time.time(),
                    success=False,
                    alert_level=AlertLevel.CRITICAL,
                    summary=f"{task['name']} failed: {e}",
                )

            with self._lock:
                task["last_run"] = time.time()
                task["next_run"] = task["last_run"] + task["interval_seconds"]
                task["run_count"] += 1
                task["last_result"] = result

            results.append(result)

        return results

    def run_all(self) -> list[ScanResult]:
        """Run all registered tasks immediately, regardless of schedule."""
        results: list[ScanResult] = []

        with self._lock:
            tasks_snapshot = list(self._tasks.values())

        for task in tasks_snapshot:
            try:
                result = task["callback"]()
                result.scan_type = task["scan_type"]
                result.timestamp = time.time()
                result.summary = f"{task['name']}: {len(result.reports)} reports"
            except Exception as e:
                result = ScanResult(
                    scan_type=task["scan_type"],
                    timestamp=time.time(),
                    success=False,
                    alert_level=AlertLevel.CRITICAL,
                    summary=f"{task['name']} failed: {e}",
                )

            with self._lock:
                task["last_run"] = time.time()
                task["next_run"] = task["last_run"] + task["interval_seconds"]
                task["run_count"] += 1
                task["last_result"] = result

            results.append(result)

        return results

    def start(self) -> None:
        """Start the scheduler background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the scheduler background thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._thread = None

    def _run_loop(self) -> None:
        """Background loop to run due tasks."""
        while self._running:
            self.run_due()
            time.sleep(1.0)

    @property
    def is_running(self) -> bool:
        return self._running and (self._thread is not None and self._thread.is_alive())

    def reset(self) -> None:
        """Remove all tasks and stop the scheduler."""
        self.stop()
        with self._lock:
            self._tasks.clear()


__all__ = [
    "AlertLevel",
    "ComplianceStatus",
    "CostAnomalyDetector",
    "CostAnomalyReport",
    "DriftDetector",
    "DriftReport",
    "PromptRegressionReport",
    "PromptRegressionTester",
    "SLAChecker",
    "SLAReport",
    "ScanResult",
    "ScanType",
    "Scheduler",
]
