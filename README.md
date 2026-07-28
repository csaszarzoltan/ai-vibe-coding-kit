# AI Vibe Coding Kit

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 695](https://img.shields.io/badge/tests-695%20total-brightgreen.svg)]()
[![Version: 0.9.0](https://img.shields.io/badge/version-0.9.0-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![CI: Test](https://github.com/csaszarzoltan/ai-vibe-coding-kit/actions/workflows/test.yml/badge.svg)](https://github.com/csaszarzoltan/ai-vibe-coding-kit/actions/workflows/test.yml)

Multi-provider LLM API wrapper with cost tracking, structured output, and tool calling. Built for Python developers who need a unified interface across OpenAI, Anthropic, DeepSeek, OpenRouter, Xiaomi MiMo, Google Gemini, Mistral AI, Cohere, and Ollama (local models).

## What's Inside

### Multi-Provider LLM Wrapper (`src/ai_vibe_coding/llm_wrapper.py`)
- `LLMProvider` ABC with `chat()`, `stream()`, `get_cost()`, `get_model_list()`
- 5 core providers: OpenAI, Anthropic, DeepSeek, OpenRouter, MiMo
- `LLMClient` facade with provider selection, `chat_async()`, `compare_providers()`
- Retry with exponential backoff (3 retries, 1s/2s/4s)
- Streaming via generator yielding text chunks
- Configurable `PRICING` dict with 2026 per-model rates

### Extended Provider Examples (`src/ai_vibe_coding/provider_examples.py`)
- 4 additional provider implementations: Gemini, Mistral, Cohere, Ollama
- `GeminiProvider` — Google Gemini via google-genai SDK
- `MistralProvider` — Mistral AI via mistralai SDK
- `CohereProvider` — Cohere chat, streaming, embeddings, and reranking
- `OllamaProvider` — Local model inference via ollama SDK (zero-cost)

### Structured Output & Tool Calling (`src/ai_vibe_coding/structured.py`)
- `chat_json()` — forces JSON output across all providers
- `chat_with_tools()` — function calling abstraction
- `ToolDef` and `ToolCallResult` dataclasses
- `LLMJSONError` and `ToolNotFoundError` exceptions

### Cost Tracking & Analytics (`src/ai_vibe_coding/cost_tracker.py`)
- `CostTracker` with thread-safe `record()`, `get_summary()`, `export_csv()`, `export_json()`
- `CostSummary` dataclass with `to_dict()` and `to_table()` (ASCII table)
- Per-provider and per-model cost breakdowns

### LLM Failover & Resilience Patterns (`src/ai_vibe_coding/resilience.py`)
- `CircuitBreaker` — state machine (CLOSED/OPEN/HALF_OPEN) with configurable failure/success thresholds and per-provider isolation
- `RetryPolicy` — exponential backoff with jitter, configurable max retries and retryable status codes
- `FallbackChain` — ordered multi-provider fallback (primary → secondary → tertiary) with health gating
- `HealthChecker` — rolling-window health scoring tracking latency, error rate, and availability per provider
- `TimeoutBudget` — per-provider and per-operation timeout configuration with global defaults
- `ResponseCache` — stale-while-revalidate caching with configurable TTL and per-provider overrides
- `Observability` — structured event emission, counter metrics, and callback hooks for every resilience layer
- `ResilientLLMClient` — facade wrapping LLMClient with all resilience layers configured via `ResilienceConfig`

### Benchmark Suite (`src/ai_vibe_coding/benchmark_runner.py`, `metric_collector.py`, `cli.py`)
- `BenchmarkTask` and `BenchmarkRunner` — define and orchestrate benchmark tasks across providers
- `BenchmarkResult` / `BenchmarkComparison` — per-run results and cross-provider comparisons
- `MetricCollector` and `BenchmarkReport` — aggregate accuracy, latency, cost, and reliability metrics
- `ai-vibe-bench` CLI — run benchmarks, list tasks, list available providers
- Evaluator functions: `exact_match`, `fuzzy_match`, `contains`

### Examples & Guides (`examples/`)
- `llm_api_wrapper.py` — legacy standalone wrapper (OpenAI + MiMo)
- `cursor-workflow.md` — vibe coding workflow with Cursor IDE
- `mimo-integration.md` — using Xiaomi MiMo for cost-effective AI coding

## Provider Comparison

| Provider | Python SDK | Key Features | Best Use Case | API Pattern |
|----------|-----------|--------------|---------------|-------------|
| **OpenAI** | `openai>=1.0.0` | GPT-4/4.5/5, function calling, structured outputs, vision | General-purpose, production apps | OpenAI client (`client.chat.completions.create`) |
| **Anthropic** | `anthropic>=0.18.0` | Claude 3.5/4 Sonnet, long context (200K), tool use, safety | Reasoning, code generation, long documents | Anthropic client (`client.messages.create`) |
| **DeepSeek** | `openai>=1.0.0` | DeepSeek-V3/R1, OpenAI-compatible API, low cost | Cost-sensitive production, reasoning tasks | OpenAI-compatible (`base_url=deepseek`) |
| **OpenRouter** | `httpx>=0.27.0` | 100+ models, unified billing, model fallback routing | Multi-model comparison, fallback chains | HTTP POST (`openrouter.ai/api/v1`) |
| **MiMo** | `requests>=2.31.0` | Xiaomi MiMo v2.5, ultra-low pricing, REST API | High-volume, cost-optimized inference | REST POST (`mimo.z.ai`) |
| **Gemini** | `google-genai` | Gemini 2.5 Flash/Pro, native multimodality, 1M context | Multimodal (text+image+audio), free tier | Google AI client (`client.models.generate_content`) |
| **Mistral** | `mistralai` | Mistral Large/Small, excellent code generation, EU-hosted | Code generation, European data residency | Mistral client (`client.chat.complete`) |
| **Cohere** | `cohere` | Command R/A+, embeddings, RAG reranking, enterprise | RAG pipelines, semantic search, document AI | Cohere client V2 (`co.chat`, `co.embed`, `co.rerank`) |
| **Ollama** | `ollama` | Local models (Gemma3, Llama3, Phi-4, Qwen2.5), zero-cost | Privacy-sensitive, offline, dev/test environments | Ollama client (`ollama.chat`, `ollama.generate`) |

## Quick Start

```bash
git clone https://github.com/csaszarzoltan/ai-vibe-coding-kit.git
cd ai-vibe-coding-kit
pip install -e ".[dev]"
```

Set API keys for the providers you want to use:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export DEEPSEEK_API_KEY="sk-..."
export OPENROUTER_API_KEY="sk-or-..."
export MIMO_API_KEY="..."
export GEMINI_API_KEY="..."
export MISTRAL_API_KEY="..."
export CO_API_KEY="..."
# Ollama runs locally — no API key needed
```

### Basic Usage

```python
from ai_vibe_coding import LLMClient

# Use any provider with the same interface
client = LLMClient(provider="openai")
response = client.chat("Explain this code: ...")
print(response.content)
print(f"Cost: ${response.cost_usd:.4f}")
print(f"Tokens: {response.tokens_used}")
print(f"Latency: {response.latency_ms:.0f}ms")

# Switch to a cheaper provider
client = LLMClient(provider="mimo")
response = client.chat("Write a Python function: ...")
```

### Streaming

```python
from ai_vibe_coding import LLMClient

client = LLMClient(provider="openai")
for chunk in client.stream("Tell me a story"):
    print(chunk, end="", flush=True)
```

### Compare Providers

```python
from ai_vibe_coding import LLMClient

client = LLMClient(provider="openai")
results = client.compare_providers("Write a haiku about testing")
for provider, response in results.items():
    print(f"{provider}: {response.content}")
    print(f"  Cost: ${response.cost_usd:.4f}")
```

### Structured JSON Output

```python
from ai_vibe_coding import LLMClient
from ai_vibe_coding.structured import chat_json

client = LLMClient(provider="openai")
result = chat_json(
    client,
    "List 3 Python testing frameworks with their pros and cons",
    schema={"type": "object", "properties": {"frameworks": {"type": "array"}}},
)
print(result)  # parsed dict
```

### Tool Calling

```python
from ai_vibe_coding import LLMClient
from ai_vibe_coding.structured import chat_with_tools, ToolDef

client = LLMClient(provider="openai")
tools = [
    ToolDef(
        name="get_weather",
        description="Get current weather for a city",
        parameters={"type": "object", "properties": {"city": {"type": "string"}}},
    ),
]
result = chat_with_tools(client, "What's the weather in Zurich?", tools)
print(result.tool_name)    # "get_weather"
print(result.arguments)    # {"city": "Zurich"}
```

### Cost Tracking

```python
from ai_vibe_coding import LLMClient
from ai_vibe_coding.cost_tracker import CostTracker

tracker = CostTracker()
client = LLMClient(provider="openai")

# Record each call
for prompt in prompts:
    response = client.chat(prompt)
    tracker.record(response)

# Print summary table
summary = tracker.get_summary()
print(summary.to_table())

# Export for analysis
tracker.export_csv("costs.csv")
tracker.export_json("costs.json")
```

### Using Extended Providers

All four extended providers implement the same `LLMProvider` interface and can be used either through `LLMClient` or directly.

```python
from ai_vibe_coding import LLMClient

# Use any new provider with the same LLMClient facade
for provider in ["gemini", "mistral", "cohere", "ollama"]:
    client = LLMClient(provider=provider)
    response = client.chat("Explain the singleton pattern")
    print(f"[{provider}] {response.content}")
    print(f"  Cost: ${response.cost_usd:.6f}")
```

Or use them directly:

```python
from ai_vibe_coding.provider_examples import (
    GeminiProvider,
    MistralProvider,
    CohereProvider,
    OllamaProvider,
)

# Gemini — multimodal, 1M context, free tier available
gemini = GeminiProvider(api_key="...")  # or set GEMINI_API_KEY
response = gemini.chat([{"role": "user", "content": "Describe this image"}])
# Models: gemini-2.5-flash (default), gemini-2.5-pro, gemini-2.0-flash

# Mistral — strong code generation, EU data residency
mistral = MistralProvider(api_key="...")  # or set MISTRAL_API_KEY
response = mistral.chat([{"role": "user", "content": "Write a Python decorator"}])
# Models: mistral-large-latest (default), mistral-small-latest

# Cohere — chat + embeddings + RAG reranking
cohere = CohereProvider(api_key="...")  # or set CO_API_KEY
response = cohere.chat([{"role": "user", "content": "Explain RAG architecture"}])
embedding = cohere.embed(["text to embed"], input_type="search_document")
reranked = cohere.rerank("query", ["doc1", "doc2"], top_n=5)
# Models: command-a-plus-05-2026 (default), command-r-08-2024

# Ollama — local models, zero cost, private
ollama = OllamaProvider()  # defaults to http://localhost:11434, model=gemma3
response = ollama.chat([{"role": "user", "content": "Hello from local LLM"}])
print(f"Cost: ${response.cost_usd}")  # Always 0.0 — local inference
# Models: gemma3 (default), llama3, mistral, phi4, qwen2.5
```

## Getting Started with MCP in 5 Minutes

Connect AI coding assistants (Cursor, Claude Desktop, Windsurf) to a local
toolbox — file read/write, web search, sandboxed Python execution, and more.
No API keys needed.

### 1. Install the `mcp` package

```bash
pip install mcp
```

Already in the project venv? `pip install -e ".[dev]"` installs it too.

### 2. Run the server

```bash
cd ai-vibe-coding-kit
python examples/standalone_mcp_server.py
```

The server listens on stdin/stdout (stdio transport). Press Ctrl+C to stop.

To test it's alive, run from another terminal:

```bash
python -c "
import sys; sys.path.insert(0, '.')
from examples.standalone_mcp_server import get_weather
print(get_weather('Zurich'))
"
```

For an interactive test UI: `mcp dev examples/standalone_mcp_server.py` opens
the MCP Inspector at `http://localhost:5173`.

### 3. Configure Cursor

Add `.cursor/mcp.json` to your project root:

```json
{
  "mcpServers": {
    "ai-vibe-coding": {
      "command": "python",
      "args": ["${workspaceFolder}/examples/standalone_mcp_server.py"],
      "env": {
        "ALLOWED_BASE_DIR": "${workspaceFolder}",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Restart Cursor. Look for a green "MCP connected" indicator.

### 4. Configure Claude Desktop

Edit `claude_desktop_config.json` (find it at
`~/Library/Application Support/Claude/` on macOS,
`%APPDATA%\Claude\` on Windows,
`~/.config/Claude/` on Linux):

```json
{
  "mcpServers": {
    "ai-vibe-coding": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/ai-vibe-coding-kit/examples/standalone_mcp_server.py"],
      "env": {
        "ALLOWED_BASE_DIR": "/ABSOLUTE/PATH/TO/ai-vibe-coding-kit",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Replace the paths with your actual repo path. Restart Claude Desktop — a
hammer icon appears in the input area when tools are connected.

### 5. Verify

Try these prompts in the connected editor:

- **read_file** — "Read the README.md file"
- **write_file** — "Write hello.txt with 'Hello MCP world'"
- **list_directory** — "List files in the examples directory"
- **search_web** — "Search the web for Python MCP SDK docs"
- **execute_python** — "Run Python: print(sum(range(100)))"
- **get_weather** — "What's the weather in Budapest?"

See [docs/mcp-guide.md](docs/mcp-guide.md) for the full tool reference,
security model, troubleshooting, and the programmatic API.

---

## Cost Optimizer — Compare & Save on LLM Costs

Estimate and compare LLM API costs across 9 providers with the `ai-vibe-bench cost` CLI.
Get task-type-aware recommendations for coding, chat, analysis, and translation
without making a single API call.

### Quick comparison

```bash
ai-vibe-bench cost compare 1000 500
```

Output shows all 24 models from all 9 providers ranked by total cost (cheapest first),
with per-1K-token normalised costs.

### Estimate a single call

```bash
ai-vibe-bench cost estimate openai gpt-4 1000 500
```

Expected output:

```
Provider:     openai
Model:        gpt-4
Input tokens: 1000
Output tokens:500
Total cost:   $0.060000
```

### Get a recommendation

Find the best provider for your workload:

```bash
ai-vibe-bench cost recommend coding 5000 2000
```

Output ranks providers by a weighted value score that balances cost, quality,
and speed according to the task profile.

### Python API

```python
from ai_vibe_coding.cost_calculator import calculate_cost, compare_all, recommend_for_task

# Quick cost check
cost = calculate_cost(1000, 500, "openai", "gpt-4")
print(f"Cost: ${cost:.4f}")

# Compare providers
options = compare_all(1000, 500)
for opt in options[:5]:
    print(f"{opt['provider']:12s} {opt['model']:20s} ${opt['total_cost']:.6f}")

# Task-specific recommendation
recs = recommend_for_task(5000, 2000, "coding")
for rec in recs:
    print(f"{rec['provider']:12s} {rec['model']:20s} "
          f"${rec['total_cost']:.6f}  (score: {rec['value_score']:.2f})")
```

### Pricing data browser

```bash
ai-vibe-bench cost pricing
ai-vibe-bench cost pricing --provider openai
ai-vibe-bench cost pricing --provider openai --model gpt-4
```

See [docs/cost-optimizer.md](docs/cost-optimizer.md) for the full reference
with provider pricing tables, task profiles, cost profiles JSON structure,
pricing update workflow, and API reference.

---

## Production Resilience

The kit ships with production-grade failover patterns for enterprise AI reliability.

### Quick Start

```python
from ai_vibe_coding import LLMClient, CircuitBreakerConfig, RetryPolicyConfig, ResilienceConfig, ResilientLLMClient

config = ResilienceConfig(
    circuit_breaker=CircuitBreakerConfig(failure_threshold=5, open_timeout=30.0),
    retry=RetryPolicyConfig(max_retries=3, base_delay=1.0),
)
client = ResilientLLMClient(LLMClient(provider="openai"), config=config)

# Auto-retry with circuit breaker, timeout enforcement
response = client.chat_with_failover(
    [{"role": "user", "content": "Hello"}],
    model="gpt-4",
)
print(f"Response from {response.provider} (retries: {response.retry_count}, circuit: {response.circuit_state.value})")
```

### Configuring Timeout Budgets

```python
from ai_vibe_coding import TimeoutBudget, TimeoutConfig

budget = TimeoutBudget(
    global_default=TimeoutConfig(chat=30.0, stream=60.0),
    per_provider={
        "openai": TimeoutConfig(chat=15.0, stream=30.0),
        "ollama": TimeoutConfig(chat=60.0, stream=120.0),
    }
)
timeout = budget.get_timeout("openai", "chat")  # 15.0 seconds
```

### Health Monitoring

```python
from ai_vibe_coding import HealthChecker

checker = HealthChecker(window_size=100)
# Record samples
checker.record_sample("openai", 1200, success=True)   # 1.2s latency, success
checker.record_sample("openai", 30000, success=False)  # timeout, failure

status = checker.check("openai")
print(f"Status: {status.status.value}, Error rate: {status.error_rate:.1%}, Latency: {status.latency_ms:.0f}ms")
```

### Resilience Configuration Reference

All resilience layers are configured via `ResilienceConfig`:

| Config Field | Type | Default | Description |
|-------------|------|---------|-------------|
| `circuit_breaker` | `CircuitBreakerConfig` | `None` | Failure/success thresholds and open timeout |
| `retry` | `RetryPolicyConfig` | `None` | Max retries, base delay, retryable status codes |
| `timeout` | `dict[str, TimeoutConfig]` | `None` | Per-provider timeout overrides |
| `global_timeout` | `TimeoutConfig` | `None` | Global fallback timeout |
| `cache` | `dict[str, ResponseCacheConfig]` | `None` | Per-provider cache TTL/SWR config |

---

## Agent Orchestration Templates

Compose multiple LLM agents into coordinated workflows with 4 built-in
orchestration patterns. Each pattern supports heterogeneous providers, cost
limits, circuit breakers, and shared state.

### Quick Start — Sequential Pipeline

```python
from ai_vibe_coding import AgentPipeline
from ai_vibe_coding.llm_wrapper import LLMClient

research = LLMClient(provider="openai", model="gpt-4o-mini")
writer   = LLMClient(provider="anthropic", model="claude-3-haiku-20240307")
reviewer = LLMClient(provider="deepseek", model="deepseek-chat")

pipeline = AgentPipeline(agents=[research, writer, reviewer])
result = pipeline.run("Impact of quantum computing on cryptography")
print(f"Status: {result.status}, Cost: ${result.total_cost_usd:.4f}")
```

### Quick Start — Pub/Sub Event-Driven

```python
from ai_vibe_coding import AgentMessage, AgentPubSubCoordinator, MessageBus

bus = MessageBus()
coordinator = AgentPubSubCoordinator(message_bus=bus)

def on_alert(msg: AgentMessage) -> None:
    print(f"ALERT: {msg.payload}")

coordinator.register_agent("alerter", on_alert, subscription="alert.*")
coordinator.start()

# Sensor publishes → analyzer detects anomaly → alerter fires
bus.publish(AgentMessage(from_agent="sensor", to_agent=None,
            type="sensor.cpu", payload={"value": 95}))
coordinator.stop()
```

### All 4 Patterns

| Pattern | Class | Use Case |
|---------|-------|----------|
| **Sequential Pipeline** | `AgentPipeline` | Research → Write → Review (fixed order) |
| **Parallel Fan-Out/Fan-In** | `AgentFanOut` + `AgentFanIn` | Technical + Business + Security analysis |
| **Hierarchical Supervisor** | `AgentSupervisor` | LLM routes tasks to specialists |
| **Pub/Sub Event-Driven** | `AgentPubSubCoordinator` | Agent reacts to matching message types |

### Foundation Layer

- `MessageBus` — thread-safe pub/sub with wildcard type filtering
- `SharedState` — thread-safe key-value store with namespace isolation

### Error Handling

- `AgentCircuitBreaker` — per-provider failure threshold gate
- `AgentRetryPolicy` — exponential backoff with dead-letter queue
- `AgentFallback` — primary → fallback failover

See [docs/agent-orchestration.md](docs/agent-orchestration.md) for the full
reference with code examples, architecture diagrams, cost management, and
migration guides.

---

## Installation

### From source (recommended for development)

```bash
git clone https://github.com/csaszarzoltan/ai-vibe-coding-kit.git
cd ai-vibe-coding-kit
pip install -e ".[dev]"
```

### Dependencies

- `openai>=1.0.0` — OpenAI and DeepSeek (OpenAI-compatible API)
- `anthropic>=0.18.0` — Anthropic Claude
- `httpx>=0.27.0` — OpenRouter async HTTP
- `requests>=2.31.0` — MiMo REST API
- `google-genai>=1.0.0` — Google Gemini SDK
- `mistralai>=1.0.0` — Mistral AI SDK
- `cohere>=5.0.0` — Cohere SDK (chat, embed, rerank)
- `ollama>=0.4.0` — Ollama local model SDK
- `python-dotenv>=1.0.0` — .env file loading

### Dev dependencies

- `pytest>=7.4.0`, `pytest-asyncio`, `pytest-mock`, `responses` — testing
- `ruff>=0.4.0` — linting

## Testing

```bash
# Run all tests (no API keys needed — all HTTP is mocked)
pytest tests/ -v

# Run specific module tests
pytest tests/test_llm_wrapper.py -v
pytest tests/test_structured.py -v
pytest tests/test_cost_tracker.py -v
pytest tests/test_playground.py -v

# Run benchmark tests (62 tests)
pytest tests/test_benchmark_runner.py -v

# Run frontend contract tests (29 pass, 17 behavioral stubs pending)
pytest tests/test_frontend_playground.py -v

# Lint
ruff check src/ tests/
```

All 695 tests pass with no real API keys required. HTTP calls are mocked via `unittest.mock` and `responses`.

## CI/CD Integration

Three GitHub Actions workflow templates live in `.github/workflows/`. `test.yml` runs automatically; the other two are pre-configured and will also run on push to `main`. To disable an optional workflow, add a `.disabled` suffix to its filename.

### `test.yml` — Automated Testing ✅

**Status:** Enabled by default — runs on every push/PR to `main`.

- **Lint:** `ruff check` across the codebase
- **Test:** `pytest -v --tb=short` on Python 3.11 and 3.12
- **Cache:** pip cache keyed on `pyproject.toml`

```yaml
name: Test
on:
  push: {branches: [main]}
  pull_request: {branches: [main]}
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
          cache-dependency-path: pyproject.toml
      - run: pip install -e ".[dev]"
      - run: ruff check
      - run: pytest -v --tb=short
```

No setup needed — just push to GitHub and the workflow runs.

### `llm-integration-test.yml` — Provider Integration Testing

**Status:** Pre-configured. Runs on push/PR to `main`. Add `.disabled` suffix to disable.

Validates actual LLM provider connectivity, response parsing, and cost calculations against live API endpoints.

**To enable:**

No activation needed — the workflow is already active. Add `.disabled` to the filename to skip it.

If you only want to test specific providers, add only their API keys as GitHub Secrets (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `MIMO_API_KEY`, `GEMINI_API_KEY`, `MISTRAL_API_KEY`, `CO_API_KEY`). Push to `main` or trigger via `workflow_dispatch`.

The workflow installs deps, lints provider modules, runs the full unit suite (mocked, no keys needed), runs provider-specific integration tests when keys are present, reports configured API keys, and uploads JUnit XML artifacts.

> **Note:** Ollama tests always run against mocked endpoints in CI. Uncomment the `OLLAMA_HOST` secret if you self-host Ollama.

### `deploy.yml` — Railway / Docker Deployment

**Status:** Pre-configured. Runs on push/PR to `main`. Add `.disabled` suffix to disable.

Deploys the LLM Playground API to Railway using the existing `Dockerfile` and `railway.toml`.

**To enable:**

No activation needed — the workflow is already active. Add `.disabled` to the filename to skip it.

Set up your Railway token and link your project, then push to `main` (or trigger manually via the GitHub UI):

```bash
railway login
railway token create --name github-actions
railway link --project <your-project-name>
```

Add `RAILWAY_TOKEN` as a GitHub Actions secret.

```yaml
name: Deploy to Railway
on:
  push: {branches: [main]}
  workflow_dispatch:
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: railwayapp/actions/deploy@v3
        with:
          token: ${{ secrets.RAILWAY_TOKEN }}
          dockerfile: Dockerfile
          config: railway.toml
```

> **Tip:** The `deploy.yml` workflow supports manual dispatch from the GitHub Actions tab — useful for redeploying without a new commit.

## Supported Providers & Pricing

| Provider | Models | Input (per 1K tokens) | Output (per 1K tokens) |
|----------|--------|-----------------------|------------------------|
| OpenAI | gpt-4, gpt-4-turbo, gpt-4.5, gpt-5 | $0.03–$0.08 | $0.06–$0.24 |
| Anthropic | claude-3.5-sonnet, claude-4-sonnet, claude-4.5-sonnet | $0.003–$0.005 | $0.015–$0.025 |
| DeepSeek | deepseek-v3, deepseek-r1 | $0.0014 | $0.0028 |
| OpenRouter | 100+ models (routed) | varies | varies |
| MiMo | mimo-v2.5 | $0.0004 | $0.002 |
| Gemini | gemini-2.5-flash, gemini-2.5-pro, gemini-2.0-flash | $0.00004–$0.00125 | $0.00015–$0.005 |
| Mistral | mistral-large-latest, mistral-small-latest | $0.001–$0.004 | $0.003–$0.012 |
| Cohere | command-a-plus-05-2026, command-r-08-2024, embed-v4.0 | $0.0001–$0.003 | $0.0001–$0.015 |
| Ollama | gemma3, llama3, mistral, phi4, qwen2.5 | $0.00 (local) | $0.00 (local) |

Pricing is stored in the `PRICING` dict in `llm_wrapper.py` — update it when providers change their rates.

### Prompt Chaining & Agent Workflow Templates (`src/ai_vibe_coding/chain_templates.py`)

Compose LLM calls into multi-step workflows with 7 chain patterns:

- **SequentialChain** — ordered A→B→C pipeline with state passing between steps
- **ConditionalChain** — gate routing with true/false branches and converge steps
- **ParallelChain** — fan-out/fan-in with `ThreadPoolExecutor` and configurable aggregation
- **MapReduceChain** — split/process/merge for documents exceeding context windows
- **AgentWithToolsChain** — ReAct-style tool-calling loop with configurable max iterations
- **HITLStep** — human-in-the-loop approval gates with callable or CLI channels
- **ChainRunner** — universal chain execution with streaming mode

All chains share the same `.run(input_data=None) -> ChainResult` interface, providing
consistent cost tracking, token accounting, and step-by-step debugging.

```python
from ai_vibe_coding import LLMClient, SequentialChain, ChainRunner

client = LLMClient(provider="openai")

def draft(ctx):
    return client.chat(f"Draft an email about: {ctx.steps.get('input', '')}")

def proofread(ctx):
    return client.chat(f"Proofread this email:\n{ctx.steps['draft']}")

draft.name = "draft"
proofread.name = "proofread"

chain = SequentialChain(steps=[draft, proofread])
result = ChainRunner().run(chain, "Team standup reminder")
print(f"Status: {result.status}, Cost: ${result.total_cost_usd:.4f}")
```

See [docs/prompt-chaining.md](docs/prompt-chaining.md) for the full pattern reference,
real-world use cases, and API documentation.

## Documentation

- [Quick Start Guide](docs/quickstart.md)
- [API Reference](docs/api-reference.md)
- [Prompt Chaining Guide](docs/prompt-chaining.md)
- [Agent Orchestration Guide](docs/agent-orchestration.md)
- [Model Comparison & Pricing](docs/model-comparison.md)
- [Benchmark Suite Guide](docs/benchmark-guide.md)
- [MCP Server Guide](docs/mcp-guide.md)
- [Best Practices](docs/best-practices.md)
- [Cursor Workflow Guide](examples/cursor-workflow.md)
- [MiMo Integration Guide](examples/mimo-integration.md)

## Use Cases

- **Multi-provider routing** — switch between models for cost/quality tradeoffs
- **Cost monitoring** — track spending across providers in real-time
- **Structured output** — force JSON responses for programmatic use
- **Tool calling** — give LLMs access to functions and APIs
- **Provider comparison** — benchmark the same prompt across all 9 providers
- **Streaming UX** — real-time text streaming for chat interfaces
- **RAG pipelines** — Cohere embeddings and reranking for semantic search
- **Local inference** — Ollama for privacy-sensitive, offline, or dev/test use
- **Multimodal prompts** — Gemini's native image+text+audio understanding

## Benchmark Suite

Compare all 9 LLM providers on coding tasks. The benchmark suite automates running
prompts across provider/model combinations, evaluating responses against ground-truth
answers, and producing structured reports with accuracy, latency, cost, and reliability
metrics.

### CLI Quick Start

```bash
# List available providers (based on set env vars)
ai-vibe-bench list-providers

# Run a single task across two providers
ai-vibe-bench run \
    --providers openai,gpt-4 \
    --providers deepseek,deepseek-v3 \
    --task-file benchmarks/default.json \
    --format markdown

# Full comparison across all 9 providers, 3 runs each
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
    --format markdown --output report.md
```

### Defining Benchmark Tasks

Tasks are JSON files with a `version` and `tasks` array:

```json
{
  "version": "1.0",
  "tasks": [
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

Supported evaluators: `exact_match` (default), `fuzzy_match` (Jaccard similarity),
`contains` (substring match).

### Python API

```python
from ai_vibe_coding import (
    BenchmarkRunner, BenchmarkTask, MetricCollector,
)

runner = BenchmarkRunner()
runner.add_task(BenchmarkTask(
    id="qa-1", name="Simple QA",
    prompt_template="What is the capital of France?",
    expected_answer="Paris", evaluator="contains",
))

results = runner.run(
    provider_model_pairs=[("openai", "gpt-4")],
    num_runs=3, temperature=0.0,
)

collector = MetricCollector()
collector.record_results(results)
report = collector.get_report(title="My Benchmark")
print(report.to_markdown())        # Markdown table with metrics
print(report.to_ascii_table())     # Console-friendly table
print(report.to_dict())            # JSON-compatible dict
```

### Provider Selection

Use benchmark reports to pick the right provider for your needs:

| Goal | Key Metric |
|------|-----------|
| Highest accuracy | Provider with highest `accuracy_mean` |
| Lowest latency | Provider with lowest `avg_latency_ms` |
| Lowest cost | Provider with lowest `avg_cost_usd` |
| Best reliability | Provider with lowest `error_rate` |
| Best overall value | Compare accuracy/cost ratio |

### Full Reference

See [docs/benchmark-guide.md](docs/benchmark-guide.md) for:
- Complete CLI reference (all flags and subcommands)
- Task file format specification
- Report format examples (JSON, Markdown, ASCII)
- Evaluator details
- Programmatic API with cost tracking

## LLM Playground

Interactive web-based LLM playground for comparing all 9 providers side-by-side. Check provider responses, latency, cost, and response structure in one place.

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)

### Quick Start

```bash
# 1. Install with web dependencies
cd ai-vibe-coding-kit
pip install -e ".[dev]"

# 2. Set API keys (at least one provider)
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
# ... other providers (see Supported Providers table)

# 3. Start the server
uvicorn ai_vibe_coding.app:app --host 0.0.0.0 --port 8000

# 4. Open in browser
open http://localhost:8000/static/index.html
```

### API Endpoints

#### `POST /api/playground/compare`

Compare a prompt across selected LLM providers.

**Request:**
```bash
curl -X POST http://localhost:8000/api/playground/compare \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Write a Python function to check if a string is a palindrome",
    "providers": ["openai", "anthropic", "deepseek", "mimo"]
  }'
```

**Response:**
```json
{
  "results": {
    "openai": {
      "content": "def is_palindrome(s: str) -> bool:\n    ...",
      "provider": "openai",
      "model": "gpt-4",
      "tokens_used": 120,
      "cost_usd": 0.0035,
      "latency": {
        "time_to_first_token_ms": 234.56,
        "total_ms": 1234.56
      },
      "character_count": 312,
      "response_highlights": {
        "code_blocks": 1,
        "inline_code": 2,
        "list_items": 0,
        "tables": 0,
        "json_blocks": 0
      },
      "error": null
    }
  },
  "total_latency_ms": 5200.42
}
```

Optional fields:
- `system_prompt` — prepend a system message to the prompt
- `providers` — if omitted, all 9 providers are queried

#### `GET /health`

Health check for Railway's deployment monitoring:

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.3.0"}
```

### 9 Supported Providers

| Provider | Slug | Auth | Default Model |
|----------|------|------|---------------|
| OpenAI | `openai` | `OPENAI_API_KEY` | gpt-4 |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` | claude-4-sonnet |
| DeepSeek | `deepseek` | `DEEPSEEK_API_KEY` | deepseek-v3 |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` | openai/gpt-4 |
| MiMo | `mimo` | `MIMO_API_KEY` | mimo-v2.5 |
| Gemini | `gemini` | `GEMINI_API_KEY` | gemini-2.5-flash |
| Mistral | `mistral` | `MISTRAL_API_KEY` | mistral-large-latest |
| Cohere | `cohere` | `CO_API_KEY` | command-a-plus-05-2026 |
| Ollama | `ollama` | (none — local) | gemma3 |

### Features

| Feature | Detail |
|---------|--------|
| **Rate limiting** | 20 requests per 60s per client IP (sliding window) |
| **SSRF protection** | Blocks prompts containing URLs to localhost, 127.0.0.1, 169.254.169.254, private subnets (10.x, 172.16-31.x, 192.168.x) |
| **Latency tracking** | Time-to-first-token via streaming + total response time |
| **Per-provider errors** | A single failing provider never breaks the full comparison |
| **Response highlights** | Auto-detection of code blocks, inline code, lists, tables, JSON objects |
| **Character count** | Per-result character length |

### Deployment

#### Railway

A ready-to-deploy config is included:

- [`railway.toml`](railway.toml) — build and deploy config with health check path, restart policy, env vars
- [`Dockerfile`](Dockerfile) — `python:3.11-slim` base, `uv` for fast installs, non-root user

```bash
# Railway auto-detects the config. Deploy via:
railway up
```

Set the same `*_API_KEY` environment variables in the Railway dashboard for each provider you want to use.

### Frontend Status

The playground ships with:

| File | Status | Description |
|------|--------|-------------|
| `static/index.html` | **Complete** | HTML shell with 9 provider checkboxes, prompt textarea, Compare button, results grid |
| `static/playground.css` | *In progress* | Stub file — responsive grid layout pending |
| `static/playground.js` | *In progress* | Stub file — API calls, rendering, and metrics display pending |

The backend API is fully functional and can be used via `curl`, HTTP clients, or the frontend once the JS/CSS are implemented. See [`docs/api-reference.md`](docs/api-reference.md) for the full contract spec.

### Testing

```bash
# Run all playground tests (42 tests — no API keys needed)
pytest tests/test_playground.py -v

# Run frontend contract tests (29 pass, 17 behavioral stubs pending)
pytest tests/test_frontend_playground.py -v
```

---

## Tech Stack

- **Language:** Python 3.11+
- **LLM SDKs:** openai, anthropic, httpx, google-genai, mistralai, cohere, ollama
- **Testing:** pytest, pytest-asyncio, pytest-mock, responses
- **Linting:** ruff
- **CI:** GitHub Actions — [test.yml](.github/workflows/test.yml), [llm-integration-test.yml](.github/workflows/llm-integration-test.yml), [deploy.yml](.github/workflows/deploy.yml)

## Project Structure

```
src/ai_vibe_coding/
    __init__.py          — package exports (9 providers, tools, cost tracking)
    llm_wrapper.py       — multi-provider wrapper with retry, streaming, async
    provider_examples.py — extended providers: Gemini, Mistral, Cohere, Ollama
    structured.py        — JSON mode and tool calling
    cost_tracker.py      — thread-safe cost tracking and export
    benchmark_runner.py  — benchmark orchestration (tasks, runners, comparisons)
    metric_collector.py  — metrics aggregation, reporting, evaluators
    cli.py               — ai-vibe-bench CLI entry point
    mcp_server.py        — MCP server integration
    agent_team.py        — multi-agent team orchestration
    playground.py        — FastAPI router for LLM Playground API
    app.py               — FastAPI application entry point
static/
    index.html           — Playground HTML shell
    playground.css       — Playground styles (stub)
    playground.js        — Playground logic (stub)
tests/
    test_llm_wrapper.py  — 29 tests
    test_structured.py   — 11 tests
    test_cost_tracker.py — 22 tests
    test_gemini_provider.py  — 20 tests
    test_mistral_provider.py — 18 tests
    test_cohere_provider.py  — 26 tests
    test_ollama_provider.py  — 18 tests
    test_mcp_server.py       — MCP server tests
    test_agent_team.py       — agent team orchestration tests
    test_benchmark_runner.py — 62 benchmark suite tests
    test_playground.py       — 42 playground API tests
    test_frontend_playground.py — 46 frontend contract tests
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.

## Contributing

Contributions are welcome! Please:

1. Fork the repo and create a feature branch
2. Write tests for new features (TDD)
3. Ensure `ruff check src/ tests/` passes
4. Ensure `pytest tests/` passes (all 695 tests, no API keys needed)
5. Review the [CI/CD workflows](.github/workflows/) — `test.yml` runs automatically on PRs
6. Submit a pull request

## License

MIT License — see [LICENSE](LICENSE) for details.

## Author

**Zoltan Csaszar**
- GitHub: [@csaszarzoltan](https://github.com/csaszarzoltan)
- Upwork: [Profile](https://www.upwork.com/freelancers/~010b8149572fd46b3d)
- Location: Zurich, Switzerland

---

Star this repo if you find it useful!
