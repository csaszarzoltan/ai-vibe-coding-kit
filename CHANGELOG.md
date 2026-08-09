# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.14.0] - 2026-08-08

### Added

- **Memory Compaction & Knowledge Distillation** — agent memory no longer
  grows unbounded: stale low-importance clusters are distilled into summaries,
  near-duplicates are merged, and importance decays over time.
  - New engine module `src/ai_vibe_coding/memory_compaction.py` — six
    deterministic, dependency-free pure functions (`summarize`,
    `select_clusters`, `select_merges`, `compute_decay`, `build_decay_plan`,
    `build_plan`) with locked defaults: `compaction_age_days=30`,
    `compaction_importance_threshold=0.3`, `merge_threshold=0.82` (cosine),
    `decay_days=7`, `decay_halflife=2.0` periods, `min_importance=0.1`.
  - `MemoryStore.compact(dry_run=True | False)` — dry-run returns a plan
    (clusters, merges, candidate ids) without mutating; apply distills each
    stale low-importance cluster into one `distilled` entry (deterministic
    template summary with provenance header + `metadata.source_ids`),
    archives the originals (never deleted), merges near-duplicate memories
    (newest kept, older archived, `metadata.merged_from`), and writes a
    `compaction_log` row keyed on `run_id`. Idempotent: re-runs skip
    already-archived rows (`skipped` count), no double-archiving.
  - `MemoryStore.impact_decay(dry_run=...)` — half-life importance decay
    (`new = max(min_importance, importance * 0.5 ** (periods / halflife))`),
    each applied decay recorded in `decay_log` (`memory_id, happened_at,
    old_score, new_score`); decayed rows become compaction-eligible.
  - `MemoryStore.memory_stats()` — extends `stats()` with
    `distilled_count`, `archived_count`, `merged_count`, `decayed_count`,
    `last_compaction`, `compact_runs`, `decay_events`.
  - CLI: new `ai-vibe-bench memory` subcommand (`compact`, `decay`,
    `stats`) — dry-run by default, `--apply` to mutate; `--age-days`,
    `--importance-threshold`, `--merge-threshold`, `--decay-days`, `--db`
    overrides.
  - MCP: `memory_compact` tool on `examples/mcp_memory_server.py`
    (`mode="dry-run" | "apply"` + the three threshold overrides); the
    server now exposes six tools.
  - `StorageBackend` ABC gained 9 compaction methods; `RedisBackend`
    declares them but they are `NotImplementedError` stubs — compaction on
    the Redis backend is not yet implemented (SQLite only for now).

### Tests

- 58 tests in `tests/test_memory_compaction.py` — interface tests (defaults,
  signatures, response shapes) + behavioral tests: distill/archive
  (US-001), merge (US-002), decay + decay_log (US-003), idempotent re-run
  (US-004), compaction log, extended stats, archived excluded from search.
- Full suite: 1210 passed, 0 failed, 0 skipped (34 modules; tester gate
  t_9f97f39b). Ruff clean on `src/`.

### Docs

- README.md: "Memory Compaction & Knowledge Distillation" feature section +
  "Memory Compaction (quick start)" snippet + examples list entry.
- `docs/memory-guide.md`: new "Memory Compaction & Knowledge Distillation"
  guide (mechanics, locked defaults table, CLI + MCP + programmatic API,
  backend status), MCP tool table now lists six tools.
- `examples/compaction_client_example.py`: runnable walkthrough (dry-run →
  apply → idempotent re-run → decay → stats) with a deterministic clock.
- `FEATURES-DONE.md`: machine-readable entry for the compaction feature.

## [0.13.0] - 2026-08-06

### Added

- **Pluggable Storage Backend / Redis Backend** (`src/ai_vibe_coding/memory_store.py`):
  - `StorageBackend` ABC with two implementations: `SQLiteBackend` (default) and `RedisBackend`
  - `RedisBackend` stores memories in Redis hashes (`aivck:memory:{id}`) with a recency sorted set and metadata hash
  - Install the Redis extra: `pip install aivck[redis]` (requires `redis>=5.0.0`)
  - Configure via env var or CLI: `AI_VIBE_MEMORY_REDIS_URL=redis://localhost:6379/0` or `--redis-url redis://localhost:6379/0`
  - Same API (`store`, `retrieve`, `search`, `forget`, `stats`) — swap backends without changing application code
  - TTL expiry works via Redis native key expiry; importance × recency eviction via sorted-set scan

### Tests

