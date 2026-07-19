# Model Comparison & Pricing

Last updated: 2026-07-19. Prices are per 1K tokens. Verify at official provider pages before production use.

## Pricing Table

### OpenAI

| Model | Input (per 1K) | Output (per 1K) | Context Window |
|-------|----------------|-----------------|----------------|
| gpt-4 | $0.03 | $0.06 | 8K |
| gpt-4-turbo | $0.01 | $0.03 | 128K |
| gpt-4.5 | $0.05 | $0.15 | 128K |
| gpt-5 | $0.08 | $0.24 | 128K |

### Anthropic

| Model | Input (per 1K) | Output (per 1K) | Context Window |
|-------|----------------|-----------------|----------------|
| claude-3-5-sonnet | $0.003 | $0.015 | 200K |
| claude-4-sonnet | $0.003 | $0.015 | 200K |
| claude-4.5-sonnet | $0.005 | $0.025 | 200K |

### DeepSeek

| Model | Input (per 1K) | Output (per 1K) | Context Window |
|-------|----------------|-----------------|----------------|
| deepseek-v3 | $0.0014 | $0.0028 | 64K |
| deepseek-r1 | $0.0014 | $0.0028 | 64K |

### OpenRouter

| Model | Input (per 1K) | Output (per 1K) | Notes |
|-------|----------------|-----------------|-------|
| (default) | $0.01 | $0.03 | Varies by routed model |

### Xiaomi MiMo

| Model | Input (per 1K) | Output (per 1K) | Context Window |
|-------|----------------|-----------------|----------------|
| mimo-v2.5 | $0.0004 | $0.002 | 1M |

## Cost Comparison by Task

Estimated costs for common coding tasks (token estimates are approximate):

| Task | Est. Tokens | OpenAI GPT-4 | Claude 4 Sonnet | DeepSeek V3 | MiMo V2.5 |
|------|-------------|--------------|-----------------|-------------|-----------|
| Simple question | 500 in + 200 out | $0.027 | $0.003 | $0.0013 | $0.0006 |
| Write a function | 1K in + 500 out | $0.06 | $0.0105 | $0.0028 | $0.0014 |
| Code review (500 LOC) | 5K in + 1K out | $0.21 | $0.030 | $0.0098 | $0.004 |
| Refactor a module | 10K in + 3K out | $0.48 | $0.060 | $0.021 | $0.010 |
| Generate test suite | 3K in + 2K out | $0.20 | $0.039 | $0.0098 | $0.0052 |

## Provider Recommendations

### By Use Case

| Use Case | Recommended Provider | Rationale |
|----------|---------------------|-----------|
| Production quality code | OpenAI GPT-4 or Claude 4 Sonnet | Best code generation quality |
| Cost-sensitive batch jobs | DeepSeek V3 or MiMo V2.5 | 10-50x cheaper than GPT-4 |
| Long context (>64K tokens) | Anthropic Claude 4 | 200K context window |
| Rapid prototyping | DeepSeek V3 | Fast and affordable |
| Streaming chat UX | OpenAI GPT-4 Turbo | Low latency, good streaming |
| Tool calling / agents | OpenAI GPT-4 | Most reliable function calling |

### By Budget Tier

| Tier | Provider | Cost per 1K calls (est.) |
|------|----------|--------------------------|
| Enterprise ($100+/day) | OpenAI GPT-4 | $200-500 |
| Mid-range ($10-50/day) | Claude 4 Sonnet | $30-100 |
| Budget ($1-10/day) | DeepSeek V3 | $2-10 |
| Minimal (<$1/day) | MiMo V2.5 | $0.50-2 |

## Updating Pricing

Pricing is stored in `src/ai_vibe_coding/llm_wrapper.py` in the `PRICING` dict:

```python
PRICING = {
    "openai": {
        "gpt-4": {"input": 0.03, "output": 0.06},
        # ... add new models here
    },
    # ... add new providers here
}
```

When a provider changes pricing:

1. Update the `PRICING` dict
2. Run `pytest tests/` to verify cost calculations still pass
3. Bump the version in `pyproject.toml`
4. Add a changelog entry

## Context Window Comparison

```
MiMo V2.5     ████████████████████████████████████████████████ 1M
Claude 4      ██████████████████████                            200K
GPT-4 Turbo   █████████████                                    128K
GPT-4.5/5     █████████████                                    128K
DeepSeek V3   ██████                                           64K
GPT-4         █                                                 8K
```

## Quality vs Cost Tradeoff

```
Quality
  ▲
  │  GPT-4 ─── Claude 4 Sonnet
  │                │
  │          Claude 3.5
  │                    │
  │              DeepSeek V3
  │                        │
  │                  MiMo V2.5
  │
  └──────────────────────────────────► Cost
```

For most coding tasks, DeepSeek V3 offers the best quality-per-dollar ratio. MiMo V2.5 is cheapest but may struggle with complex reasoning.
