"""Metrics aggregation and reporting for benchmark results.

Collects, aggregates, and reports accuracy, latency, cost, and reliability
metrics from benchmark results. Wraps CostTracker for cost metrics.

Module dependencies: benchmark_runner (new), cost_tracker (existing), stdlib
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC
from typing import Any

from ai_vibe_coding.benchmark_runner import BenchmarkResult
from ai_vibe_coding.cost_tracker import CostSummary

# ──────────────────────────────────────────────────────────────
# Data classes (fully implemented — pure data containers)
# ──────────────────────────────────────────────────────────────


@dataclass
class TaskMetrics:
    """Aggregated metrics for a single task across runs and providers.

    Attributes:
        task_id: Unique task identifier.
        task_name: Human-readable task name.
        best_provider: Provider with highest accuracy.
        best_model: Model with highest accuracy.
        provider_rankings: Sorted by accuracy.
        accuracy_mean: Average accuracy across runs.
        accuracy_std: Standard deviation of accuracy.
        avg_latency_ms: Average end-to-end latency.
        avg_cost_usd: Average cost per run.
        error_rate: Fraction of calls that errored.
        run_count: Number of runs aggregated.
    """

    task_id: str
    task_name: str
    best_provider: str | None = None
    best_model: str | None = None
    provider_rankings: list[dict[str, Any]] = field(default_factory=list)
    accuracy_mean: float = 0.0
    accuracy_std: float = 0.0
    avg_latency_ms: float = 0.0
    avg_cost_usd: float = 0.0
    error_rate: float = 0.0
    run_count: int = 0


@dataclass
class BenchmarkReport:
    """Full report for a benchmark session.

    Attributes:
        title: Report title.
        timestamp: ISO timestamp of report generation.
        tasks: Maps task_id -> TaskMetrics.
        provider_summary: Provider -> aggregated stats.
        model_summary: Model -> aggregated stats.
        total_cost: Total cost across all runs.
        total_runs: Total number of runs.
    """

    title: str = "Benchmark Report"
    timestamp: str = ""
    tasks: dict[str, TaskMetrics] = field(default_factory=dict)
    provider_summary: dict[str, dict] = field(default_factory=dict)
    model_summary: dict[str, dict] = field(default_factory=dict)
    total_cost: float = 0.0
    total_runs: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Full JSON-serializable report.

        Returns:
            A dictionary representation of the report suitable for JSON serialization.
        """
        return {
            "title": self.title,
            "timestamp": self.timestamp,
            "tasks": {
                task_id: {
                    "task_id": tm.task_id,
                    "task_name": tm.task_name,
                    "best_provider": tm.best_provider,
                    "best_model": tm.best_model,
                    "provider_rankings": tm.provider_rankings,
                    "accuracy_mean": tm.accuracy_mean,
                    "accuracy_std": tm.accuracy_std,
                    "avg_latency_ms": tm.avg_latency_ms,
                    "avg_cost_usd": tm.avg_cost_usd,
                    "error_rate": tm.error_rate,
                    "run_count": tm.run_count,
                }
                for task_id, tm in self.tasks.items()
            },
            "provider_summary": self.provider_summary,
            "model_summary": self.model_summary,
            "total_cost": self.total_cost,
            "total_runs": self.total_runs,
        }

    def to_markdown(self, output_path: str | None = None) -> str:
        """Render as markdown with tables. Optionally write to file.

        Args:
            output_path: Optional path to write the markdown file.

        Returns:
            A markdown-formatted string with task and provider summaries.
        """
        lines = [f"# {self.title}", f"_Generated: {self.timestamp}_\n"]

        # Overall summary
        lines.append("## Overall Summary\n")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Runs | {self.total_runs} |")
        lines.append(f"| Total Cost | ${self.total_cost:.4f} |")
        lines.append("")

        # Tasks table
        if self.tasks:
            lines.append("## Task Metrics\n")
            lines.append(
                "| Task ID | Name | Accuracy (mean±std) | Avg Latency (ms) "
                "| Avg Cost ($) | Error Rate | Best Provider |"
            )
            lines.append(
                "|---------|------|---------------------|------------------"
                "|-------------|------------|---------------|"
            )
            for task_id, tm in self.tasks.items():
                acc_str = f"{tm.accuracy_mean:.2f}±{tm.accuracy_std:.2f}"
                best_prov = tm.best_provider or "—"
                lines.append(
                    f"| {task_id} | {tm.task_name} | {acc_str} "
                    f"| {tm.avg_latency_ms:.1f} | {tm.avg_cost_usd:.4f} "
                    f"| {tm.error_rate:.2%} | {best_prov} |"
                )

        md = "\n".join(lines)

        if output_path:
            from pathlib import Path

            Path(output_path).write_text(md)

        return md

    def to_ascii_table(self) -> str:
        """Simple console-friendly ASCII table.

        Returns:
            An ASCII-formatted table string summarizing the report.
        """
        lines = [
            "=" * 60,
            f"  {self.title}",
            "=" * 60,
            f"  Total Runs: {self.total_runs}",
            f"  Total Cost: ${self.total_cost:.4f}",
            "-" * 60,
        ]

        if self.tasks:
            lines.append("  Tasks:")
            lines.append(
                "  {:20s} {:12s} {:12s} {:10s}".format(
                    "Task ID", "Accuracy", "Latency", "Cost",
                ),
            )
            lines.append(
                "  {:20s} {:12s} {:12s} {:10s}".format(
                    "-" * 20, "-" * 12, "-" * 12, "-" * 10,
                ),
            )
            for task_id, tm in self.tasks.items():
                acc = f"{tm.accuracy_mean:.2f}" if tm.run_count > 0 else "—"
                lat = f"{tm.avg_latency_ms:.1f}ms" if tm.run_count > 0 else "—"
                cost = f"${tm.avg_cost_usd:.4f}" if tm.run_count > 0 else "—"
                lines.append(f"  {task_id:20s} {acc:12s} {lat:12s} {cost:10s}")

        lines.append("=" * 60)
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# Behavioural stubs (raise NotImplementedError)
# ──────────────────────────────────────────────────────────────


