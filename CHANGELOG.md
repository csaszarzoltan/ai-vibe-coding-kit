# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.1] - 2026-07-24

### Added

- **MCP Getting Started guide** — "MCP in 5 Minutes" section in README with
  step-by-step instructions for Cursor and Claude Desktop configuration
- **docs/mcp-guide.md** — full reference covering all 6 tools, security model,
  programmatic API, troubleshooting, and verification checklist

## [0.6.0] - 2026-07-23

### Added

- **Benchmark suite** (`src/ai_vibe_coding/benchmark_runner.py`, `metric_collector.py`, `cli.py`):
  - `BenchmarkTask` — define tasks with prompts, expected answers, and evaluator type
  - `BenchmarkRunner` — orchestrate tasks across provider/model combos with configurable runs
  - `BenchmarkResult` / `BenchmarkComparison` — per-run and comparative result data classes
  - `MetricCollector` — aggregate accuracy, latency, cost, and error-rate metrics
  - `BenchmarkReport` — full-report generation in JSON, Markdown, or ASCII table
  - Evaluator functions: `exact_match`, `fuzzy_match`, `contains`
  - `ai-vibe-bench` CLI — `run`, `list-tasks`, `list-providers` subcommands
- **62 behavioral tests** for the benchmark suite (378 total tests, zero regressions)
- **Benchmark Suite section** in README with quick-start examples
- **docs/benchmark-guide.md** — full reference with task file format, report examples, provider selection guidance

## [0.5.0] - 2026-07-23

### Added

- **CI/CD integration** — three GitHub Actions workflow templates in `.github/workflows/`:
  - `test.yml` — automated lint + pytest on push/PR (Python 3.11, 3.12). Runs by default
  - `llm-integration-test.yml` — optional LLM provider integration testing with live API keys
  - `deploy.yml` — optional Railway/Docker deployment template
- **CI badge** in README showing workflow status
- **CI/CD section** in README with activation instructions, copy-paste code examples, and status notes
- **Contributing checklist** updated to reference CI workflows

## [0.4.0] - 2026-07-26

### Added

- **Prompt chaining templates** (`src/ai_vibe_coding/chain_templates.py`):
  - SequentialChain — ordered A→B→C pipeline with state passing
  - ConditionalChain — gate routing with true/false branches
  - ParallelChain — fan-out/fan-in with ThreadPoolExecutor
  - MapReduceChain — split/map/reduce for large input processing
  - AgentWithToolsChain — ReAct-style tool-calling loop
  - HITLStep — human-in-the-loop approval gates
  - ChainRunner — universal chain execution with streaming
- **Test suite**: 50+ new tests for all chain templates
- **Documentation**: docs/prompt-chaining.md with pattern reference

### Fixed

- Fixed __init__.py broken imports for missing modules

## [0.3.0] - 2026-07-19

### Added

- **Multi-provider LLM wrapper** (`src/ai_vibe_coding/llm_wrapper.py`):
  - `LLMProvider` ABC with `chat()`, `stream()`, `get_cost()`, `get_model_list()`
  - 5 concrete providers: OpenAI, Anthropic, DeepSeek, OpenRouter, MiMo
  - `LLMClient` facade with provider selection, `chat_async()`, `compare_providers()`
  - Direct provider calls with explicit error surfacing
  - Streaming via generator yielding text chunks
  - Configurable `PRICING` dict with 2026 per-model rates
- **Structured output and tool calling** (`src/ai_vibe_coding/structured.py`):
  - `chat_json()` — forces JSON output across all providers
  - `chat_with_tools()` — function calling abstraction
  - `ToolDef` and `ToolCallResult` dataclasses
  - `LLMJSONError` and `ToolNotFoundError` exceptions
- **Cost tracking and analytics** (`src/ai_vibe_coding/cost_tracker.py`):
  - `CostTracker` with thread-safe `record()`, `get_summary()`, `export_csv()`, `export_json()`
  - `CostSummary` dataclass with `to_dict()` and `to_table()` (ASCII table)
- **Package structure**: `pyproject.toml` with setuptools, ruff, pytest config
- **Test suite**: 51 tests covering all modules (interface smoke + behavioral)

### Changed

- Version bumped from 0.2.0 to 0.3.0
- Added `.gitignore` for Python build artifacts
