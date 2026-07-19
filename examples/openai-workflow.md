# OpenAI Workflow Guide

How to use OpenAI GPT models with the ai-vibe-coding-kit for development workflows.

## Setup

1. Set your OpenAI API key:

```bash
export OPENAI_API_KEY="sk-..."
```

2. Install the kit:

```bash
pip install -e ".[dev]"
```

## Model Selection

| Model | Best For | Cost (per 1K tokens) |
|-------|----------|----------------------|
| gpt-4 | Complex reasoning, production code | $0.03 in / $0.06 out |
| gpt-4-turbo | Fast coding, good quality | $0.01 in / $0.03 out |
| gpt-4.5 | Advanced reasoning | $0.05 in / $0.15 out |
| gpt-5 | Best quality, highest cost | $0.08 in / $0.24 out |

```python
from ai_vibe_coding import LLMClient

# Fast day-to-day coding
fast = LLMClient(provider="openai", model="gpt-4-turbo")

# Complex architectural decisions
smart = LLMClient(provider="openai", model="gpt-5")
```

## Common Patterns

### Code Generation

```python
from ai_vibe_coding import LLMClient

client = LLMClient(provider="openai", model="gpt-4-turbo")

response = client.chat(
    "Write a Python async function that fetches data from an API with retry logic",
    system_prompt="Use httpx, type hints, and docstrings. Include error handling.",
)
print(response.content)
```

### Code Review

```python
from ai_vibe_coding import LLMClient

client = LLMClient(provider="openai")

code = open("src/myapp/handlers.py").read()
response = client.chat(
    f"Review this code for bugs, security issues, and improvements:\n\n{code}",
    system_prompt="You are a senior Python developer. List issues with severity.",
)
print(response.content)
print(f"Review cost: ${response.cost_usd:.4f}")
```

### Test Generation

```python
from ai_vibe_coding import LLMClient
from ai_vibe_coding.structured import chat_json

client = LLMClient(provider="openai", model="gpt-4-turbo")

source_code = "def add(a, b): return a + b"
result = chat_json(
    client,
    f"Generate pytest test cases for this function:\n```python\n{source_code}\n```",
    schema={
        "type": "object",
        "properties": {
            "test_code": {"type": "string"},
            "test_cases": {"type": "array"},
        },
    },
)
print(result["test_code"])
```

### Documentation Generation

```python
from ai_vibe_coding import LLMClient

client = LLMClient(provider="openai", model="gpt-4-turbo")

code = open("src/myapp/models.py").read()
response = client.chat(
    f"Write Google-style docstrings for all functions:\n\n{code}",
    system_prompt="Output only the documented code, no explanations.",
)
# Save the documented version
open("src/myapp/models_documented.py", "w").write(response.content)
```

### Tool Calling for Agentic Workflows

```python
from ai_vibe_coding import LLMClient
from ai_vibe_coding.structured import chat_with_tools, ToolDef

client = LLMClient(provider="openai")

tools = [
    ToolDef(
        name="read_file",
        description="Read a file from the repository",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    ),
    ToolDef(
        name="write_file",
        description="Write content to a file",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    ),
]

result = chat_with_tools(
    client,
    "Read the file src/utils.py and add a logging decorator",
    tools,
)
# result.tool_name -> "read_file" or "write_file"
# result.arguments -> {"path": "src/utils.py", ...}
```

## Streaming for Interactive UX

```python
from ai_vibe_coding import LLMClient

client = LLMClient(provider="openai")

print("Explanation: ", end="")
for chunk in client.stream("Explain how Python's GIL works"):
    print(chunk, end="", flush=True)
print()
```

## Cost Tracking for a Development Session

```python
from ai_vibe_coding import LLMClient
from ai_vibe_coding.cost_tracker import CostTracker

tracker = CostTracker()
client = LLMClient(provider="openai", model="gpt-4-turbo")

# Simulate a coding session
tasks = [
    ("Generate a REST handler for /users", "You are a Python developer using FastAPI."),
    ("Add input validation to the handler", "Use pydantic for validation."),
    ("Write tests for the handler", "Use pytest and httpx.AsyncClient."),
    ("Add docstrings", "Use Google style docstrings."),
]

for prompt, system in tasks:
    response = client.chat(prompt, system_prompt=system)
    tracker.record(response)
    print(f"Done: {prompt[:40]}... (${response.cost_usd:.4f})")

print("\n" + tracker.get_summary().to_table())
```

## Integration with OpenAI-Compatible APIs

DeepSeek and other providers use the OpenAI-compatible API format:

```python
from ai_vibe_coding import LLMClient

# DeepSeek via OpenAI-compatible API
deepseek = LLMClient(provider="deepseek", model="deepseek-v3")
response = deepseek.chat("Write a binary search function")
```

## Best Practices

- Use `gpt-4-turbo` for most coding tasks (best speed/cost/quality balance)
- Reserve `gpt-5` for complex architectural decisions
- Set `max_tokens` to control output length and cost
- Use system prompts for consistent code style
- Track costs with `CostTracker` for budget monitoring
- Stream responses for interactive applications
- Use structured output when you need to parse the response programmatically
