# API Reference

## `ai_vibe_coding` — Package exports

```python
from ai_vibe_coding import LLMClient, LLMProvider, LLMResponse
```

---

## `LLMResponse` (dataclass)

Standardized response from any LLM provider.

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | Text content of the response |
| `provider` | `str` | Provider name (e.g. `"openai"`) |
| `model` | `str` | Model name (e.g. `"gpt-4"`) |
| `tokens_used` | `int` | Total tokens (input + output) |
| `cost_usd` | `float` | Estimated cost in USD |
| `latency_ms` | `float` | Response latency in milliseconds |
| `input_tokens` | `int` | Input/prompt tokens (default 0) |
| `output_tokens` | `int` | Output/completion tokens (default 0) |
| `raw` | `dict[str, Any]` | Raw provider response for debugging |

---

## `LLMProvider` (ABC)

Abstract base class for all providers.

### Methods

#### `chat(messages, *, model=None, **kwargs) -> LLMResponse`

Send a chat completion request.

- **messages**: `list[dict[str, str]]` — message dicts with `"role"` and `"content"`
- **model**: `str | None` — optional model override
- **kwargs**: provider-specific parameters (temperature, max_tokens, etc.)
- **Returns**: `LLMResponse`

#### `stream(messages, *, model=None, **kwargs) -> Iterator[str]`

Stream a chat completion, yielding text chunks.

- **Yields**: text chunks as they arrive from the provider

#### `get_cost(input_tokens, output_tokens) -> float`

Calculate cost for token usage based on the `PRICING` dict.

#### `get_model_list() -> list[str]`

Return list of available models for this provider.

---

## Concrete Providers

All providers implement `LLMProvider`.

### `OpenAIProvider`
- **Models:** gpt-4, gpt-4-turbo, gpt-4.5, gpt-5
- **SDK:** `openai` (official)
- **Env var:** `OPENAI_API_KEY`

```python
from ai_vibe_coding.llm_wrapper import OpenAIProvider

provider = OpenAIProvider(model="gpt-4-turbo")
response = provider.chat([{"role": "user", "content": "Hello"}])
```

### `AnthropicProvider`
- **Models:** claude-3-5-sonnet, claude-4-sonnet, claude-4.5-sonnet
- **SDK:** `anthropic` (official)
- **Env var:** `ANTHROPIC_API_KEY`
- **Note:** System messages are extracted and passed via the `system` parameter

### `DeepSeekProvider`
- **Models:** deepseek-v3, deepseek-r1
- **SDK:** `openai` (DeepSeek is OpenAI-compatible)
- **Env var:** `DEEPSEEK_API_KEY`
- **Base URL:** `https://api.deepseek.com/v1`

### `OpenRouterProvider`
- **Models:** 100+ models via OpenRouter routing (e.g. `"openai/gpt-4"`)
- **SDK:** `httpx` (direct HTTP)
- **Env var:** `OPENROUTER_API_KEY`
- **Base URL:** `https://openrouter.ai/api/v1`

### `MiMoProvider`
- **Models:** mimo-v2.5
- **SDK:** `httpx` (direct HTTP)
- **Env var:** `MIMO_API_KEY`
- **Base URL:** `https://api.xiaomimimo.com/v1`

---

## `LLMClient` (facade)

Unified interface for provider selection, async calls, and comparison.

### Constructor

```python
LLMClient(provider="openai", **kwargs)
```

- **provider**: one of `"openai"`, `"anthropic"`, `"deepseek"`, `"openrouter"`, `"mimo"`
- **kwargs**: passed to the provider constructor (api_key, model, etc.)

### Methods

#### `chat(prompt, system_prompt=None, *, model=None, **kwargs) -> LLMResponse`

Simple chat interface that builds the messages list internally.

#### `chat_async(prompt, system_prompt=None, *, model=None) -> LLMResponse`

Async version of `chat()`. Uses `asyncio` for non-blocking calls.

#### `stream(prompt, system_prompt=None, *, model=None, **kwargs) -> Iterator[str]`

