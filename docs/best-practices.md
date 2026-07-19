# Best Practices

## 1. Choose the Right Provider for the Task

```python
from ai_vibe_coding import LLMClient

# Use GPT-4 for complex reasoning
reasoning_client = LLMClient(provider="openai", model="gpt-4")

# Use DeepSeek for cost-sensitive batch work
batch_client = LLMClient(provider="deepseek", model="deepseek-v3")

# Use MiMo for simple tasks at minimal cost
simple_client = LLMClient(provider="mimo", model="mimo-v2.5")
```

Rule of thumb: match provider capability to task complexity. Don't use GPT-4 for a one-line comment; don't use MiMo for architectural design.

## 2. Always Track Costs

```python
from ai_vibe_coding import LLMClient
from ai_vibe_coding.cost_tracker import CostTracker

tracker = CostTracker()
client = LLMClient(provider="openai")

for prompt in prompts:
    response = client.chat(prompt)
    tracker.record(response)

summary = tracker.get_summary()
if summary.total_cost > 10.0:  # $10 budget
    print(f"WARNING: spent ${summary.total_cost:.2f}")
    print(summary.to_table())
```

Set cost alerts in your application logic to catch runaway spending early.

## 3. Use Streaming for Better UX

```python
from ai_vibe_coding import LLMClient

client = LLMClient(provider="openai")

# Good: user sees text immediately
for chunk in client.stream("Explain how RSA encryption works"):
    print(chunk, end="", flush=True)

# Bad: user waits for the entire response
response = client.chat("Explain how RSA encryption works")
print(response.content)
```

Streaming reduces perceived latency and lets users cancel mid-generation.

## 4. Cache Repeated Prompts

```python
import hashlib
from functools import lru_cache
from ai_vibe_coding import LLMClient

client = LLMClient(provider="openai")

@lru_cache(maxsize=128)
def cached_chat(prompt_hash, prompt):
    return client.chat(prompt)

def smart_chat(prompt):
    h = hashlib.md5(prompt.encode()).hexdigest()
    return cached_chat(h, prompt)
```

For prompts that repeat (e.g., code explanation of unchanged files), caching saves both time and money.

## 5. Use Structured Output for Programmatic Use

```python
from ai_vibe_coding import LLMClient
from ai_vibe_coding.structured import chat_json

client = LLMClient(provider="openai")

# Good: parse JSON directly
result = chat_json(
    client,
    "Extract the function names and their parameters from this code: ...",
    schema={"type": "object", "properties": {"functions": {"type": "array"}}},
)
for func in result["functions"]:
    print(func["name"], func["params"])

# Bad: parse unstructured text
response = client.chat("List the function names and parameters: ...")
# Now you have to regex or NLP-parse the response...
```

## 6. Compare Providers Before Committing

```python
from ai_vibe_coding import LLMClient

client = LLMClient(provider="openai")
results = client.compare_providers("Write a REST API handler for user registration")

for provider, response in results.items():
    if isinstance(response, str):
        print(f"{provider}: FAILED")
        continue
    print(f"\n=== {provider} (${response.cost_usd:.4f}) ===")
    print(response.content[:200])
```

Benchmark quality vs cost before choosing a provider for production.

## 7. Set Reasonable max_tokens

```python
from ai_vibe_coding import LLMClient

client = LLMClient(provider="openai")

# Good: limit output for simple tasks
response = client.chat("Summarize this in 2 sentences", max_tokens=200)

# Bad: no limit (can generate 4K+ tokens, costing more)
response = client.chat("Summarize this in 2 sentences")
```

## 8. Use System Prompts for Consistent Behavior

```python
from ai_vibe_coding import LLMClient

client = LLMClient(provider="openai")

system = (
    "You are a Python code reviewer. "
    "Always respond with: 1) Issues found, 2) Suggested fixes, 3) Severity rating. "
    "Be concise."
)

response = client.chat(
    "Review this function: def foo(x): return x*2",
    system_prompt=system,
)
```

## 9. Handle Errors Gracefully

```python
from ai_vibe_coding import LLMClient
from ai_vibe_coding.structured import chat_json, LLMJSONError

client = LLMClient(provider="openai")

try:
    result = chat_json(client, "Return invalid JSON on purpose")
except LLMJSONError as e:
    print(f"JSON parse failed: {e}")
    print(f"Raw response: {e.raw_response}")
    # Fallback: use as plain text
    response = client.chat("Return the data as plain text")
```

## 10. Use Tool Calling for Agentic Workflows

```python
from ai_vibe_coding import LLMClient
from ai_vibe_coding.structured import chat_with_tools, ToolDef

client = LLMClient(provider="openai")

tools = [
    ToolDef(
        name="get_user",
        description="Get user by ID",
        parameters={"type": "object", "properties": {"user_id": {"type": "integer"}}},
    ),
    ToolDef(
        name="list_orders",
        description="List orders for a user",
        parameters={"type": "object", "properties": {"user_id": {"type": "integer"}}},
    ),
]

result = chat_with_tools(client, "Get user 42 and their orders", tools)

# Dispatch to the actual function
if result.tool_name == "get_user":
    user = get_user(**result.arguments)
elif result.tool_name == "list_orders":
    orders = list_orders(**result.arguments)
```

## 11. Export Cost Data for Analysis

```python
from ai_vibe_coding.cost_tracker import CostTracker

tracker = CostTracker()
# ... record calls ...

# CSV for Excel/pandas
tracker.export_csv("monthly_costs.csv")

# JSON for programmatic analysis
tracker.export_json("monthly_costs.json")

# Print summary table
print(tracker.get_summary().to_table())
```

## 12. Batch Async Calls for Throughput

```python
import asyncio
from ai_vibe_coding import LLMClient

async def batch_process(prompts):
    client = LLMClient(provider="openai")
    tasks = [client.chat_async(p) for p in prompts]
    return await asyncio.gather(*tasks)

results = asyncio.run(batch_process(prompts))
```

Async calls run concurrently, reducing total wall time for batch workloads.
