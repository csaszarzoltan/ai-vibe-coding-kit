# Agent Memory Guide

Module: `src/ai_vibe_coding/memory_store.py` + `src/ai_vibe_coding/memory_embedding.py` + `src/ai_vibe_coding/memory_compaction.py`  
MCP server: `examples/mcp_memory_server.py`  
Cross-session demo: `examples/memory_client_example.py`  
Compaction demo: `examples/compaction_client_example.py`  
Integration templates: `templates/memory_agent_orchestration.md`, `templates/memory_prompt_chaining.md`, `templates/memory_cost_tracked_agent.md`

## Overview

The **MCP Agent Memory Server** gives AI editors and agent pipelines persistent,
semantic memory. Agents can `store` memories, `retrieve` them by id, `search`
them semantically (real cosine similarity over real embeddings — never a mock),
`forget` them, and inspect `stats`. Memories survive restarts (SQLite file),
expire via TTL, are evicted by an importance × recency score when a row
budget is exceeded, and — since v0.14.0 — can be **compacted**: stale
low-importance memories are distilled into summaries, near-duplicates are
merged, and importance decays over time, so the store keeps its signal
without growing unbounded.

No API keys required. The server follows the repo's existing
`examples/standalone_mcp_server.py` pattern: a `FastMCP` instance with
`@mcp.tool()`-decorated, importable, plain-Python functions, run over stdio.
Core logic lives in `src/ai_vibe_coding/` so templates and the client example
can reuse it programmatically.

## Memory types: episodic vs semantic vs procedural

Agent memory is commonly split into three kinds. The kit's memory server covers
the first two directly; the third is a design pattern you apply on top.

| Type | What it stores | Example | How the kit supports it |
|------|----------------|---------|-------------------------|
| **Episodic** | What happened — events, sessions, outcomes with timestamps | "On 2026-08-03 the pricing agent compared OpenAI vs DeepSeek; OpenAI won by 12% on cost" | `memory_store` with `metadata={"type": "episodic", ...}`, `created_at` / `last_accessed_at` timestamps, TTL for short-lived facts |
| **Semantic** | What is known — facts, concepts, relationships | "DeepSeek-V3 is the cheapest provider per 1M output tokens" | `memory_search` with real cosine similarity over `all-MiniLM-L6-v2` embeddings |
| **Procedural** | How to do something — workflows, recipes, learned preferences | "When comparing providers, always include latency in the report" | Not stored by the server; encode as a persistent `metadata={"type": "procedural"}` memory and inject it into prompts before each run (see the orchestration template) |

Rule of thumb: use episodic for "what happened in run X", semantic for
"facts to search across everything ever stored", and treat procedural memories
as high-`importance` rows (e.g. `importance=1.0`) so eviction never drops the
rules your agents rely on.

## Memory lifecycle: write → retrieve → forget

A memory moves through three states, plus two background mechanisms that keep
the store bounded:

```
         ┌────────────┐   store()    ┌──────────────┐
         │  write     │ ───────────► │   stored     │
         └────────────┘              └──────┬───────┘
                                            │
              ┌─────────────────────────────┼──────────────────────┐
              │                             │                      │
       retrieve(id)                  search(query)            forget(id)
              │                             │                      │
              ▼                             ▼                      ▼
      ┌──────────────┐            ┌──────────────┐        ┌──────────────┐
      │  active row  │            │  ranked hits │        │  deleted     │
      └──────────────┘            └──────────────┘        └──────────────┘

   TTL expiry (time-based)     Importance × recency eviction (budget-based)
   rows with ttl_seconds       when total > max_rows, the lowest-scoring
   past their age are purged   rows are deleted until total == max_rows

   Compaction (v0.14.0, on demand)     Importance decay (v0.14.0, on demand)
   stale low-importance clusters       rarely-accessed rows lose importance
   are distilled + originals are       per half-life curve and become
   archived (never deleted)            compaction-eligible
```

- **Write** — `memory_store(content, metadata, ttl_seconds, importance)` embeds
  the content (or hashes it in fallback mode) and inserts a row. Returns the
  new `id`.
- **Retrieve** — `memory_retrieve(id)` returns a stored memory by id and
  touches `last_accessed_at`. Retrieving an expired id purges the row and
  raises `MemoryNotFoundError`.
- **Forget** — `memory_forget(id)` is **idempotent**: forgetting a missing id
  returns `{"forgotten": false}` instead of raising. Agent-friendly.