class MetricCollector:
    """Collects and aggregates metrics from benchmark runs.

    Wraps CostTracker for cost metrics and adds accuracy/latency/reliability.
    """

    def __init__(self):
        """Initialize with fresh CostTracker."""
        from ai_vibe_coding.cost_tracker import CostTracker

        self._cost_tracker = CostTracker()
        self._results: list[BenchmarkResult] = []

    def record_result(self, result: BenchmarkResult) -> None:
        """Record a single benchmark result. Updates all metric tracks.

        Args:
            result: A BenchmarkResult instance to record.
        """
        self._results.append(result)
        if result.cost_usd > 0:
            from ai_vibe_coding.llm_wrapper import LLMResponse

            self._cost_tracker.record(
                LLMResponse(
                    content=result.raw_response,
                    provider=result.provider,
                    model=result.model,
                    tokens_used=result.input_tokens + result.output_tokens,
                    cost_usd=result.cost_usd,
                    latency_ms=result.latency_ms,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                )
            )

    def record_results(self, results: list[BenchmarkResult]) -> None:
        """Record multiple results at once.

        Args:
            results: A list of BenchmarkResult instances.
        """
        for r in results:
            self.record_result(r)

    def get_task_metrics(self, task_id: str) -> TaskMetrics:
        """Get aggregated metrics for a specific task.

        Args:
            task_id: The task identifier.

        Returns:
            A TaskMetrics instance with aggregated values.
        """
        task_results = [r for r in self._results if r.task_id == task_id]

        if not task_results:
            return TaskMetrics(task_id=task_id, task_name="")

        # Find task name from first result's metadata
        task_name = ""
        for r in task_results:
            if r.metadata and "task_name" in r.metadata:
                task_name = r.metadata["task_name"]
                break

        scores = [
            r.accuracy_score if r.accuracy_score is not None else 0.0
            for r in task_results
        ]
        latencies = [r.latency_ms for r in task_results]
        costs = [r.cost_usd for r in task_results]
        errors = [1 for r in task_results if r.error is not None]

        accuracy_mean = sum(scores) / len(scores) if scores else 0.0
        accuracy_std = (
            (sum((s - accuracy_mean) ** 2 for s in scores) / len(scores)) ** 0.5
            if len(scores) > 1
            else 0.0
        )
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        avg_cost = sum(costs) / len(costs) if costs else 0.0
        error_rate = sum(errors) / len(task_results) if task_results else 0.0

        # Find best provider/model by accuracy
        provider_scores: dict[str, list[float]] = {}
        model_scores: dict[str, list[float]] = {}
        for r in task_results:
            s = r.accuracy_score if r.accuracy_score is not None else 0.0
            provider_scores.setdefault(r.provider, []).append(s)
            model_scores.setdefault(r.model, []).append(s)

        best_provider = max(
            provider_scores,
            key=lambda p: (
                sum(provider_scores[p]) / len(provider_scores[p])
            ),
        ) if provider_scores else None
        best_model = max(
            model_scores, key=lambda m: sum(model_scores[m]) / len(model_scores[m])
        ) if model_scores else None

        provider_rankings = sorted(
            [
                {
                    "provider": p,
                    "avg_accuracy": sum(s) / len(s),
                    "count": len(s),
                }
                for p, s in provider_scores.items()
            ],
            key=lambda x: x["avg_accuracy"],
            reverse=True,
        )

        return TaskMetrics(
            task_id=task_id,
            task_name=task_name,
            best_provider=best_provider,
            best_model=best_model,
            provider_rankings=provider_rankings,
            accuracy_mean=accuracy_mean,
            accuracy_std=accuracy_std,
            avg_latency_ms=avg_latency,
            avg_cost_usd=avg_cost,
            error_rate=error_rate,
            run_count=len(task_results),
        )

    def get_report(self, title: str = "Benchmark Report") -> BenchmarkReport:
        """Generate full report from all recorded results.

        Args:
            title: Optional report title. Defaults to "Benchmark Report".

        Returns:
            A BenchmarkReport with aggregated metrics.
        """
        from datetime import datetime

        tasks: dict[str, TaskMetrics] = {}
        total_cost = 0.0
        provider_summary: dict[str, dict] = {}
        model_summary: dict[str, dict] = {}

        # Collect unique task IDs
        task_ids = {r.task_id for r in self._results}
        for task_id in sorted(task_ids):
            tm = self.get_task_metrics(task_id)
            tasks[task_id] = tm

        # Build provider summary
        for r in self._results:
            total_cost += r.cost_usd
            if r.provider not in provider_summary:
                provider_summary[r.provider] = {
                    "total_cost": 0.0,
                    "total_runs": 0,
                    "avg_latency_ms": 0.0,
                    "latencies": [],
                }
            provider_summary[r.provider]["total_cost"] += r.cost_usd
            provider_summary[r.provider]["total_runs"] += 1
            provider_summary[r.provider]["latencies"].append(r.latency_ms)

            if r.model not in model_summary:
                model_summary[r.model] = {
                    "total_cost": 0.0,
                    "total_runs": 0,
                    "avg_latency_ms": 0.0,
                    "latencies": [],
                }
            model_summary[r.model]["total_cost"] += r.cost_usd
            model_summary[r.model]["total_runs"] += 1
            model_summary[r.model]["latencies"].append(r.latency_ms)

        # Compute averages for summaries
        for p in provider_summary.values():
            latencies = p.pop("latencies", [])
            p["avg_latency_ms"] = sum(latencies) / len(latencies) if latencies else 0.0

        for m in model_summary.values():
            latencies = m.pop("latencies", [])
            m["avg_latency_ms"] = sum(latencies) / len(latencies) if latencies else 0.0

        report = BenchmarkReport(
            title=title,
            timestamp=datetime.now(UTC).isoformat(),
            tasks=tasks,
            provider_summary=provider_summary,
            model_summary=model_summary,
            total_cost=round(total_cost, 6),
            total_runs=len(self._results),
        )
        return report

    def get_cost_summary(self) -> CostSummary:
        """Delegate to internal CostTracker.

        Returns:
            A CostSummary from the internal cost tracker.
        """
        return self._cost_tracker.get_summary()

    def reset(self) -> None:
        """Clear all recorded results and cost data."""
        self._results.clear()
        self._cost_tracker.reset()


