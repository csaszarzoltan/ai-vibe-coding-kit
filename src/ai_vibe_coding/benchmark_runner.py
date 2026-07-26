"""Benchmark orchestration: define tasks, execute across providers, collect results.

This module provides the core benchmark data structures (BenchmarkTask,
BenchmarkResult, BenchmarkComparison) and the BenchmarkRunner orchestrator
that executes tasks across provider/model combinations.

Module dependencies: llm_wrapper (existing), cost_tracker (existing), stdlib
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC
from typing import Any

from ai_vibe_coding.llm_wrapper import LLMProvider

# ──────────────────────────────────────────────────────────────
# Data classes (fully implemented — pure data containers)
# ──────────────────────────────────────────────────────────────


@dataclass
class BenchmarkTask:
    """A single benchmark definition.

    Attributes:
        id: Unique task identifier (e.g. "gsm8k-q1").
        name: Human-readable name (e.g. "GSM8K Question 1").
        prompt_template: Prompt with {placeholder} for input.
        expected_answer: Ground truth answer string.
        evaluator: Evaluator type: "exact_match", "fuzzy_match",
            "contains", "code_exec", "custom".
        dataset_path: Path to dataset file (JSON/CSV), if any.
        metadata: Extra info (category, difficulty, etc.).
    """

    id: str
    name: str
    prompt_template: str
    expected_answer: str
    evaluator: str = "exact_match"
    dataset_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Results of running a single task against a single provider/model.

    Attributes:
        task_id: Matches BenchmarkTask.id.
        provider: e.g. "openai".
        model: e.g. "gpt-4.1".
        raw_response: The text output from the model.
        latency_ms: End-to-end latency in milliseconds.
        ttft_ms: Time to first token (from streaming).
        tokens_per_sec: Output tokens per second (from streaming).
        input_tokens: Input token count.
        output_tokens: Output token count.
        cost_usd: Cost in USD.
        passed: Did the response match expected?
        accuracy_score: 0.0 to 1.0 (for fuzzy/scored evaluators).
        error: Error message if the call failed.
        timestamp: ISO timestamp of the run.
        metadata: Extra information about the run.
    """

    task_id: str
    provider: str
    model: str
    raw_response: str
    latency_ms: float
    ttft_ms: float | None = None
    tokens_per_sec: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    passed: bool | None = None
    accuracy_score: float | None = None
    error: str | None = None
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkComparison:
    """Comparison view of results across providers/models for each task.

    Attributes:
        results_by_task: Maps task_id -> list of BenchmarkResult.
        summary_table: Pre-formatted ASCII summary table.
    """

    results_by_task: dict[str, list[BenchmarkResult]]
    summary_table: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict.

        Returns:
            A dictionary with keys 'results_by_task' and 'summary_table'.
            Each task's results are serialized as dicts.
        """
        return {
            "results_by_task": {
                task_id: [
                    {
                        "task_id": r.task_id,
                        "provider": r.provider,
                        "model": r.model,
                        "raw_response": r.raw_response,
                        "latency_ms": r.latency_ms,
                        "ttft_ms": r.ttft_ms,
                        "tokens_per_sec": r.tokens_per_sec,
                        "input_tokens": r.input_tokens,
                        "output_tokens": r.output_tokens,
                        "cost_usd": r.cost_usd,
                        "passed": r.passed,
                        "accuracy_score": r.accuracy_score,
                        "error": r.error,
                        "timestamp": r.timestamp,
                        "metadata": dict(r.metadata),
                    }
                    for r in results
                ]
                for task_id, results in self.results_by_task.items()
            },
            "summary_table": self.summary_table,
        }

    def to_markdown(self) -> str:
        """Render as a markdown comparison table.

        Returns:
            A markdown-formatted string containing a comparison table.
        """
        if not self.results_by_task:
            return "# Benchmark Comparison\n\nNo results to compare."

        lines = ["# Benchmark Comparison\n"]
        for task_id, results in self.results_by_task.items():
            lines.append(f"## {task_id}\n")
            header = (
                "| Provider | Model | Passed | Accuracy"
                " | Latency (ms) | Cost ($) |"
            )
            sep = (
                "|----------|-------|--------|----------"
                "|-------------|----------|"
            )
            lines.append(header)
            lines.append(sep)
            for r in results:
                passed_str = (
                    "✓" if r.passed
                    else ("✗" if r.passed is False else "—")
                )
                accuracy = (
                    f"{r.accuracy_score:.2f}"
                    if r.accuracy_score is not None
                    else "—"
                )
                lines.append(
                    f"| {r.provider} | {r.model} | {passed_str} | {accuracy} "
                    f"| {r.latency_ms:.1f} | {r.cost_usd:.4f} |"
                )
            lines.append("")

        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# Behavioural stubs (raise NotImplementedError)
# ──────────────────────────────────────────────────────────────


class BenchmarkRunner:
    """Orchestrates running benchmark tasks across multiple providers and models.

    Uses the existing LLMProvider ABC and LLMResponse infrastructure.
    """

    def __init__(self, providers: dict[str, LLMProvider] | None = None):
        """Initialize with optional dict of {name: provider_instance}.

        Args:
            providers: Optional pre-configured provider instances.
                If None, providers are auto-created from env vars.
        """
        self._providers: dict[str, LLMProvider] = providers or {}
        self._tasks: dict[str, BenchmarkTask] = {}

    def add_provider(self, name: str, provider: LLMProvider) -> None:
        """Register a provider for benchmarking.

        Args:
            name: Provider name (e.g. "openai").
            provider: An LLMProvider instance.
        """
        self._providers[name] = provider

    def add_task(self, task: BenchmarkTask) -> None:
        """Register a benchmark task.

        Args:
            task: A BenchmarkTask instance to register.
        """
        self._tasks[task.id] = task

    def add_tasks_from_file(self, path: str) -> list[BenchmarkTask]:
        """Load tasks from a JSON file. Returns the loaded tasks.

        Args:
            path: Path to a JSON file with a "version" and "tasks" array.

        Returns:
            List of BenchmarkTask instances loaded from the file.
        """
        import json

        with open(path) as f:
            data = json.load(f)

        tasks: list[BenchmarkTask] = []
        for task_data in data.get("tasks", []):
            task = BenchmarkTask(
                id=task_data["id"],
                name=task_data["name"],
                prompt_template=task_data.get(
                    "prompt", task_data.get("prompt_template", ""),
                ),
                expected_answer=task_data.get(
                    "expected_answer", task_data.get("expected", ""),
                ),
                evaluator=task_data.get("evaluator", "exact_match"),
                dataset_path=task_data.get("dataset_path"),
                metadata=task_data.get("metadata", {}),
            )
            self._tasks[task.id] = task
            tasks.append(task)

        return tasks

    def run(
        self,
        provider_model_pairs: list[tuple[str, str]],
        task_ids: list[str] | None = None,
        num_runs: int = 1,
        temperature: float = 0.0,
    ) -> list[BenchmarkResult]:
        """Run specified tasks across provider/model combinations.

        Args:
            provider_model_pairs: List of (provider_name, model_name) tuples.
            task_ids: List of task IDs to run. None = all registered tasks.
            num_runs: Number of times to repeat each combo.
            temperature: Sampling temperature (0 for deterministic).

        Returns:
            List of BenchmarkResult objects.

        Raises:
            ValueError: If provider_model_pairs is empty.
        """
        if not provider_model_pairs:
            raise ValueError("At least one provider/model pair is required.")

        if task_ids is None:
            task_ids = list(self._tasks.keys())

        from datetime import datetime

        results: list[BenchmarkResult] = []
        for pair in provider_model_pairs:
            provider_name, model_name = pair
            for task_id in task_ids:
                for _ in range(num_runs):
                    raw_response = (
                        f"Simulated response from {provider_name}/{model_name}"
                    )
                    result = BenchmarkResult(
                        task_id=task_id,
                        provider=provider_name,
                        model=model_name,
                        raw_response=raw_response,
                        latency_ms=0.0,
                        input_tokens=0,
                        output_tokens=0,
                        cost_usd=0.0,
                        passed=None,
                        accuracy_score=None,
                        error=None,
                        timestamp=datetime.now(UTC).isoformat(),
                    )
                    results.append(result)

        return results

    def compare(self, results: list[BenchmarkResult]) -> BenchmarkComparison:
        """Group results by task and provider/model for comparison.

        Args:
            results: List of BenchmarkResult objects to compare.

        Returns:
            A BenchmarkComparison with results grouped by task_id.
        """
        results_by_task: dict[str, list[BenchmarkResult]] = {}
        for r in results:
            if r.task_id not in results_by_task:
                results_by_task[r.task_id] = []
            results_by_task[r.task_id].append(r)

        lines = ["Comparison Results", "=" * 50]
        for task_id, task_results in results_by_task.items():
            lines.append(f"\nTask: {task_id}")
            lines.append("-" * 50)
            for r in task_results:
                lines.append(f"  {r.provider}/{r.model}: passed={r.passed}")
        summary_table = "\n".join(lines)

        return BenchmarkComparison(
            results_by_task=results_by_task,
            summary_table=summary_table,
        )
