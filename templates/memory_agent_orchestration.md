# Template: Agent Orchestration with Shared Memory

**Purpose:** Give a multi-agent pipeline a team-wide episodic memory so agents
recall prior outcomes before acting and commit their own outcomes after.

**Depends on:** `src/ai_vibe_coding/agent_templates.py` (AgentPipeline,
MessageBus, SharedState), `src/ai_vibe_coding/memory_store.py` (MemoryStore),
`src/ai_vibe_coding/llm_wrapper.py` (LLMClient).

## Pattern

For every agent step:

1. **Recall** — `memory_search(query=<step intent>, limit=3)` before acting;
   inject top hits into the step's input.
2. **Act** — run the agent step as usual.
3. **Commit** — `memory_store(content=<outcome summary>, metadata={"agent":
   <name>, "stage": "plan"|"act"|"verify"})` after the step.

One `MemoryStore` instance is shared by all agents; the SQLite file is the
team's long-term memory and survives restarts.

## Copy-paste example

```python
from ai_vibe_coding import LLMClient, AgentPipeline
from ai_vibe_coding.memory_store import MemoryStore

store = MemoryStore(".memory/team.db")   # shared team memory

def recall(context, intent: str, limit: int = 3) -> str:
    """Fetch relevant memories and format them as prompt context."""
    hits = store.search(intent, limit=limit)
    if not hits["results"]:
        return ""
    lines = [f"- ({h['score']:.2f}) {h['content']}" for h in hits["results"]]
    return "Relevant memories:\n" + "\n".join(lines)

def commit(context, agent: str, stage: str, summary: str) -> None:
    store.store(
        summary,
        metadata={"agent": agent, "stage": stage},
        importance=0.8,               # keep outcomes above eviction floor
    )

def research_step(ctx):
    ctx_mem = recall(ctx, "prior research on this topic")
    prompt = f"{ctx_mem}\n\nResearch the topic: {ctx.steps.get('input', '')}"
    out = LLMClient(provider="openai").chat(prompt)
    commit(ctx, "researcher", "act", f"Research result: {out.content}")
    return out.content

research_step.name = "research"

pipeline = AgentPipeline(agents=[research_step])
result = pipeline.run("Compare DeepSeek vs OpenAI for batch jobs")
print(result.final_output)
```

## Editor-agent variant (MCP)

For Cursor / Claude Desktop, point the memory server at the same DB so editor
agents share memory with the pipeline:

```json
{
  "mcpServers": {
    "ai-vibe-memory": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/ai-vibe-coding-kit/examples/mcp_memory_server.py"],
      "env": {
        "AI_VIBE_MEMORY_DB": "/ABSOLUTE/PATH/TO/PROJECT/.memory/team.db",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Then prompt the editor: "Search memory for what we know about X, then ...".

## Notes

- Keep procedural memories (`importance=1.0`, `metadata={"type": "procedural"}`)
  so eviction never drops team rules.
- TTL short-lived context (e.g. `ttl_seconds=3600` for per-session scratch)
  so stale episodic rows purge themselves.
- `memory_forget` is idempotent — safe to call from error handlers.