# ──────────────────────────────────────────────────────────────
# Evaluator functions (stubs — NotImplementedError)
# ──────────────────────────────────────────────────────────────


def exact_match(response: str, expected: str) -> float:
    """Return 1.0 if response == expected (after normalization), else 0.0.

    Normalization strips leading/trailing whitespace and lowercases.

    Args:
        response: The model's response string.
        expected: The expected ground truth string.

    Returns:
        1.0 if normalized strings match, 0.0 otherwise.
    """
    return 1.0 if response.strip().lower() == expected.strip().lower() else 0.0


def fuzzy_match(response: str, expected: str) -> float:
    """Return similarity score 0.0-1.0 based on normalized token overlap.

    Tokenizes both strings by whitespace and lowercases them.
    Returns the Jaccard similarity of the token sets.

    Args:
        response: The model's response string.
        expected: The expected ground truth string.

    Returns:
        A float between 0.0 and 1.0 representing token overlap.
    """
    response_tokens = set(response.lower().split())
    expected_tokens = set(expected.lower().split())

    if not expected_tokens and not response_tokens:
        return 1.0
    if not expected_tokens or not response_tokens:
        return 0.0

    intersection = response_tokens & expected_tokens
    union = response_tokens | expected_tokens
    return len(intersection) / len(union)


def contains(response: str, expected: str) -> float:
    """Return 1.0 if expected is a substring of response, else 0.0.

    Performs case-insensitive substring matching.

    Args:
        response: The model's response string.
        expected: The expected substring to search for.

    Returns:
        1.0 if expected is found in response, 0.0 otherwise.
    """
    return 1.0 if expected.lower() in response.lower() else 0.0


def evaluate(response: str, expected: str, evaluator: str) -> float:
    """Dispatch to evaluator by name. Raise ValueError for unknown evaluator.

    Supported evaluators: "exact_match", "fuzzy_match", "contains".

    Args:
        response: The model's response string.
        expected: The expected ground truth string.
        evaluator: The evaluator type name.

    Returns:
        The score from the selected evaluator.

    Raises:
        ValueError: If the evaluator type is not recognized.
    """
    evaluators = {
        "exact_match": exact_match,
        "fuzzy_match": fuzzy_match,
        "contains": contains,
    }

    if evaluator not in evaluators:
        supported = ", ".join(sorted(evaluators.keys()))
        raise ValueError(
            f"Unknown evaluator: '{evaluator}'. Supported evaluators: {supported}"
        )

    return evaluators[evaluator](response, expected)
