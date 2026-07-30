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
