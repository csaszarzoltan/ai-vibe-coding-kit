# Template: Prompt Chaining with Memory Injection

**Purpose:** Inject relevant memories between chain steps so each step starts
with prior context, and log each step's outcome back to memory.

**Depends on:** `src/ai_vibe_coding/chain_templates.py` (SequentialChain,
ChainContext, ChainResult), `src/ai_vibe_coding/memory_store.py`
(MemoryStore), `src/ai_vibe_coding/llm_wrapper.py` (LLMClient).

## Pattern

Before step N: `memory_search(step_N_intent, limit=3)` and prepend the top hits
to the step prompt as `"Relevant memories:\n- ..."`.
After step N: `memory_store(chain_id + step summary, metadata={"chain":
<chain_id>, "step": <n>})`.

## Copy-paste example

```python
from ai_vibe_coding import LLMClient, SequentialChain
from ai_vibe_coding.memory_store import MemoryStore

store = MemoryStore(".memory/chains.db")
client = LLMClient(provider="openai")

def with_memory(intent: str) -> str:
    hits = store.search(intent, limit=3)
    if not hits["results"]:
        return ""
    return "Relevant memories:\n" + "\n".join(
        f"- ({h['score']:.2f}) {h['content']}" for h in hits["results"]
    )

def research_step(ctx):
    mem = with_memory("prior research on topic")
    return client.chat(
        f"{mem}\n\nResearch: {ctx.steps.get('input', '')}"
    ).content

def write_step(ctx):
    mem = with_memory("writing style and past conclusions")
    return client.chat(
        f"{mem}\n\nBased on this research write the report:\n{ctx.steps['research']}"
    ).content

research_step.name = "research"
write_step.name = "write"

chain = SequentialChain(steps=[research_step, write_step])
result = chain.run("DeepSeek vs OpenAI for batch jobs")

# Commit each step's outcome back to memory
for step in result.steps:
    store.store(
        f"Step '{step.name}': {step.output[:200]}",
        metadata={"chain": "report", "step": step.name},
    )
print(result.total_cost_usd, result.status)
```

## Notes

- Keep `limit` small (3–5) — memory is context, not the whole history.
- Set `min_score` (e.g. 0.3) to skip irrelevant hits when the store is noisy.
- Store full outcomes with a content prefix (`chain:report`) so
  `memory_search("report")` finds whole chains in one query.
