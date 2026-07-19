# Claude Code Workflow Guide

How to use Anthropic's Claude Code CLI for autonomous coding with the ai-vibe-coding-kit.

## Setup

1. Install Claude Code CLI:

```bash
npm install -g @anthropic-ai/claude-code
```

2. Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

3. Install ai-vibe-coding-kit:

```bash
pip install -e ".[dev]"
```

## Using Claude Code with the Kit

### Programmatic Integration

```python
from ai_vibe_coding import LLMClient

# Use Claude for code generation
client = LLMClient(provider="anthropic", model="claude-4-sonnet")
response = client.chat(
    "Write a Python dataclass for a User with validation",
    system_prompt="You are an expert Python developer. Use type hints.",
)
print(response.content)
print(f"Cost: ${response.cost_usd:.4f}")
```

### Streaming Code Review

```python
from ai_vibe_coding import LLMClient

client = LLMClient(provider="anthropic", model="claude-4-sonnet")

code = '''
def process_data(items):
    result = []
    for i in range(len(items)):
        if items[i] > 0:
            result.append(items[i] * 2)
    return result
'''

system = "You are a code reviewer. Identify issues and suggest improvements."

for chunk in client.stream(f"Review this code:\n```python\n{code}\n```", system_prompt=system):
    print(chunk, end="", flush=True)
```

## Daily Workflow

### Planning (Morning)

1. Ask Claude to review yesterday's code:

```python
from ai_vibe_coding import LLMClient

client = LLMClient(provider="anthropic")
response = client.chat(
    "Review these git changes and suggest today's priorities",
    system_prompt="You are a tech lead. Be concise and actionable.",
)
```

2. Generate test stubs for planned features:

```python
from ai_vibe_coding.structured import chat_json, ToolDef
from ai_vibe_coding import LLMClient

client = LLMClient(provider="anthropic")
result = chat_json(
    client,
    "Generate pytest test cases for a User CRUD API endpoint",
    schema={"type": "object", "properties": {"tests": {"type": "array"}}},
)
```

### Development Loop

1. Use Claude Code CLI for interactive coding in terminal
2. Use the kit for batch operations and cost tracking
3. Track all API costs:

```python
from ai_vibe_coding import LLMClient
from ai_vibe_coding.cost_tracker import CostTracker

tracker = CostTracker()
client = LLMClient(provider="anthropic")

for task in daily_tasks:
    response = client.chat(task)
    tracker.record(response)

print(tracker.get_summary().to_table())
```

### Review (Evening)

1. Compare Claude's output with other providers:

```python
from ai_vibe_coding import LLMClient

client = LLMClient(provider="anthropic")
results = client.compare_providers("Refactor this module for better testability: ...")
```

2. Export cost report:

```python
tracker.export_csv("daily_costs.csv")
```

## Best Practices

- Use Claude 4 Sonnet for code generation (good quality, reasonable cost)
- Use Claude 4.5 Sonnet for complex reasoning and architecture decisions
- Always review Claude's suggestions before accepting
- Keep track of costs — Claude is 10x more expensive than DeepSeek
- Use system prompts to enforce consistent coding style
- Stream responses for better UX in interactive tools

## Cost Tips

Claude 4 Sonnet at $0.003/$0.015 per 1K tokens is mid-range. For batch operations:

- Use `claude-3-5-sonnet` instead of `claude-4.5-sonnet` when quality allows
- Set `max_tokens` to avoid over-generation
- Cache repeated prompts to avoid redundant API calls
- Compare with DeepSeek V3 for cost-sensitive tasks