Streaming chat that yields text chunks.

#### `compare_providers(prompt) -> dict[str, LLMResponse | str]`

Run the same prompt across all configured providers. Returns a dict keyed by provider name. Failed providers have error strings instead of `LLMResponse` objects.

---

## `PRICING` dict

Per-provider, per-model pricing (per 1K tokens). Update this when providers change rates.

```python
from ai_vibe_coding.llm_wrapper import PRICING

# Structure: PRICING[provider][model] = {"input": float, "output": float}
PRICING["openai"]["gpt-4"]  # {"input": 0.03, "output": 0.06}
```

---

## `structured` module

```python
from ai_vibe_coding.structured import (
    chat_json, chat_with_tools,
    ToolDef, ToolCallResult,
    LLMJSONError, ToolNotFoundError,
)
```

### `chat_json(client, prompt, *, system_prompt=None, schema=None, model=None) -> dict`

Force JSON output from any provider. Strips markdown code fences if present. Raises `LLMJSONError` if the response is not valid JSON.

### `chat_with_tools(client, prompt, tools, *, system_prompt=None, model=None) -> ToolCallResult`

Send a prompt with tool definitions. The LLM responds with a JSON object containing `name` and `arguments`. Raises `ToolNotFoundError` if the LLM requests an unknown tool.

### `ToolDef` (dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Tool name |
| `description` | `str` | Human-readable description |
| `parameters` | `dict` | JSON Schema dict |

### `ToolCallResult` (dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `tool_name` | `str` | Name of the requested tool |
| `arguments` | `dict` | Parsed JSON arguments |
| `raw_response` | `LLMResponse` | The raw LLM response |

### Exceptions

- `LLMJSONError(message, raw_response="")` — invalid JSON from provider
- `ToolNotFoundError` — unknown tool name requested by LLM

---

## `cost_tracker` module

```python
from ai_vibe_coding.cost_tracker import CostTracker, CostSummary
```

### `CostTracker`

Thread-safe cost tracker for LLM API calls.

#### Methods

| Method | Description |
|--------|-------------|
| `record(response: LLMResponse)` | Record an LLMResponse and accumulate cost |
| `get_summary() -> CostSummary` | Return aggregated summary |
| `export_csv(path)` | Export records to CSV file |
| `export_json(path)` | Export summary + records to JSON |
| `reset()` | Clear all recorded costs |

### `CostSummary` (dataclass)

| Field | Type | Description |
|-------|------|-------------|
| `total_cost` | `float` | Total cost in USD |
| `total_tokens` | `int` | Total tokens consumed |
| `per_provider` | `dict[str, float]` | Cost by provider |
| `per_model` | `dict[str, float]` | Cost by model |
| `call_count` | `int` | Number of calls recorded |

#### Methods

- `to_dict() -> dict` — JSON-serializable representation
- `to_table() -> str` — aligned ASCII table string

## Control-plane API (v1)

The additive control-plane interface exposes provider configuration, one-time virtual-key issuance, preflight authorization, trace ingestion/export, evaluation experiments, security scans, and agent runs under `/api/v1`. See [AI Engineering Control Plane](control-plane.md) for states, trust boundaries, recovery, and compatibility.

---

## `cost_store` module

```python
from ai_vibe_coding.cost_store import SqliteCostStore, CostPricingTable
```

### `SqliteCostStore`

SQLite-backed persistence for LLM cost records with time-windowed queries, daily rollups, and latency percentiles.

#### Constructor

```python
SqliteCostStore(db_path: str | Path)
```

- `db_path` — Path to SQLite database file, or `":memory:"` for in-memory storage.

For `:memory:` databases, keeps a single persistent connection so all queries within the same instance see the same data.

#### Methods