- **Expire** — TTL purge runs at the start of every `store()` and `search()`.
  A memory is expired iff `ttl_seconds IS NOT NULL` and
  `(now - created_at).total_seconds() >= ttl_seconds`. Expired rows are
  physically deleted and counted in `stats()["expired"]`.
- **Evict** — only inside `store()`, only when `total > max_rows`. The lowest
  `eviction_score = importance * exp(-age_seconds / 604800.0)` rows are
  deleted until the store is back at budget (7-day half-life recency boost).
  Ties break by older `created_at`, then lexicographically smaller `id`.

## Vector vs graph store tradeoffs

| Aspect | Vector store (this kit) | Graph store (e.g. Neo4j, Memgraph) |
|--------|------------------------|------------------------------------|
| **Query** | Semantic similarity ("find memories like this") | Explicit relationships ("what is connected to X") |
| **Strength** | Fuzzy recall, synonyms, paraphrase matching | Multi-hop traversal, path queries, dedup/consolidation |
| **Weakness** | No structure; similar ≠ related | Requires defined schema and edges; no fuzzy matching |
| **Write cost** | Embed once per row | Nodes + edges per write |
| **Scale** | Linear scan over ≤10k rows is fine (this kit) | Grows with graph density |
| **Ops burden** | Zero — SQLite file | A server to run, backup, and secure |
| **Good for** | Agent episodic/semantic recall | Knowledge graphs, entity resolution, lineage |

The kit deliberately ships a **vector-style store on SQLite** (no separate
vector index — `sqlite-vec`/FAISS are out of scope) because the row budget
(default 10,000) is small enough that a linear scan with real cosine
similarity is fast and operationally trivial: one file, WAL mode, no service
to run.

## Self-hosted memory options compared

If you outgrow the kit's built-in store, the common self-hosted options are:

| Option | Stack | Strengths | Considerations |
|--------|-------|-----------|----------------|
| **Mem0** | Python SDK, pluggable vector DBs (Qdrant, pgvector, Chroma, etc.) | Purpose-built for LLM agent memory; automatic dedup/consolidation; extraction of facts from conversations | Python service / DB to host; heavier dependency tree; API surface aimed at chat-memory use cases |
| **Letta** (formerly MemGPT) | Self-hosted agent memory server (FastAPI + Postgres) | Memory as a first-class agent concept; archival/recall tiers; REST + ADE (Agent Development Environment) | Postgres required; opinionated runtime; larger operational footprint |
| **Zep** | Temporal knowledge graph + vector search over conversations | Combines graph + vector; session-scoped memory; SDKs for Python/JS | Two components (graph + vector) to run; oriented at chat-session history rather than raw fact storage |
| **Cognee** | Python, ECL (Extract-Consolidate-Load) pipelines, graph + vector | Strong entity/relationship extraction into a knowledge graph; research-oriented | Heavier compute during ingestion; graph-centric (see tradeoffs above) |

The kit's server is the **zero-dependency default**: a SQLite file you can
`rsync`, back up, or delete. Reach for Mem0/Letta/Zep/Cognee when you need
dedup + consolidation (Mem0), an agent runtime (Letta), temporal conversation
graphs (Zep), or entity extraction (Cognee).

## MCP memory protocol

The server exposes six tools over the standard MCP stdio transport
(JSON-RPC 2.0, newline-delimited). Any MCP-compatible client (Cursor, Claude
Desktop, Windsurf, `mcp` SDK `ClientSession`) works unmodified.