- 8 Redis-specific unit tests + 16 parametrized backend-agnostic tests (SQLite + Redis) in `tests/test_storage_backend_redis.py`
- MCP Redis stdio integration tests in `tests/test_mcp_memory_server.py`
- 1152 tests pass on both backends (junitxml-verified)

### Docs

- README.md: "Pluggable Storage Backend / Redis Backend" section + "Redis Memory Backend" quick-start
- `examples/redis_memory_client_example.py` — Redis memory client cross-process demo
- `FEATURES-DONE.md` — machine-readable feature tracker for the Redis backend

## [0.12.0] - 2026-08-03

### Added

- **MCP Agent Memory Server** — `src/ai_vibe_coding/memory_store.py` + `memory_embedding.py`:
  - 5-tool FastMCP stdio server (`ai-vibe-memory`): `memory_store`, `memory_retrieve`, `memory_search`, `memory_forget`, `memory_stats`
  - Episodic / semantic / procedural memory for agent pipelines; SQLite-backed, survives restarts
  - Real semantic search via `all-MiniLM-L6-v2` cosine similarity with deterministic hash-fallback (offline-safe, no mock)
  - TTL expiry purge + importance × recency eviction (7-day half-life) keeps the store bounded (default 10,000 rows)
  - Cross-session persistence demo in `examples/memory_client_example.py`
  - New dependency: `sentence-transformers>=2.2.0`

### Docs

