# Template: Cost-Tracked Agents with Spend Memory

**Purpose:** Record every agent run's cost to memory so agents can recall past
spend before deciding whether to continue, and you get a durable spend history
in the same SQLite-backed pattern as the cost store.

**Depends on:** `src/ai_vibe_coding/cost_tracker.py` (CostTracker,
CostSummary), `src/ai_vibe_coding/memory_store.py` (MemoryStore),
`src/ai_vibe_coding/llm_wrapper.py` (LLMClient, LLMResponse).

## Pattern

1. Per LLM call: `tracker.record(response)`.
2. After the run: `memory_store(f"Session {session_id} cost $..., ... tokens",
   metadata={"type": "cost", "session_id": ..., "cost_usd": ...})`.
3. Before expensive runs: `memory_search("cost")` to recall past spend and
   decide whether to continue.

Cost and memory DBs are separate files by default (`SqliteCostStore` pattern
for cost; `~/.ai_vibe_coding/memory.db` for memory).

## Copy-paste example

```python
from ai_vibe_coding import LLMClient
from ai_vibe_coding.cost_tracker import CostTracker
from ai_vibe_coding.memory_store import MemoryStore
from datetime import UTC, datetime

tracker = CostTracker()
store = MemoryStore(".memory/costs.db")
client = LLMClient(provider="openai")

session_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")

# LLM calls
response = client.chat("Summarize the pricing options")
tracker.record(response)
response2 = client.chat("Now draft the recommendation")
tracker.record(response2)

summary = tracker.get_summary()
store.store(
    f"Session {session_id} cost ${summary.total_cost:.4f}, "
    f"{summary.total_tokens} tokens, {summary.call_count} calls",
    metadata={
        "type": "cost",
        "session_id": session_id,
        "cost_usd": summary.total_cost,
        "tokens": summary.total_tokens,
    },
)

# Recall past spend before starting an expensive job
recent = store.search("cost", limit=5)
for hit in recent["results"]:
    print(f"${hit['metadata'].get('cost_usd', 0):.4f} — {hit['content']}")
```

## Notes

- `CostSummary.to_dict()` exposes `total_cost`, `total_tokens`, `per_provider`,
  `per_model`, `call_count` — store the whole dict in `metadata` if you want
  breakdowns searchable.
- Query by type: `memory_search("cost session")` plus filter on
  `metadata["type"] == "cost"` client-side.
- Set `importance=0.9` on cost rows so budget history survives eviction.