| Tool | Signature | Returns |
|------|-----------|---------|
| `memory_store` | `(content: str, metadata?: dict, ttl_seconds?: int, importance?: float = 0.5) -> dict` | `{"id", "stored": true, "embedding_source", "created_at"}` |
| `memory_retrieve` | `(memory_id: str) -> dict` | `{"id", "content", "metadata", "created_at", "last_accessed_at", "ttl_seconds", "importance", "embedding_source"}` |
| `memory_search` | `(query: str, limit?: int = 5, min_score?: float = 0.0) -> dict` | `{"query", "limit", "total", "results": [{id, content, metadata, score, importance, created_at, last_accessed_at, ttl_seconds}]}` |
| `memory_forget` | `(memory_id: str) -> dict` | `{"id", "forgotten": bool}` — idempotent |
| `memory_stats` | `() -> dict` | `{"total", "expired", "evicted", "db_path", "max_rows", "embedding_mode"}` — the MCP tool returns the base stats; the extended compaction counters (below) are available via `MemoryStore.memory_stats()` or the `ai-vibe-bench memory stats` CLI |
| `memory_compact` | `(mode?: str = "dry-run", age_days?: float, importance_threshold?: float, merge_threshold?: float) -> dict` | plan or apply result — see [Memory Compaction & Knowledge Distillation](#memory-compaction--knowledge-distillation) |

Semantics that matter for prompt engineering:

- `search` scores are **real cosine similarity** (rounded to 6 dp), sorted by
  `score DESC, importance DESC, created_at DESC`. Rows below `min_score` are
  excluded. `limit` is clamped to `[1, 50]`.
- `metadata` must be a JSON-serializable dict; it comes back parsed, so you
  can filter on it client-side (e.g. `metadata.get("agent") == "researcher"`).
- Embedding mode is **pinned per database**: the first embed decides
  `sentence-transformers` (384-dim, semantic) vs `hash-fallback` (256-dim,
  lexical). A mode/dimension mismatch on later writes raises `ValueError`
  instead of silently corrupting similarity.
- Errors: `MemoryNotFoundError` (missing/expired id on retrieve) and
  `ValueError` (invalid args) propagate as JSON-RPC errors.

## How to run and use the memory server

### 1. Install

The server needs the repo's venv (or any env with `mcp` + the project deps):

```bash
cd ai-vibe-coding-kit
pip install -e ".[dev]"          # installs mcp + sentence-transformers
```

### 2. Run the server

```bash
cd ai-vibe-coding-kit
python examples/mcp_memory_server.py
```

The server listens on stdin/stdout (stdio transport). It prints nothing to the
terminal — MCP clients communicate over the process's standard streams.
Press Ctrl+C to stop.

Override the database location or row budget per run:

```bash
AI_VIBE_MEMORY_DB=/tmp/team-memory.db AI_VIBE_MEMORY_MAX_ROWS=5000 \
    python examples/mcp_memory_server.py
# or
python examples/mcp_memory_server.py --db /tmp/team-memory.db --max-rows 5000
```

Precedence: **CLI flag > env var > default** (`~/.ai_vibe_coding/memory.db`,
`10000` rows).

> **Verify the server is alive** from another terminal by calling the tools
> directly (they are importable plain functions — no MCP client needed):
> ```bash
> python -c "
> import sys; sys.path.insert(0, '.')
> from examples.mcp_memory_server import memory_store, memory_search
> r = memory_store('vector databases index embeddings', metadata={'topic': 'sqlite'})
> print(r['id'])
> print(memory_search('embedding storage'))
> "
> ```

For an interactive test UI: `mcp dev examples/mcp_memory_server.py` opens the
MCP Inspector at `http://localhost:5173` where you can call each tool and
inspect its schema.

### 3. Configure Cursor

Add `.cursor/mcp.json` to your project root:

```json
{
  "mcpServers": {
    "ai-vibe-memory": {
      "command": "python",
      "args": ["${workspaceFolder}/examples/mcp_memory_server.py"],
      "env": {
        "AI_VIBE_MEMORY_DB": "${workspaceFolder}/.memory/team.db",
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
    "ai-vibe-memory": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/ai-vibe-coding-kit/examples/mcp_memory_server.py"],
      "env": {
        "AI_VIBE_MEMORY_DB": "/ABSOLUTE/PATH/TO/ai-vibe-coding-kit/.memory/team.db",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Replace the paths with your actual repo path. Restart Claude Desktop — a
hammer icon appears in the input area when tools are connected.

### 5. Use it from an editor prompt

- **Store a fact** — "Remember that the team prefers DeepSeek for batch jobs"
- **Recall semantically** — "What do we know about cost-efficient providers?"
- **Forget** — "Forget the memory about the deprecated endpoint"
- **Inspect** — "How many memories are stored, and how many were evicted?"

## Programmatic API (no MCP client needed)

The store is importable directly; the MCP server is a thin shell over it.

```python
from ai_vibe_coding.memory_store import MemoryStore, MemoryNotFoundError

store = MemoryStore("/tmp/demo-memory.db")   # or ":memory:"

r = store.store(
    "OpenAI vs DeepSeek comparison on 2026-08-03: DeepSeek won on cost",
    metadata={"type": "episodic", "session_id": "s-42"},
    importance=0.9,
)
print(r)      # {"id": "...", "stored": True, "embedding_source": "...", "created_at": "..."}

row = store.retrieve(r["id"])
print(row["content"])

hits = store.search("cheapest provider", limit=3, min_score=0.3)
for hit in hits["results"]:
    print(hit["score"], hit["content"])

print(store.forget(r["id"]))   # {"id": "...", "forgotten": True}
print(store.forget(r["id"]))   # {"id": "...", "forgotten": False}  (idempotent)

try:
    store.retrieve(r["id"])
except MemoryNotFoundError:
    print("gone")

print(store.stats())
```

### Config reference

| Setting | Env var | CLI flag | Default |
|---------|---------|----------|---------|
| SQLite DB path | `AI_VIBE_MEMORY_DB` | `--db` | `~/.ai_vibe_coding/memory.db` |
| Row budget | `AI_VIBE_MEMORY_MAX_ROWS` | `--max-rows` | `10000` |

`MemoryStore` constructor args override all (programmatic use). For tests,
inject a clock via `MemoryStore(..., now=<zero-arg callable>)` — TTL behavior
becomes deterministic without sleeping.

## Cross-session persistence demo

```bash
cd ai-vibe-coding-kit
python examples/memory_client_example.py --db /tmp/cross-session.db
```

The demo stores memories in **session 1**, closes the store, then opens a new
`MemoryStore` on the same path in **session 2** and proves the data survived:
retrieve by id, search again, forget one id, and print `memory_stats()`. No
network and no API key required — if sentence-transformers is unavailable it
runs in hash-fallback mode.

## Eviction worked example

With `max_rows=2`, storing three rows with `importance` 0.1, 0.5, 1.0 and
equal access times evicts the 0.1 row:

```python
from ai_vibe_coding.memory_store import MemoryStore

store = MemoryStore(":memory:", max_rows=2)
store.store("low value fact", importance=0.1)
store.store("medium value fact", importance=0.5)
store.store("high value fact", importance=1.0)
s = store.stats()
assert s["total"] == 2 and s["evicted"] == 1   # the 0.1 row is gone
store.close()
```

## Memory Compaction & Knowledge Distillation

*Added in v0.14.0. Engine: `src/ai_vibe_coding/memory_compaction.py` (pure,
deterministic functions); orchestration: `MemoryStore.compact` /
`MemoryStore.impact_decay`; CLI: `ai-vibe-bench memory`; MCP tool:
`memory_compact`.*

Agent memory grows forever if nothing prunes it. Hard eviction (the
importance × recency budget in `MemoryStore`) deletes old facts wholesale,
losing signal. Compaction instead **distills**: stale low-importance clusters
are summarized into a single distilled entry and the originals are marked
`archived` (never deleted — provenance is preserved), and near-duplicate
memories are merged. Combined with time-based importance decay, the store
stays bounded while retrieval keeps the *signal*.

### How it works

Three mechanisms run on demand (there is no background scheduler — call them
from cron, from the MCP client, or from your agent loop):

1. **Distill** — active memories older than `compaction_age_days` (default
   **30**) with `importance < compaction_importance_threshold` (default
   **0.3**) are grouped into clusters by embedding cosine similarity
   (≥ `merge_threshold`). Each cluster becomes one **distilled** entry: a
   deterministic, deduplicated summary with a provenance header
   (`Distilled from N source(s)`, date range) and `metadata.source_ids` —
   no LLM call, fully reproducible. The originals are set to `archived`.
2. **Merge** — active memories with cosine similarity ≥ `merge_threshold`
   (default **0.82**, the same `all-MiniLM-L6-v2` embeddings used for
   search) are merged into one entry: the **newest** is kept and its content
   extended with the older duplicates (`\n---\n` separator,
   `metadata.merged_from`); the older rows are archived.
3. **Decay** — `impact_decay` lowers `importance` of old rows per a
   half-life curve:
   `new = max(min_importance, importance * 0.5 ** (periods / halflife))`,
   where `periods = floor(elapsed_days / decay_days)`, `decay_days` default
   **7**, `halflife` default **2.0** periods, `min_importance` floor default
   **0.1**. Every applied decay writes a row to `decay_log`
   (`memory_id, happened_at, old_score, new_score`).

Archived and distilled rows are **excluded from `search`** (they are not
deleted — `memory_stats` counts them, and the data is recoverable). A row
becomes `archived` (compaction) or `distilled` (the synthesized entry);
both keep `status` set accordingly.

Idempotency (US-004): re-running `compact` after a partial failure skips
already-archived rows — they are counted as `skipped`, no double-archiving,
no new distilled entries, and the `compaction_log` uses
`INSERT OR IGNORE` keyed on `run_id`.

### Configuration defaults (locked)

| Constant | Default | Meaning |
|----------|---------|---------|
| `DEFAULT_COMPACTION_AGE_DAYS` | `30` | Minimum age (days) for distill eligibility |
| `DEFAULT_COMPACTION_IMPORTANCE_THRESHOLD` | `0.3` | Memories at/above this importance are kept |
| `DEFAULT_MERGE_THRESHOLD` | `0.82` | Cosine similarity for merge/cluster grouping |
| `DEFAULT_DECAY_DAYS` | `7` | One decay period (days) |
| `DEFAULT_DECAY_HALFLIFE` | `2.0` | Decay periods for importance to halve |
| `DEFAULT_MIN_IMPORTANCE` | `0.1` | Importance floor; never decays below |

### CLI: `ai-vibe-bench memory`

The CLI is dry-run by default; pass `--apply` to mutate.

```bash
# Review the plan (no mutations)
ai-vibe-bench memory compact --db /tmp/team-memory.db

# Apply: distill + merge + archive
ai-vibe-bench memory compact --apply --db /tmp/team-memory.db

# Override thresholds
ai-vibe-bench memory compact --apply --age-days 14 \
    --importance-threshold 0.5 --merge-threshold 0.9 --db /tmp/team-memory.db

# Importance decay (dry-run plan, then apply)
ai-vibe-bench memory decay --db /tmp/team-memory.db
ai-vibe-bench memory decay --apply --decay-days 14 --db /tmp/team-memory.db

# Extended stats (distilled/archived/merged/decayed counts + logs)
ai-vibe-bench memory stats --db /tmp/team-memory.db
```

The compact result looks like:

```json
{
  "run_id": "0f742d364ed14f089e9e7c994d67caad",
  "mode": "apply",
  "dry_run": false,
  "distilled": 2,
  "archived": 4,
  "merged": 1,
  "skipped": 0,
  "cluster_count": 2,
  "merge_count": 1
}
```

### MCP tool: `memory_compact`

The MCP server (`examples/mcp_memory_server.py`) exposes `memory_compact`
with the same semantics: `mode` is `"dry-run"` (default) or `"apply"`, plus
the three optional threshold overrides.

```python
# From any MCP client (Cursor, Claude Desktop, ...) or the importable tool:
from examples.mcp_memory_server import memory_compact

plan = memory_compact()                       # dry-run plan
result = memory_compact(mode="apply")         # apply with defaults
result = memory_compact(mode="apply", age_days=14, importance_threshold=0.5)
```

### Programmatic API

```python
from ai_vibe_coding.memory_store import MemoryStore

store = MemoryStore("/tmp/demo-memory.db")

# Plan first — never mutate blind
plan = store.compact(dry_run=True)
print(plan["cluster_count"], plan["merge_count"])   # e.g. 2 1

# Apply, then confirm idempotency
result = store.compact(dry_run=False)               # {"distilled": 2, "archived": 4, ...}
again = store.compact(dry_run=False)                # distilled=0, skipped>0

# Decay importance of old rows
store.impact_decay(dry_run=True)                    # {"decayed": N, "eligible_for_compaction": M, ...}
store.impact_decay(dry_run=False)                   # applies + writes decay_log

# Extended stats
stats = store.memory_stats()
print(stats["distilled_count"], stats["archived_count"],
      stats["merged_count"], stats["decayed_count"], stats["compact_runs"])
store.close()
```

A full runnable walkthrough (seeding stale memories, dry-run → apply →
idempotent re-run → decay → stats, with a deterministic clock) ships as
`examples/compaction_client_example.py`:

```bash
cd ai-vibe-coding-kit
python examples/compaction_client_example.py
```

### Backend status

`compact`, `impact_decay`, and `memory_stats` are implemented on the
**SQLite** backend (the default). The `StorageBackend` ABC gained the nine
compaction methods and `RedisBackend` declares them, but they are still
`NotImplementedError` stubs — calling these three methods on a
Redis-backed store raises `NotImplementedError`. Redis parity is tracked
separately (see CHANGELOG).

## Limitations & future work

- **No vector index** — `search` is a linear scan over the rows; fine for the
  default 10,000-row budget, not for millions of memories.
- **No graph memory** — no relationship extraction beyond the similarity
  merge; `select_merges`/`select_clusters` operate on flat embedding
  similarity (see the comparison table above; Mem0/Cognee cover graph
  consolidation).
- **stdio transport only** — streaming/SSE is out of scope; switching the
  server to `mcp.run(transport="sse")` is a one-line change if ever needed.
- **No auth / encryption-at-rest** — the SQLite file is plaintext; keep it out
  of shared volumes or encrypt at the filesystem level.
- **Redis compaction parity pending** — see [Backend status](#backend-status)
  above.
