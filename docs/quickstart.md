# Quick Start Guide

## Prerequisites

- Python 3.11 or higher
- pip or uv
- Git

## Installation

```bash
git clone https://github.com/csaszarzoltan/ai-vibe-coding-kit.git
cd ai-vibe-coding-kit
pip install -e ".[dev]"
```

This installs the package in editable mode with all development dependencies (pytest, ruff, etc.).

## API Keys

Set environment variables for the providers you want to use:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export DEEPSEEK_API_KEY="sk-..."
export OPENROUTER_API_KEY="sk-or-..."
export MIMO_API_KEY="..."
```

Or create a `.env` file:

```bash
cat > .env << 'EOF'
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=sk-...
EOF
```

You only need keys for providers you actually use. Tests run without any API keys (all HTTP is mocked).

## Your First LLM Call

```python
from ai_vibe_coding import LLMClient

client = LLMClient(provider="openai")
response = client.chat("What is 2 + 2?")

print(f"Content:  {response.content}")
print(f"Cost:     ${response.cost_usd:.4f}")
print(f"Tokens:   {response.tokens_used}")
print(f"Latency:  {response.latency_ms:.0f}ms")
```

## Switching Providers

```python
from ai_vibe_coding import LLMClient

# OpenAI GPT-4
openai = LLMClient(provider="openai")
r1 = openai.chat("Write a haiku about Python")

# Anthropic Claude 4
anthropic = LLMClient(provider="anthropic")
r2 = anthropic.chat("Write a haiku about Python")

# DeepSeek V3 (cheapest)
deepseek = LLMClient(provider="deepseek")
r3 = deepseek.chat("Write a haiku about Python")

for name, r in [("OpenAI", r1), ("Anthropic", r2), ("DeepSeek", r3)]:
    print(f"{name}: {r.content} (${r.cost_usd:.4f})")
```

## Streaming Responses

```python
from ai_vibe_coding import LLMClient

client = LLMClient(provider="openai")
for chunk in client.stream("Explain how HTTP works, step by step"):
    print(chunk, end="", flush=True)
print()  # newline at end
```

## Comparing Providers

Run the same prompt across all configured providers and compare cost and quality:

```python
from ai_vibe_coding import LLMClient

client = LLMClient(provider="openai")
results = client.compare_providers("Write a function to reverse a linked list")

for provider, response in results.items():
    if isinstance(response, str):
        print(f"{provider}: ERROR — {response}")
    else:
        print(f"{provider}: {response.content[:80]}...")
        print(f"  cost=${response.cost_usd:.4f} tokens={response.tokens_used}")
```

## Structured JSON Output

```python
from ai_vibe_coding import LLMClient
from ai_vibe_coding.structured import chat_json

client = LLMClient(provider="openai")
result = chat_json(
    client,
    "List 3 Python web frameworks with their main features",
    schema={
        "type": "object",
        "properties": {
            "frameworks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "features": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
    },
)
# result is a parsed dict
for fw in result["frameworks"]:
    print(f"{fw['name']}: {', '.join(fw['features'])}")
```

## Tool Calling

```python
from ai_vibe_coding import LLMClient
from ai_vibe_coding.structured import chat_with_tools, ToolDef

client = LLMClient(provider="openai")

tools = [
    ToolDef(
        name="search_docs",
        description="Search documentation for a query",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    ),
]

result = chat_with_tools(client, "Search docs for 'async programming'", tools)
print(f"Tool: {result.tool_name}")     # "search_docs"
print(f"Args: {result.arguments}")     # {"query": "async programming", "limit": ...}
```

## Cost Tracking

```python
from ai_vibe_coding import LLMClient
from ai_vibe_coding.cost_tracker import CostTracker

tracker = CostTracker()
client = LLMClient(provider="openai")

prompts = [
    "Explain Python decorators",
    "Write a fibonacci function",
    "What is async/await?",
]

for prompt in prompts:
    response = client.chat(prompt)
    tracker.record(response)

# Print ASCII summary table
summary = tracker.get_summary()
print(summary.to_table())

# Export for analysis
tracker.export_csv("costs.csv")
tracker.export_json("costs.json")
```

Example output:

```
==================================================
Cost Summary
==================================================
  Total Cost:   $0.0234
  Total Tokens: 3420
  Call Count:   3
--------------------------------------------------
  Per-Provider:
    openai               $0.0234
--------------------------------------------------
  Per-Model:
    gpt-4                $0.0234
==================================================
```

## Running Tests

```bash
# All tests (no API keys needed)
pytest tests/ -v

# Specific module
pytest tests/test_llm_wrapper.py -v

# Lint
ruff check src/ tests/
```

## Next Steps

- Read the [API Reference](api-reference.md) for detailed documentation
- See [Model Comparison](model-comparison.md) for provider pricing and recommendations
- Check [Best Practices](best-practices.md) for cost optimization tips
- Browse the [examples](../examples/) directory for more workflows
