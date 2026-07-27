"""Pre-development tests for benchmark_runner.py (Task P0.1-P0.4).

Interface tests verify the public API exists with correct signatures and
type hints — these must PASS immediately with the stub implementation.

Behavioral tests define the expected behaviour that the developer must
make green by implementing the stubs — these must FAIL with NotImplementedError.

pytest markers:
    @pytest.mark.unit — mocked HTTP, no real API keys needed
"""

from __future__ import annotations

import pytest

from ai_vibe_coding.benchmark_runner import (
    BenchmarkComparison,
    BenchmarkResult,
    BenchmarkRunner,
    BenchmarkTask,
)

# ──────────────────────────────────────────────────────────────
# Interface smoke tests (should PASS — verify API surface exists)
# ──────────────────────────────────────────────────────────────


class TestBenchmarkTaskInterface:
    """Verify BenchmarkTask dataclass exists and has correct fields."""

    def test_benchmark_task_is_dataclass(self):
        """BenchmarkTask should be instantiable with required fields."""
        task = BenchmarkTask(
            id="test-1",
            name="Test Task",
            prompt_template="What is {input}?",
            expected_answer="42",
        )
        assert task.id == "test-1"
        assert task.name == "Test Task"
        assert task.prompt_template == "What is {input}?"
        assert task.expected_answer == "42"

    def test_benchmark_task_defaults(self):
        """Optional fields (evaluator, dataset_path, metadata) should have correct defaults."""
        task = BenchmarkTask(
            id="test-1",
            name="Test Task",
            prompt_template="Hello?",
            expected_answer="World",
        )
        assert task.evaluator == "exact_match"
        assert task.dataset_path is None
        assert task.metadata == {}
        # Type checks
        assert isinstance(task.id, str)
        assert isinstance(task.name, str)
        assert isinstance(task.prompt_template, str)
        assert isinstance(task.expected_answer, str)


class TestBenchmarkResultInterface:
    """Verify BenchmarkResult dataclass exists and has correct fields."""

    def test_benchmark_result_is_dataclass(self):
        """BenchmarkResult should be instantiable with required fields."""
        result = BenchmarkResult(
            task_id="test-1",
            provider="openai",
            model="gpt-4",
            raw_response="Hello",
            latency_ms=150.0,
        )
        assert result.task_id == "test-1"
        assert result.provider == "openai"
        assert result.model == "gpt-4"
        assert result.raw_response == "Hello"
        assert result.latency_ms == 150.0

    def test_benchmark_result_optional_fields(self):
        """Optional fields should default to None/0 correctly."""
        result = BenchmarkResult(
            task_id="t1",
            provider="p",
            model="m",
            raw_response="r",
            latency_ms=0.0,
        )
        assert result.ttft_ms is None
        assert result.tokens_per_sec is None
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.cost_usd == 0.0
        assert result.passed is None
        assert result.accuracy_score is None
        assert result.error is None
        assert result.timestamp == ""
        assert result.metadata == {}


class TestBenchmarkRunnerInterface:
    """Verify BenchmarkRunner class has expected structure."""

    def test_benchmark_runner_init(self):
        """BenchmarkRunner should be instantiable with no args."""
        runner = BenchmarkRunner()
        assert runner is not None
        assert hasattr(runner, "_providers")
        assert runner._providers == {}

    def test_benchmark_runner_init_with_providers(self):
        """BenchmarkRunner should accept optional providers dict."""
        runner = BenchmarkRunner(providers={})
        assert runner is not None

    def test_benchmark_runner_has_methods(self):
        """BenchmarkRunner should have all 5 methods."""
        assert hasattr(BenchmarkRunner, "add_provider")
        assert hasattr(BenchmarkRunner, "add_task")
        assert hasattr(BenchmarkRunner, "add_tasks_from_file")
        assert hasattr(BenchmarkRunner, "run")
        assert hasattr(BenchmarkRunner, "compare")

    def test_benchmark_runner_method_signatures(self):
        """Method signatures should match expected parameter names."""
        import inspect

        sig_add_provider = inspect.signature(BenchmarkRunner.add_provider)
        params = list(sig_add_provider.parameters.keys())
        assert "name" in params
        assert "provider" in params

        sig_add_task = inspect.signature(BenchmarkRunner.add_task)
        assert "task" in list(sig_add_task.parameters.keys())

        sig_run = inspect.signature(BenchmarkRunner.run)
        run_params = list(sig_run.parameters.keys())
        assert "provider_model_pairs" in run_params
        assert "task_ids" in run_params
        assert "num_runs" in run_params
        assert "temperature" in run_params

        sig_compare = inspect.signature(BenchmarkRunner.compare)
        assert "results" in list(sig_compare.parameters.keys())


class TestBenchmarkComparisonInterface:
    """Verify BenchmarkComparison dataclass and methods."""

    def test_benchmark_comparison_is_dataclass(self):
        """BenchmarkComparison should be instantiable."""
        comp = BenchmarkComparison(
            results_by_task={},
            summary_table="",
        )
        assert comp.results_by_task == {}
        assert comp.summary_table == ""

    def test_benchmark_comparison_has_methods(self):
        """BenchmarkComparison should have to_dict() and to_markdown()."""
        assert hasattr(BenchmarkComparison, "to_dict")
        assert hasattr(BenchmarkComparison, "to_markdown")