| Method | Description |
|--------|-------------|
| `record_request(provider, model, input_tokens, output_tokens, cost_usd, latency_ms, session_id=None, tags=None) -> int` | Insert a cost record. Returns row id. |
| `get_daily_rollup(start_date=None, end_date=None) -> list[dict]` | Daily aggregated cost/token data with avg latency |
| `get_total_cost(start_date=None, end_date=None, provider=None) -> float` | Sum of costs matching filters |
| `get_latency_percentiles(percentile=95.0, start_date=None, end_date=None, provider=None) -> float` | Latency at the given percentile |
| `get_cost_by_model(start_date=None, end_date=None) -> list[dict]` | Cost breakdown by model |
| `get_cost_by_provider(start_date=None, end_date=None) -> list[dict]` | Cost breakdown by provider |
| `get_cost_by_user(start_date=None, end_date=None) -> list[dict]` | Cost breakdown by session/user |
| `run_daily_rollup() -> dict` | Aggregate today's cost_log into daily_rollup table |

### `CostPricingTable`

In-memory per-model pricing management.

| Method | Description |
|--------|-------------|
| `upsert_pricing(provider, model, input_rate, output_rate)` | Insert or update pricing for a model |
| `get_pricing(provider, model) -> dict\|None` | Get `{"input": float, "output": float}` or None |
| `seed_from_pricing_dict(pricing) -> int` | Bulk seed from a `PRICING`-style dict, returns count |

---

## `budget_alert` module

```python
from ai_vibe_coding.budget_alert import BudgetAlertEngine, BudgetConfig, AlertThreshold
```

### `AlertThreshold` (dataclass)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `metric` | `str` | `"cost"` | Metric to monitor: `"cost"`, `"tokens"`, or `"latency"` |
| `operator` | `str` | `"gt"` | Comparison: `"gt"`, `"gte"`, `"lt"`, `"lte"` |
| `value` | `float` | `0.0` | Threshold value |
| `label` | `str` | `""` | Human-readable label |

### `BudgetConfig` (dataclass)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | `""` | Budget configuration name |
| `thresholds` | `list[AlertThreshold]` | `[]` | List of threshold definitions |
| `period` | `str` | `"monthly"` | Billing period: `"daily"`, `"weekly"`, `"monthly"` |
| `max_budget` | `float` | `0.0` | Maximum allowed cost for the period |
| `notification_channels` | `list[str]` | `["console"]` | Notification targets: `"console"`, `"slack"`, `"email"` |
| `enabled` | `bool` | `True` | Whether this budget is active |

#### Class methods

| Method | Description |
|--------|-------------|
| `from_yaml(path) -> BudgetConfig` | Load configuration from a YAML file |

### `BudgetAlertEngine`

Evaluates budget thresholds and fires alerts.

| Method | Description |
|--------|-------------|
| `add_config(config: BudgetConfig)` | Add a budget configuration |
| `check_budgets(current_spend=None) -> list[dict]` | Check all budgets; each alert dict has `name`, `metric`, `actual`, `threshold`, `message`, `timestamp` |
| `get_alert_history() -> list[dict]` | Chronological list of fired alerts |

---

## `cost_comparison` module

```python
from ai_vibe_coding.cost_comparison import compare_actual_costs, compare_estimated_vs_actual, get_cost_trend
```

### `compare_actual_costs(start_date=None, end_date=None, providers=None) -> list[dict]`

Compare actual costs across providers for a date range.

| Parameter | Type | Description |
|-----------|------|-------------|
| `start_date` | `str\|None` | ISO date filter (start) |
| `end_date` | `str\|None` | ISO date filter (end) |
| `providers` | `list[str]\|None` | Filter to specific providers; `None` = all |

Returns list sorted by `total_cost` descending. Each dict: `provider`, `total_cost`, `total_tokens`, `request_count`, `avg_latency_ms`, `cost_per_1k_tokens`.

### `compare_estimated_vs_actual(start_date=None, end_date=None, providers=None) -> list[dict]`

Compare estimated vs actual costs. Estimates use the `PRICING` dict; actuals come from the cost store.

Returns list of dicts: `provider`, `estimated_cost`, `actual_cost`, `difference`, `difference_pct`, `total_tokens`.

### `get_cost_trend(granularity="daily", start_date=None, end_date=None) -> list[dict]`

Get cost trend data over time.

