# Benchmark Suite Guide

Compare all 9 providers on coding tasks, collect accuracy/latency/cost metrics,
and generate reports — all from a single CLI.

## Quick Start

```bash
# Run a single task across two providers
ai-vibe-bench run --providers openai,gpt-4 --providers deepseek,deepseek-v3 \
    --task-file benchmarks/default.json --format markdown
```

If no `--task-file` is provided, a single default task (`qa-1`) is used as a
smoke test. See [Defining Benchmark Tasks](#defining-benchmark-tasks) below.

## CLI Reference

### `ai-vibe-bench run`

Run benchmark tasks across selected provider/model combinations.

```
usage: ai-vibe-bench run [-h] --providers PROVIDER,MODEL [--tasks TASK_ID]
                         [--runs N] [--temperature T] [--output FILE]
                         [--format {json,markdown,table}]
                         [--task-file PATH]

Required:
  --providers PROVIDER,MODEL   Repeatable. E.g. openai,gpt-4

Options:
  --tasks TASK_ID              Repeatable. Task IDs to run (all tasks if omitted)
  --runs N                     How many times to repeat each combo (default: 1)
  --temperature T              Sampling temperature (default: 0.0)
  --task-file PATH             Path to a JSON task definition file
  --output FILE                Write output to file
  --format {json,markdown,table}
                               Output format (default: json)
```

**Examples:**

```bash
# Compare gpt-4 vs deepseek-v3 on all tasks from a file, 3 runs each
ai-vibe-bench run \
    --providers openai,gpt-4 \
    --providers deepseek,deepseek-v3 \
    --task-file benchmarks/coding-tasks.json \
    --runs 3 \
    --format markdown --output report.md

# Single task, JSON output to stdout
ai-vibe-bench run \
    --providers anthropic,claude-4-sonnet \
    --providers gemini,gemini-2.5-pro \
    --tasks gsm8k-q1 \
    --format json

# Accuracy comparison across all 9 providers (with api keys set)
ai-vibe-bench run \
    --providers openai,gpt-4 \
    --providers anthropic,claude-4-sonnet \
    --providers deepseek,deepseek-v3 \
    --providers openrouter,openai/gpt-4 \
    --providers mimo,mimo-v2.5 \
    --providers gemini,gemini-2.5-flash \
    --providers mistral,mistral-large-latest \
    --providers cohere,command-a-plus-05-2026 \
    --providers ollama,gemma3 \
    --task-file benchmarks/coding-tasks.json \
    --runs 3 \
    --format markdown
```

### `ai-vibe-bench list-tasks`

List tasks defined in a JSON task file.

```
ai-vibe-bench list-tasks --task-file benchmarks/default.json
```

### `ai-vibe-bench list-providers`

List providers that can be used based on currently set environment variables.

```
ai-vibe-bench list-providers
```

Output example:
```
Available Providers:
----------------------------------------
  openai     (requires OPENAI_API_KEY)
  anthropic  (requires ANTHROPIC_API_KEY)
  deepseek   (requires DEEPSEEK_API_KEY)
  openrouter (requires OPENROUTER_API_KEY)
  mimo       (requires MIMO_API_KEY)
  gemini     (requires GEMINI_API_KEY)
  mistral    (requires MISTRAL_API_KEY)
  cohere     (requires CO_API_KEY)
  ollama     (local, no API key required)
```

## Defining Benchmark Tasks

Tasks are defined as JSON files with a `version` field and a `tasks` array.

### Task File Format

```json
{
  "version": "1.0",
  "tasks": [
    {
      "id": "gsm8k-q1",
      "name": "GSM8K Question 1",
      "prompt": "Solve: Janet has 3 apples. She buys 5 more. How many apples does she have?",
      "expected_answer": "8",
      "evaluator": "contains"
    },
    {
      "id": "code-python-fib",
      "name": "Fibonacci function",
      "prompt": "Write a Python function that returns the nth Fibonacci number.",
      "expected_answer": "def fib",
      "evaluator": "contains"
    }
  ]
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique task identifier (e.g. `"code-python-fib"`) |
| `name` | Yes | Human-readable name |
| `prompt` | Yes | The prompt sent to the LLM |
| `expected_answer` | Yes | Ground-truth answer for evaluation |
| `evaluator` | No | Default: `"exact_match"`. See [Evaluators](#evaluators) |
| `dataset_path` | No | Path to external dataset (JSON/CSV) |
| `metadata` | No | Arbitrary key-value pairs (category, difficulty, tags) |

> **Note:** The field names `prompt` and `expected` (without `_template` / `_answer`
> suffixes) are also accepted for backward compatibility with earlier task file
> versions.

### Evaluators

| Evaluator | Description | Score |
|-----------|-------------|-------|
| `exact_match` | Response equals expected (case-insensitive, stripped) | 0.0 or 1.0 |
| `fuzzy_match` | Token-set Jaccard similarity | 0.0 — 1.0 |
| `contains` | Expected is a substring of response (case-insensitive) | 0.0 or 1.0 |

Evaluators are in `metric_collector.py` and can be extended programmatically.

## Python API

You can also use the benchmark suite directly from Python.

### Basic Usage

```python
from ai_vibe_coding import (
    BenchmarkRunner,
    BenchmarkTask,
    MetricCollector,
)

# Create a runner
runner = BenchmarkRunner()

# Add providers
from ai_vibe_coding import LLMClient

client = LLMClient(provider="openai")
runner.add_provider("openai", client._provider)

# Or rely on auto-creation from env vars (pass no providers)

# Add tasks
runner.add_task(
    BenchmarkTask(
        id="qa-1",
        name="Simple QA",
        prompt_template="What is the capital of France?",
        expected_answer="Paris",
        evaluator="contains",
    )
)

# Run benchmarks
results = runner.run(
    provider_model_pairs=[("openai", "gpt-4")],
    num_runs=3,
    temperature=0.0,
)

# Collect metrics
collector = MetricCollector()
collector.record_results(results)
report = collector.get_report(title="My Benchmark")
print(report.to_markdown())
```

### Loading Tasks from File

```python
runner = BenchmarkRunner()
tasks = runner.add_tasks_from_file("benchmarks/coding-tasks.json")
for t in tasks:
    print(f"{t.id}: {t.name}")
```

### Generating Reports

```python
# Markdown report
print(report.to_markdown())                          # stdout
report.to_markdown("benchmark-report.md")            # to file

# ASCII table (console-friendly)
print(report.to_ascii_table())

# JSON export
import json
print(json.dumps(report.to_dict(), indent=2))

# Comparison across providers
from ai_vibe_coding import BenchmarkComparison

comparison = runner.compare(results)
print(comparison.to_markdown())
```

### Cost Tracking

The `MetricCollector` wraps `CostTracker` internally:

```python
# After recording results
cost_summary = collector.get_cost_summary()
print(cost_summary.to_table())      # per-provider breakdown
print(cost_summary.to_dict())       # JSON-compatible
```

## Report Formats

### Markdown

The markdown report includes an overall summary table and per-task metrics:

```markdown
# My Benchmark
_Generated: 2026-07-23T12:00:00+00:00_

## Overall Summary

| Metric | Value |
|--------|-------|
| Total Runs | 6 |
| Total Cost | $0.0240 |

## Task Metrics

| Task ID | Name | Accuracy (mean±std) | Avg Latency (ms) | Avg Cost ($) | Error Rate | Best Provider |
|---------|------|---------------------|------------------|-------------|------------|---------------|
| gsm8k-q1 | GSM8K Question 1 | 0.67±0.47 | 1234.5 | 0.0040 | 0.00% | openai |
```

### ASCII Table

Compact console output:

```
============================================================
  My Benchmark
============================================================
  Total Runs: 6
  Total Cost: $0.0240
------------------------------------------------------------
  Tasks:
  Task ID              Accuracy    Latency      Cost
  -------------------- ------------ ------------ ----------
  gsm8k-q1             0.67         1234.5ms     $0.0040
============================================================
```

## Provider Selection Guidance

Use benchmark results to pick the best provider for your use case:

| If you need... | Look for... |
|----------------|-------------|
| Highest accuracy | Provider with highest `accuracy_mean` across your tasks |
| Lowest latency | Provider with lowest `avg_latency_ms` |
| Lowest cost | Provider with lowest `avg_cost_usd` |
| Best reliability | Provider with lowest `error_rate` |
| Best overall value | Compare accuracy/cost ratio across providers |

The `provider_rankings` field in `TaskMetrics` sorts providers by accuracy
within each task. The `provider_summary` in `BenchmarkReport` aggregates
cost, runs, and latency per provider across all tasks.

## All Module Reference

| Module | Classes / Functions |
|--------|---------------------|
| `benchmark_runner.py` | `BenchmarkTask`, `BenchmarkResult`, `BenchmarkComparison`, `BenchmarkRunner` |
| `metric_collector.py` | `TaskMetrics`, `BenchmarkReport`, `MetricCollector`, `exact_match()`, `fuzzy_match()`, `contains()`, `evaluate()` |
| `cli.py` | `main()` — `ai-vibe-bench` entry point |

All three modules are exported from `ai_vibe_coding` and available as:
```python
from ai_vibe_coding import (
    BenchmarkRunner, BenchmarkTask, BenchmarkResult,
    BenchmarkComparison, MetricCollector, BenchmarkReport,
    TaskMetrics, evaluate, exact_match, fuzzy_match, contains,
)
```

## See Also

- [Quick Start Guide](quickstart.md)
- [Model Comparison & Pricing](model-comparison.md)
- [README — Benchmark Suite section](../README.md#benchmark-suite)
