# AI Vibe Coding Kit

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 51](https://img.shields.io/badge/tests-51%20passed-brightgreen.svg)]()
[![Version: 0.3.0](https://img.shields.io/badge/version-0.3.0-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Multi-provider LLM API wrapper with cost tracking, structured output, and tool calling. Built for Python developers who need a unified interface across OpenAI, Anthropic, DeepSeek, OpenRouter, and Xiaomi MiMo.

## What's Inside

### Multi-Provider LLM Wrapper (`src/ai_vibe_coding/llm_wrapper.py`)
- `LLMProvider` ABC with `chat()`, `stream()`, `get_cost()`, `get_model_list()`
- 5 concrete providers: OpenAI, Anthropic, DeepSeek, OpenRouter, MiMo
- `LLMClient` facade with provider selection, `chat_async()`, `compare_providers()`
- Retry with exponential backoff (3 retries, 1s/2s/4s)
- Streaming via generator yielding text chunks
- Configurable `PRICING` dict with 2026 per-model rates

### Structured Output & Tool Calling (`src/ai_vibe_coding/structured.py`)
- `chat_json()` — forces JSON output across all providers
- `chat_with_tools()` — function calling abstraction
- `ToolDef` and `ToolCallResult` dataclasses
- `LLMJSONError` and `ToolNotFoundError` exceptions

### Cost Tracking & Analytics (`src/ai_vibe_coding/cost_tracker.py`)
- `CostTracker` with thread-safe `record()`, `get_summary()`, `export_csv()`, `export_json()`
- `CostSummary` dataclass with `to_dict()` and `to_table()` (ASCII table)
- Per-provider and per-model cost breakdowns

### Examples & Guides (`examples/`)
- `llm_api_wrapper.py` — legacy standalone wrapper (OpenAI + MiMo)
- `cursor-workflow.md` — vibe coding workflow with Cursor IDE
- `mimo-integration.md` — using Xiaomi MiMo for cost-effective AI coding

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

# Lint
ruff check src/ tests/
```

All 51 tests pass with no real API keys required. HTTP calls are mocked via `unittest.mock` and `responses`.

## Supported Providers & Pricing

| Provider | Models | Input (per 1K tokens) | Output (per 1K tokens) |
|----------|--------|-----------------------|------------------------|
| OpenAI | gpt-4, gpt-4-turbo, gpt-4.5, gpt-5 | $0.03–$0.08 | $0.06–$0.24 |
| Anthropic | claude-3.5-sonnet, claude-4-sonnet, claude-4.5-sonnet | $0.003–$0.005 | $0.015–$0.025 |
| DeepSeek | deepseek-v3, deepseek-r1 | $0.0014 | $0.0028 |
| OpenRouter | 100+ models (routed) | varies | varies |
| MiMo | mimo-v2.5 | $0.0004 | $0.002 |

Pricing is stored in the `PRICING` dict in `llm_wrapper.py` — update it when providers change their rates.

## Documentation

- [Quick Start Guide](docs/quickstart.md)
- [API Reference](docs/api-reference.md)
- [Model Comparison & Pricing](docs/model-comparison.md)
- [Best Practices](docs/best-practices.md)
- [Cursor Workflow Guide](examples/cursor-workflow.md)
- [MiMo Integration Guide](examples/mimo-integration.md)

## Use Cases

- **Multi-provider routing** — switch between models for cost/quality tradeoffs
- **Cost monitoring** — track spending across providers in real-time
- **Structured output** — force JSON responses for programmatic use
- **Tool calling** — give LLMs access to functions and APIs
- **Provider comparison** — benchmark the same prompt across all providers
- **Streaming UX** — real-time text streaming for chat interfaces

## Tech Stack

- **Language:** Python 3.11+
- **LLM SDKs:** openai, anthropic, httpx
- **Testing:** pytest, pytest-asyncio, pytest-mock, responses
- **Linting:** ruff
- **CI:** GitHub Actions

## Project Structure

```
src/ai_vibe_coding/
    __init__.py          — package exports (LLMClient, LLMProvider, LLMResponse)
    llm_wrapper.py       — multi-provider wrapper with retry, streaming, async
    structured.py        — JSON mode and tool calling
    cost_tracker.py      — thread-safe cost tracking and export
tests/
    test_llm_wrapper.py  — 29 tests
    test_structured.py   — 11 tests
    test_cost_tracker.py — 22 tests
examples/
    llm_api_wrapper.py   — legacy standalone wrapper
    cursor-workflow.md   — Cursor IDE workflow
    mimo-integration.md  — MiMo cost comparison
docs/
    quickstart.md        — getting started guide
    api-reference.md     — full API reference
    model-comparison.md  — provider pricing and benchmarks
    best-practices.md    — prompt engineering and cost optimization
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.

## Contributing

Contributions are welcome! Please:

1. Fork the repo and create a feature branch
2. Write tests for new features (TDD)
3. Ensure `ruff check src/ tests/` passes
4. Ensure `pytest tests/` passes
5. Submit a pull request

## License

MIT License — see [LICENSE](LICENSE) for details.

## Author

**Zoltan Csaszar**
- GitHub: [@csaszarzoltan](https://github.com/csaszarzoltan)
- Upwork: [Profile](https://www.upwork.com/freelancers/~010b8149572fd46b3d)
- Location: Zurich, Switzerland

---

Star this repo if you find it useful!
