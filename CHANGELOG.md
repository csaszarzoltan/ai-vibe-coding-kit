# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