| Parameter | Type | Description |
|-----------|------|-------------|
| `granularity` | `str` | `"daily"`, `"weekly"`, or `"monthly"` |

Returns list of dicts: `period`, `total_cost`, `total_tokens`, `request_count`, `avg_latency_ms`.

---

## Cost Dashboard

The cost dashboard is a standalone HTML page at `src/ai_vibe_coding/static/cost_dashboard.html`. It provides:

- **Date range filter** — start/end date inputs with filter button
- **Summary card** — aggregate cost and token display
- **Sparkline area** — SVG line chart for cost trends
- **Bar chart** — per-period cost visualization
- **Data table** — tabular view of cost records by date, provider, model
- **Auto-refresh** — meta refresh at 300s + JS `setInterval` at 30s

Serve via the FastAPI app:

```bash
uvicorn ai_vibe_coding.app:app --host 0.0.0.0 --port 8000
# Open: http://localhost:8000/static/cost_dashboard.html
```

---

## Cost API endpoints (`/api/v1/costs`)

Defined in `src/ai_vibe_coding/cost_api.py`. These are FastAPI route stubs registered on an `APIRouter`:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/costs/total` | Total cost with optional date/provider filters |
| `GET` | `/api/v1/costs/daily` | Daily cost/token breakdown |
| `GET` | `/api/v1/costs/by-provider` | Cost breakdown by provider |
| `GET` | `/api/v1/costs/by-model` | Cost breakdown by model |
| `GET` | `/api/v1/costs/by-user` | Cost breakdown by session/user |
| `GET` | `/api/v1/costs/latency/percentiles` | Latency at specified percentile |
| `GET` | `/api/v1/costs/comparison/providers` | Compare costs across providers |
| `GET` | `/api/v1/costs/trend` | Cost trend data over time |
| `GET` | `/api/v1/costs/budget/alerts` | Recent alert history |
| `POST` | `/api/v1/costs/budget/check` | Check all budgets |

## Control-plane API endpoints (`/api/v1`)

Defined in `src/ai_vibe_coding/control_api.py`. Full state, trust boundary, and recovery semantics in [control-plane.md](control-plane.md).

| Method | Path | Description |
|--------|------|-------------|
| `PUT` | `/api/v1/providers/{provider_id}` | Upsert provider configuration |
| `POST` | `/api/v1/virtual-keys` | Create scoped virtual key (plaintext returned once) |
| `GET` | `/api/v1/authorize` | Fail-closed preflight: model scope + budget check |
| `POST` | `/api/v1/spend` | Record spend (idempotent on run_id) |
| `GET` | `/api/v1/budget` | Budget summary (remaining, spent) |
| `POST` | `/api/v1/traces` | Start trace trace (supports Idempotency-Key) |
| `POST` | `/api/v1/traces/{trace_id}/spans` | Add span to trace |
| `GET` | `/api/v1/traces/{trace_id}` | Full trace with spans |
| `GET` | `/api/v1/traces/{trace_id}/export` | JSON export of trace |
| `POST` | `/api/v1/evaluations` | Create evaluation experiment |
| `POST` | `/api/v1/evaluations/{experiment_id}/scores` | Record evaluation score |
| `POST` | `/api/v1/evaluations/{experiment_id}/gate` | Evaluate release gate |
| `POST` | `/api/v1/security/scans` | Start security scan |
| `POST` | `/api/v1/security/scans/{scan_id}/findings` | Record finding (blocking findings fail the scan) |
| `GET` | `/api/v1/security/scans/{scan_id}` | Security report with findings |
| `POST` | `/api/v1/agent-runs` | Create agent run |
| `POST` | `/api/v1/agent-runs/{run_id}/steps/{step}` | Complete step |
| `POST` | `/api/v1/agent-runs/{run_id}/approval` | Request human approval |
| `POST` | `/api/v1/agent-runs/{run_id}/approval/{step}/decide` | Approve/reject (no self-approval) |
| `POST` | `/api/v1/agent-runs/{run_id}/resume` | Resume run from last checkpoint |