# ──────────────────────────────────────────────────────────────
# Behavioral pre-state tests (should FAIL — NotImplementedError)
# These define the contract the developer must satisfy.
# ──────────────────────────────────────────────────────────────


class TestBenchmarkRunnerAddProvider:
    """Behavioral tests for add_provider() — fail until implemented."""

    @pytest.mark.unit
    def test_add_provider_stores_provider(self):
        """add_provider() should store the provider instance."""
        from ai_vibe_coding.llm_wrapper import OpenAIProvider

        runner = BenchmarkRunner()
        provider = OpenAIProvider(api_key="fake-key")
        runner.add_provider("my_openai", provider)

    @pytest.mark.unit
    def test_add_provider_overwrites_existing(self):
        """add_provider() should allow replacing an existing provider."""
        from ai_vibe_coding.llm_wrapper import AnthropicProvider, OpenAIProvider

        runner = BenchmarkRunner()
        runner.add_provider("provider_a", OpenAIProvider(api_key="fake"))
        runner.add_provider("provider_a", AnthropicProvider(api_key="fake"))


class TestBenchmarkRunnerAddTask:
    """Behavioral tests for add_task() — fail until implemented."""

    @pytest.mark.unit
    def test_add_task_stores_task(self):
        """add_task() should store the benchmark task."""
        runner = BenchmarkRunner()
        task = BenchmarkTask(
            id="qa-1", name="Test", prompt_template="Q?", expected_answer="A",
        )
        runner.add_task(task)


class TestBenchmarkRunnerRun:
    """Behavioral tests for run() — fail until implemented."""

    @pytest.mark.unit
    def test_benchmark_runner_run_returns_list(self):
        """run() should return a list of BenchmarkResult objects."""
        runner = BenchmarkRunner()
        results = runner.run(
            provider_model_pairs=[("openai", "gpt-4")],
            task_ids=["qa-1"],
        )
        assert isinstance(results, list)
        if len(results) > 0:
            assert isinstance(results[0], BenchmarkResult)

    @pytest.mark.unit
    def test_benchmark_runner_run_with_empty_providers(self):
        """run() with empty provider list should raise ValueError."""
        runner = BenchmarkRunner()
        with pytest.raises(ValueError):
            runner.run(
                provider_model_pairs=[],
                task_ids=["qa-1"],
            )

    @pytest.mark.unit
    def test_benchmark_runner_run_honours_num_runs(self):
        """run() should repeat each combo num_runs times."""
        runner = BenchmarkRunner()
        results = runner.run(
            provider_model_pairs=[("openai", "gpt-4")],
            task_ids=["qa-1"],
            num_runs=3,
        )
        assert len(results) == 3

    @pytest.mark.unit
    def test_benchmark_runner_compare_returns_comparison(self):
        """compare() should accept results and return BenchmarkComparison."""
        runner = BenchmarkRunner()
        results = [
            BenchmarkResult(
                task_id="qa-1", provider="openai", model="gpt-4",
                raw_response="42", latency_ms=100.0,
            ),
        ]
        comp = runner.compare(results)
        assert isinstance(comp, BenchmarkComparison)


class TestBenchmarkRunnerAddTasksFromFile:
    """Behavioral tests for add_tasks_from_file() — fail until implemented."""

    @pytest.mark.unit
    def test_benchmark_runner_add_tasks_from_file(self, tmp_path):
        """add_tasks_from_file() should load tasks from a JSON file."""
        import json

        task_file = tmp_path / "tasks.json"
        task_data = {
            "version": "1.0",
            "tasks": [
                {
                    "id": "qa-1",
                    "name": "Test Q",
                    "prompt": "Q?",
                    "expected": "A",
                    "evaluator": "exact_match",
                },
            ],
        }
        task_file.write_text(json.dumps(task_data))

        runner = BenchmarkRunner()
        tasks = runner.add_tasks_from_file(str(task_file))
        assert isinstance(tasks, list)
        assert len(tasks) > 0
        assert all(isinstance(t, BenchmarkTask) for t in tasks)


class TestBenchmarkComparisonBehavior:
    """Behavioral tests for BenchmarkComparison — fail until implemented."""

    @pytest.mark.unit
    def test_benchmark_comparison_to_dict_serializable(self):
        """to_dict() should return a JSON-serializable dict."""
        import json

        comp = BenchmarkComparison(
            results_by_task={
                "qa-1": [
                    BenchmarkResult(
                        task_id="qa-1", provider="openai", model="gpt-4",
                        raw_response="42", latency_ms=100.0,
                    ),
                ],
            },
            summary_table="",
        )
        d = comp.to_dict()
        assert isinstance(d, dict)
        # Must be JSON-serializable
        json.dumps(d)

    @pytest.mark.unit
    def test_benchmark_comparison_to_markdown_returns_string(self):
        """to_markdown() should return a non-empty string."""
        comp = BenchmarkComparison(
            results_by_task={},
            summary_table="",
        )
        md = comp.to_markdown()
        assert isinstance(md, str)
        assert len(md) > 0