- **docs/memory-guide.md** — agent memory architecture (episodic vs semantic vs procedural), lifecycle (write → retrieve → forget), vector vs graph store tradeoffs, self-hosted options (Mem0/Letta/Zep/Cognee), MCP memory protocol, run-and-use guide for the memory server
- **templates/** — integration templates for agent orchestration (`memory_agent_orchestration.md`), prompt chaining (`memory_prompt_chaining.md`), and cost-tracked agents (`memory_cost_tracked_agent.md`)

## [0.10.0] - 2026-07-28

### Added
- Rate Limiting & Quota Management: TokenBucket, SlidingWindowCounter, AdaptiveRateLimiter, QuotaManager with cost-aware distribution
- Chaos Engineering: FaultInjector for 6 fault types, ExperimentRunner with prepare→inject→observe→clean lifecycle, ObservabilityHook with stability reporting
- Scheduled Scanning & Monitoring: DriftDetector, PromptRegressionTester, CostAnomalyDetector, SLAChecker, and interval-based Scheduler

## [0.9.0] - 2026-07-28

### Added

- **Agent Orchestration Templates** — `src/ai_vibe_coding/agent_templates.py`:
  - 4 orchestration patterns: `AgentPipeline` (sequential), `AgentFanOut`/`AgentFanIn` (parallel),
    `AgentSupervisor` (hierarchical), `AgentPubSubCoordinator` (pub/sub)
  - Foundation layer: `AgentMessage`, `MessageBus`, `SharedState`
  - Error handling: `AgentCircuitBreaker`, `AgentRetryPolicy`, `AgentFallback` with DLQ support
  - 4 working examples in `examples/` with multi-provider support
- **82 behavioral tests** for agent templates (695 total tests, 0 regressions)

## [0.8.0] - 2026-07-27

### Added

- **LLM Failover & Resilience Patterns** — `src/ai_vibe_coding/resilience.py`:
  - `CircuitBreaker` — state machine (CLOSED/OPEN/HALF_OPEN) with configurable thresholds
  - `RetryPolicy` — exponential backoff with jitter, configurable max retries and retryable statuses
  - `FallbackChain` — multi-provider fallback (primary → secondary → tertiary) with health gating
  - `HealthChecker` — rolling window health scoring (latency, error rate, availability)
  - `TimeoutBudget` — per-provider/operation timeout configuration
  - `ResponseCache` — stale-while-revalidate caching with configurable TTL
  - `Observability` — structured events, counters, and callback hooks for every resilience layer
  - `ResilientLLMClient` — facade wrapping LLMClient with all resilience layers

## [0.7.0] - 2026-07-27

### Added

- **LLM Cost Calculator** — `src/ai_vibe_coding/cost_calculator.py`:
  - `calculate_cost()` — deterministic cost for any provider/model/token count
  - `compare_all()` — ranked cost comparison across all 9 providers
  - `recommend_for_task()` — task-type-aware provider recommendations
  - 100% test coverage on calculation logic
- **Task type profiles** — `src/ai_vibe_coding/cost_profiles.json`:
  - 5 profiles: coding, chat, analysis, translation, general
  - Configurable weights for cost/quality/latency trade-offs
- **Cost CLI** — `ai-vibe-cost` subcommands:
  - `ai-vibe-cost estimate <provider> <model> <input> <output>` — cost query
  - `ai-vibe-cost compare <input> <output> [--providers]` — provider comparison
  - `ai-vibe-cost recommend <task_type> <input> <output> [--providers]` — recommendations
  - `ai-vibe-cost pricing [--provider] [--model]` — pricing data browser

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

## [0.11.0] - 2026-07-30

### Added

- A durable AI engineering control plane covering provider policy, virtual keys, budgets, traces, evaluation gates, AI security scans, and checkpointed agent approvals.
- Six responsive command-center workspaces with keyboard navigation, live status messaging, empty states, recovery guidance, and dark-mode support.
- Versioned `/api/v1` contracts for provider configuration, virtual keys, trace ingestion/export, experiments, security scans, agent runs, and preflight authorization.
- Fail-closed model and budget policies, idempotent trace ingestion, spend deduplication, secret redaction, release threshold enforcement, blocking security findings, and self-approval prevention.
- Deterministic unit, persistence, security, UI-state, accessibility, and route-contract tests.

### Changed

- Bumped the package and application version to 0.11.0.

### [Unreleased] - 2026-08-01

#### Added
- Provider-readiness endpoint for the playground without secret disclosure.
- Optional system-prompt control, device-local preferences, recent comparisons, and result sorting.
- Accessible skip navigation, live/busy result semantics, and alert feedback.
- TDD coverage for new UX, readiness, persistence, and telemetry contracts.
- Product analysis, requirements, and implementation handoff documentation.

#### Changed
- FastAPI root now serves the primary playground and registers the cost API router.

#### Continued UX hardening
- Connected provider readiness metadata to the visible provider selector.
- Disabled providers that require setup while retaining a clear status and refresh action.
- Added HTML and JavaScript package-data declarations so the installed wheel contains the runnable playground.
- Added TDD coverage and wheel-content validation for these behaviors.

#### Actionable provider failure recovery
- Added stable provider error categories and safe recovery guidance.
- Added an accessible per-provider Retry action that preserves successful comparison results.
- Added privacy-minimal retry telemetry containing only the provider slug.
- Added TDD and regression coverage for credential failure categorization and retry UX.

#### Privacy-aware comparison exports
- Added local Markdown and schema-versioned JSON exports for completed comparisons.
- Removed raw/authentication fields from exported provider payloads.
- Added export evidence including prompt, optional system prompt, timestamp, model, cost, tokens, latency, errors, and recovery guidance.
- Fixed copy feedback so it no longer depends on a browser-global event object.

#### Keyboard efficiency and local-history controls
- Added documented keyboard shortcuts for run, prompt focus, help, and help dismissal.
- Added focus-safe shortcut handling that does not hijack normal text-entry keys.
- Added an explicit Clear local history action and privacy-minimal history-cleared event.
- Added accessible shortcut help with focus restoration and responsive presentation.

#### Decision evidence and preferred-result workflow
- Added a preferred-result action to successful provider cards.
- Added a device-local decision note and accessible preferred-provider summary.
- Added preferred-provider highlighting and toggle semantics.
- Included preferred provider and decision rationale in Markdown and JSON exports.
- Added privacy-minimal preferred-result telemetry and TDD coverage.

#### Aggregate comparison evidence
- Added an accessible comparison summary for success, failure, total cost, and total token usage.
- Added explicit Lowest latency and Lowest cost indicators without presenting either as universally best.
- Added clear partial-comparison and all-failed states while preserving usable completed results.
- Added defensive handling for missing or non-numeric metrics and TDD coverage.

#### Run-scoped decisions and complete recent-run restoration
- Reset stale preferred-provider and decision-note state when a genuinely new comparison replaces results.
- Preserved decision evidence during scoped provider retries.
- Saved and restored the optional system prompt with recent local runs.
- Added localized recent-run timestamps, provider counts, and descriptive accessible labels.
- Added defensive handling for invalid historical timestamps and TDD coverage.

#### Prompt-length guardrails and accessible validation
- Added a shared 20,000-character prompt limit to the browser and API contract.
- Added a localized live character counter with remaining capacity.
- Added accessible validation messaging and `aria-invalid` state.
- Prevented invalid oversized prompts from enabling comparison submission.
- Added responsive near-limit feedback and TDD coverage for boundary behavior.
