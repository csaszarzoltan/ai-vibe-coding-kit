# MCP Agent Memory Server — Architecture & Tech Spec

- **Status:** Approved — implementation contract (v1)
- **Repo:** `ai-vibe-coding-kit` (branch `main`)
- **Target version:** `0.12.0` (current: `0.11.0`)
- **Author:** code-architect (kanban task `t_9605b236`)
- **Consumers:** pre-tester (writes `tests/test_mcp_memory_server.py`), developer (implements), documenter (writes `docs/memory-guide.md`, templates, README/CHANGELOG)

---

## 1. Overview

A self-hosted, SQLite-backed **MCP Agent Memory Server** that gives AI editors and
agent pipelines persistent, semantic memory. Agents can `store` memories, `retrieve`
them by id, `search` them semantically (real cosine similarity over real embeddings —
never a mock), `forget` them, and inspect `stats`. Memories survive restarts (SQLite
file), expire via TTL, and are evicted by an importance × recency score when a row
budget is exceeded.

The server follows the repo's existing `examples/standalone_mcp_server.py` pattern:
a `FastMCP` instance with `@mcp.tool()`-decorated, importable, plain-Python functions,
run over stdio. Core logic lives in `src/ai_vibe_coding/` so templates and the client
example can reuse it programmatically.

### 1.1 Acceptance criteria (from task)

The spec contains the full API contract, schema DDL, eviction formula, and file
layout, and is unambiguous enough that a pre-tester can write failing behavioral
tests from it without guessing. (§6–§11 are that contract.)

---

## 2. Design decisions (key decisions)

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Tools: `memory_store`, `memory_retrieve`, `memory_search`, `memory_forget`, `memory_stats`; server name `ai-vibe-memory` | Task body; matches standalone pattern naming. |
| D2 | Tools return JSON-serializable **dicts** (FastMCP serializes to JSON text content); plain functions stay importable/callable | Testable, MCP-wire compatible, richer than `str` returns. |
| D3 | `id` is a **UUID hex string** (`uuid4().hex`, 32 chars), TEXT PRIMARY KEY — not INTEGER AUTOINCREMENT | Client-held ids must never be reused after eviction; supports future sync/merge across stores. |
| D4 | Timestamps are **ISO-8601 UTC strings** (`datetime.now(UTC).isoformat()`, matching `cost_tracker.py`); TTL/age math done in **Python** | SQLite `datetime()`/`strftime()` do not reliably parse `+00:00` ISO offsets; Python keeps expiry deterministic. |
| D5 | Embeddings: **sentence-transformers `all-MiniLM-L6-v2`** (384-dim, `normalize_embeddings=True`) primary; **deterministic sha256 bag-of-words fallback** (256-dim) when package/model unavailable. Cosine similarity over normalized vectors in both modes. | Task requires real cosine, no mock; fallback keeps the server functional offline (lexical, not semantic — logged as `hash-fallback`). |
| D6 | Embedding mode is **pinned per database** (stored in `meta` table); a mode/dim mismatch on later writes raises `ValueError` | Prevents comparing 384-dim vs 256-dim vectors; predictable failure instead of silent garbage. |
| D7 | Eviction: purge expired-TTL rows on every `store`/`search`; when `total > max_rows`, delete the lowest `eviction_score = importance * recency_boost` (7-day half-life) until `total == max_rows`. | Task body formula; deterministic, testable, gentle (no eviction under budget). |
| D8 | Deps: add **`sentence-transformers>=2.2.0`** to `[project.dependencies]` (hard dep) | The semantic-search behavioral test requires the real model in the test env; pre-tester task mandates runtime deps pinned in `dependencies`. |
| D9 | Config: env `AI_VIBE_MEMORY_DB` (default `~/.ai_vibe_coding/memory.db`) + `AI_VIBE_MEMORY_MAX_ROWS` (default `10000`); CLI `--db` / `--max-rows` on the example server; constructor args on `MemoryStore`. | Task body; layered config with deterministic precedence: CLI > env > default. |
| D10 | File layout: `src/ai_vibe_coding/memory_store.py` + `src/ai_vibe_coding/memory_embedding.py` (core), `examples/mcp_memory_server.py` (FastMCP server), `examples/memory_client_example.py` (cross-session demo). New top-level `templates/` dir for the documenter. | Core reusable + thin MCP shell mirrors `standalone_mcp_server.py`. |
| D11 | Errors: `MemoryNotFoundError(KeyError)` raised by retrieve on missing id; `ValueError` for invalid args (bad content, importance, ttl). `memory_forget` is **idempotent** (never raises). | Consistent with repo pattern (standalone tools raise `ValueError`); idempotent forget is agent-friendly. |
| D12 | Clock seam: `MemoryStore(..., now=None)` — injectable zero-arg callable returning a tz-aware datetime (default `datetime.now(UTC)`). | Deterministic TTL tests without `sleep()`. |
| D13 | DB connections: fresh `sqlite3` connection per operation for file DBs (mirrors `SqliteCostStore`), single persistent connection for `:memory:`; `PRAGMA journal_mode=WAL` on file DBs. | Thread-safe under FastMCP's threadpool; survives restarts. |

---

## 3. File layout (exact)

New files (created by developer):

```
src/ai_vibe_coding/memory_embedding.py      # embed_text, cosine, serialization
src/ai_vibe_coding/memory_store.py          # MemoryStore, MemoryNotFoundError, DDL, eviction
examples/mcp_memory_server.py               # FastMCP server "ai-vibe-memory" (5 tools)
examples/memory_client_example.py           # cross-session store/retrieve/search demo
templates/memory_agent_orchestration.md     # NEW top-level templates/ dir (documenter)
templates/memory_prompt_chaining.md
templates/memory_cost_tracked_agent.md
docs/memory-guide.md                        # documenter
tests/test_mcp_memory_server.py             # pre-tester
```

Modified files:

```
pyproject.toml   # + "sentence-transformers>=2.2.0" in dependencies; version → 0.12.0
README.md        # documenter
CHANGELOG.md     # documenter (create if missing)
```

> Note: no `templates/` directory exists in the repo today — the documenter creates it.

---

## 4. Dependencies (`pyproject.toml`)

Add to `[project.dependencies]`:

```toml
"sentence-transformers>=2.2.0",
```

- Bump `version = "0.12.0"`.
- `sentence-transformers` pulls `torch` + `numpy` transitively. The **runtime code never imports numpy directly** (see §6 serialization) so the hash-fallback path keeps the server importable even if torch fails to load.
- No new dev dependencies.

---

## 5. Module contract — `src/ai_vibe_coding/memory_embedding.py`

```python
MODEL_NAME = "all-MiniLM-L6-v2"   # 384-dim sentence-transformers model
FALLBACK_DIM = 256                # deterministic hash-fallback dimension
```

### 5.1 `embed_text(text: str) -> tuple[list[float], str]`

Returns `(vector, source)` where `source` is exactly one of:

- `"sentence-transformers"` — model loaded lazily on first call; `model.encode([text], normalize_embeddings=True)[0]` → `list[float]` of length **384**.
- `"hash-fallback"` — deterministic lexical vector, length **256**, computed as:

```
tokens = re.findall(r"[a-z0-9]+", text.lower())
vec = [0.0] * 256
for token in tokens:
    d = hashlib.sha256(token.encode("utf-8")).digest()
    idx = int.from_bytes(d[:4], "little") % 256
    sign = 1.0 if d[4] % 2 == 0 else -1.0
    vec[idx] += sign
# L2-normalize; if norm == 0.0 leave vec as-is (cosine will be 0.0)
```

Rules:

- MUST use `hashlib.sha256` (never builtin `hash()` — per-process randomization makes it non-deterministic across runs).
- MUST be deterministic: same text → same vector on any platform/run.
- Both modes return **L2-normalized** vectors, so cosine similarity == dot product and scores land in roughly `[0, 1]` for MiniLM.
- Lazy loading: first call attempts `from sentence_transformers import SentenceTransformer` then `SentenceTransformer(MODEL_NAME)`. Any `ImportError`/`OSError` (e.g., offline, no HF cache) → fallback mode, and a one-time warning is printed to **stderr** (`"memory_embedding: sentence-transformers unavailable, using hash-fallback embeddings"`).
- Load the model at most once per process; cache the vectorizer.

### 5.2 `cosine_similarity(a: list[float], b: list[float]) -> float`

- Returns `float` in `[-1.0, 1.0]`; `0.0` if either vector is all zeros.
- MUST be a real cosine computation (`dot / (norm(a) * norm(b))`), never a constant/mock.
- Raises `ValueError` if `len(a) != len(b)`.

### 5.3 Serialization helpers (stdlib `array`, no numpy import)

```python
def serialize_vector(vec: list[float]) -> bytes      # array('f', vec).tobytes()
def deserialize_vector(blob: bytes) -> list[float]   # array('f').frombytes(blob).tolist()
```

- Round-trips exactly: `deserialize_vector(serialize_vector(v)) == v` (float32 precision is acceptable; scores computed on the float32 vectors).
- The embedding BLOB column stores `serialize_vector(embed_text(content)[0])`.

---

## 6. Module contract — `src/ai_vibe_coding/memory_store.py`

### 6.1 Constants & errors

```python
DEFAULT_DB_PATH = Path.home() / ".ai_vibe_coding" / "memory.db"
DEFAULT_MAX_ROWS = 10_000

class MemoryNotFoundError(KeyError):
    """Raised by retrieve() when no memory has the given id."""
```

### 6.2 `MemoryStore.__init__(db_path: str | Path = DEFAULT_DB_PATH, max_rows: int = DEFAULT_MAX_ROWS, now: Callable[[], datetime] | None = None)`

- `db_path`: file path or the literal string `":memory:"`. Parent dirs are created (`mkdir(parents=True, exist_ok=True)`). For file DBs, `PRAGMA journal_mode=WAL` is set at init; ignored for `:memory:`.
- `max_rows`: integer row budget, `>= 1`; `ValueError` otherwise. The **row budget is fixed for the store instance** — tests construct small stores (e.g. `max_rows=2`).
- `now`: clock seam for tests — a zero-arg callable returning a tz-aware `datetime`. Default: `lambda: datetime.now(UTC)`.
- `close()`: releases the persistent `:memory:` connection; no-op for file DBs (per-op connections are self-closing).

### 6.3 SQLite schema (exact DDL — `_ensure_tables`)

```sql
CREATE TABLE IF NOT EXISTS memories (
    id               TEXT PRIMARY KEY,              -- uuid4().hex (32 chars)
    content          TEXT NOT NULL,
    metadata         TEXT NOT NULL DEFAULT '{}',    -- JSON object
    embedding        BLOB,                          -- serialize_vector(embedding)
    created_at       TEXT NOT NULL,                 -- ISO-8601 UTC
    last_accessed_at TEXT NOT NULL,                 -- ISO-8601 UTC
    ttl_seconds      INTEGER,                       -- NULL = never expires
    importance       REAL NOT NULL DEFAULT 0.5
);
CREATE INDEX IF NOT EXISTS idx_memories_ttl          ON memories(ttl_seconds);
CREATE INDEX IF NOT EXISTS idx_memories_importance   ON memories(importance);
CREATE INDEX IF NOT EXISTS idx_memories_last_accessed ON memories(last_accessed_at);
CREATE INDEX IF NOT EXISTS idx_memories_created      ON memories(created_at);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

`meta` rows maintained by the store:

| key | value | set when |
|-----|-------|----------|
| `embedding_mode` | `"sentence-transformers"` \| `"hash-fallback"` | first embed |
| `embedding_dim`  | `"384"` \| `"256"` | first embed |
| `evicted_total`  | integer string | incremented on each eviction |

Mode pinning: on every embed (store/search), if `meta.embedding_mode` exists and differs from the current mode, or `embedding_dim` differs — raise `ValueError("EMBEDDING_MODE_MISMATCH: database was created with <mode>/<dim>, current is <mode>/<dim>")`. This makes mode changes explicit rather than silently corrupting similarity.

### 6.4 Timestamps & TTL

- `created_at` / `last_accessed_at`: `now().isoformat()` (e.g. `2026-08-03T12:00:00.123456+00:00`).
- Parse back with `datetime.fromisoformat`; compute ages in Python with `(now - dt).total_seconds()`.
- A memory is **expired** iff `ttl_seconds IS NOT NULL` AND `(now - created_at).total_seconds() >= ttl_seconds`.
- **TTL purge runs at the start of every `store()` and every `search()`**: delete all expired rows, increment `evicted_total` by the number deleted.

### 6.5 Validation (raises `ValueError`)

| arg | rule |
|-----|------|
| `content` | non-empty string (fails if not `str` or `.strip() == ""`) |
| `metadata` | `None` → `{}`; else must be a JSON-serializable dict (`TypeError`/`ValueError` otherwise) |
| `ttl_seconds` | `None`, or `int` with `>= 1` |
| `importance` | `float` in `[0.0, 1.0]` (reject out-of-range, do not clamp) |
| `limit` | `int`, clamped to `[1, 50]` |
| `min_score` | `float`, `[-1.0, 1.0]` |

### 6.6 Public methods — exact signatures & return contracts

```python
def store(self, content: str, metadata: dict | None = None,
          ttl_seconds: int | None = None, importance: float = 0.5) -> dict:
    """Returns: {"id": str, "stored": True,
                  "embedding_source": "sentence-transformers"|"hash-fallback",
                  "created_at": <ISO-8601 UTC str>}"""

def retrieve(self, memory_id: str) -> dict:
    """Returns: {"id", "content", "metadata": dict, "created_at", "last_accessed_at",
                  "ttl_seconds": int|None, "importance": float,
                  "embedding_source": str}
        Raises MemoryNotFoundError if id missing (or expired). Touches
        last_accessed_at = now()."""

def search(self, query: str, limit: int = 5, min_score: float = 0.0) -> dict:
    """Returns: {"query": str, "limit": int, "total": int,
                  "results": [ {"id","content","metadata": dict,"score": float,
                                "importance": float,"created_at","last_accessed_at",
                                "ttl_seconds": int|None} ]}
        score = cosine_similarity(query_embedding, row_embedding), rounded to 6 dp.
        Results sorted by: score DESC, importance DESC, created_at DESC.
        Rows with score < min_score are excluded. Expired rows are purged first."""

def forget(self, memory_id: str) -> dict:
    """Idempotent. Returns: {"id": str, "forgotten": bool}  (never raises)."""

def stats(self) -> dict:
    """Returns: {"total": int, "expired": int, "evicted": int,
                  "db_path": str, "max_rows": int,
                  "embedding_mode": "sentence-transformers"|"hash-fallback"}"""
```

- `store` flow: validate → purge expired → embed → insert → if `total > max_rows` evict (§6.7) → return.
- `retrieve` of an expired id: row is deleted first (purge-on-read) → `MemoryNotFoundError`.
- `embedding_source` on stored/retrieved rows is the mode recorded in `meta` at first embed.
- `search` with an empty result set returns `"total": 0, "results": []`.

### 6.7 Eviction (exact formula)

After TTL purge, let `total = COUNT(*)` from `memories`. If `total <= max_rows`, **no eviction happens**. Otherwise delete exactly `total - max_rows` rows with the **lowest** `eviction_score`:

```
age_seconds  = (now - last_accessed_at).total_seconds()
recency_boost = exp(-age_seconds / 604800.0)          # 7-day half-life (604800 s)
eviction_score = importance * recency_boost
```

- Ties broken by: older `created_at` first, then lexicographically smaller `id` (fully deterministic).
- Every deleted row increments `meta.evicted_total`.
- The eviction candidate set includes ALL rows (including just-inserted ones — a low-importance insert under an over-full store can evict itself).
- Eviction runs only inside `store()` (after insert); `search()` purges TTL-expired rows but never runs importance eviction.

Reference behavior (for pre-tester test 4): with `max_rows=2`, storing three rows with `importance` 0.1, 0.5, 1.0 and equal access times evicts the `0.1` row; `stats()["total"] == 2`, `stats()["evicted"] == 1`.

### 6.8 Connection handling

- File DB: open a fresh `sqlite3.connect(str(db_path))` per operation inside a context manager (autocommit via `commit()` before close). This is thread-safe under FastMCP's threadpool (mirrors `SqliteCostStore`).
- `":memory:"`: single persistent connection created at init, closed by `close()`.
- WAL is set once at init for file DBs.

---

## 7. Module contract — `examples/mcp_memory_server.py`

Mirrors `examples/standalone_mcp_server.py` structure (module docstring with usage, module-level `mcp`, `@mcp.tool()` functions, `if __name__ == "__main__"`). No API keys. stdio transport.

### 7.1 Server instance & config

```python
SERVER_NAME = "ai-vibe-memory"
mcp = FastMCP(SERVER_NAME)

_DB_PATH   = Path(os.environ.get("AI_VIBE_MEMORY_DB", DEFAULT_DB_PATH)).expanduser()
_MAX_ROWS  = int(os.environ.get("AI_VIBE_MEMORY_MAX_ROWS", DEFAULT_MAX_ROWS))
_store: MemoryStore | None = None     # lazy singleton; created on first tool call
```

- Config precedence: **CLI flag > env var > default** (`--db`, `--max-rows` parsed in `__main__` and written into module globals before first tool call).
- Importing the module must be side-effect-free except creating the `FastMCP` instance (no DB file created, no model loaded until a tool is first called).
- `_get_store()` lazily builds `MemoryStore(db_path=_DB_PATH, max_rows=_MAX_ROWS)`.

### 7.2 Tool functions (importable, callable directly — same shape as §6.6)

```python
@mcp.tool()
def memory_store(content: str, metadata: dict | None = None,
                 ttl_seconds: int | None = None, importance: float = 0.5) -> dict
@mcp.tool()
def memory_retrieve(memory_id: str) -> dict
@mcp.tool()
def memory_search(query: str, limit: int = 5, min_score: float = 0.0) -> dict
@mcp.tool()
def memory_forget(memory_id: str) -> dict
@mcp.tool()
def memory_stats() -> dict
```

- Each is a thin wrapper delegating to `_get_store()`; exceptions (`MemoryNotFoundError`, `ValueError`) propagate — FastMCP converts them to JSON-RPC errors.
- Registration order (also the `tools/list` order): `memory_store`, `memory_retrieve`, `memory_search`, `memory_forget`, `memory_stats`.

### 7.3 Tool JSON Schemas (canonical — derived from the signatures)

```json
{
  "memory_store": {
    "type": "object",
    "properties": {
      "content":     {"type": "string", "description": "Memory content to store"},
      "metadata":    {"type": "object", "description": "Optional structured metadata (JSON object)"},
      "ttl_seconds": {"type": "integer", "description": "Time-to-live in seconds; omit for never-expiring"},
      "importance":  {"type": "number", "description": "Importance weight 0.0-1.0, default 0.5"}
    },
    "required": ["content"]
  },
  "memory_retrieve": {
    "type": "object",
    "properties": {"memory_id": {"type": "string"}},
    "required": ["memory_id"]
  },
  "memory_search": {
    "type": "object",
    "properties": {
      "query":     {"type": "string"},
      "limit":     {"type": "integer", "description": "Max results 1-50, default 5"},
      "min_score": {"type": "number", "description": "Minimum cosine score, default 0.0"}
    },
    "required": ["query"]
  },
  "memory_forget": {
    "type": "object",
    "properties": {"memory_id": {"type": "string"}},
    "required": ["memory_id"]
  },
  "memory_stats": {"type": "object", "properties": {}}
}
```

### 7.4 MCP / JSON-RPC handshake contract (pre-tester test 6)

Transport: stdio, newline-delimited JSON-RPC 2.0 messages (FastMCP default). A standard `mcp` SDK client session (`mcp.client.stdio.stdio_client` + `ClientSession`) MUST work unmodified. Raw wire contract:

1. Client → server:
   ```json
   {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test-client","version":"0.0.1"}}}
   ```
2. Server → client result MUST include:
   ```json
   {"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"ai-vibe-memory","version":"0.12.0"}}
   ```
3. Client → server notification: `{"jsonrpc":"2.0","method":"notifications/initialized"}` (no `id`).
4. `tools/list` → `result.tools` is an array of **5** objects whose `name` fields are exactly the five tool names in §7.2 registration order.
5. `tools/call` with `{"name":"memory_stats","arguments":{}}` → `result.content[0]` is a text block whose `text` is the JSON dump of the `memory_stats()` return dict.
6. Errors: unknown tool name → JSON-RPC error response (FastMCP default).

### 7.5 `__main__`

```python
if __name__ == "__main__":
    # argparse: --db <path>, --max-rows <int>; defaults from env; then:
    mcp.run(transport="stdio")
```

---

## 8. Module contract — `examples/memory_client_example.py`

A runnable demo proving memory persists **across sessions**. Public surface:

```python
def run_demo(db_path: str | Path = DEFAULT_DB_PATH) -> dict: ...
def main() -> None: ...                       # argparse --db, then run_demo
if __name__ == "__main__":
    main()
```

`run_demo` flow (must be importable and callable with a temp path for tests):

1. **Session 1** — `store = MemoryStore(db_path)`; store ≥ 2 memories (one with `metadata={"topic": "sqlite"}`, one with `ttl_seconds` set, mixed `importance`); print the returned ids.
2. `memory_search("sqlite persistence")` on the same store; print top hits with scores.
3. `store.close()`.
4. **Session 2** — `store2 = MemoryStore(db_path)` (same path); `memory_retrieve(id_from_step_1)` → content matches; demonstrate `memory_search` again; `memory_forget` one id; print `memory_stats()`.
5. Returns a dict summarizing what was stored/retrieved (used by interface tests).

The example must not require network or an API key. If sentence-transformers is unavailable it still runs (hash-fallback).

---

## 9. Configuration reference

| Setting | Env var | CLI flag | Default |
|---------|---------|----------|---------|
| SQLite DB path | `AI_VIBE_MEMORY_DB` | `--db` | `~/.ai_vibe_coding/memory.db` |
| Row budget | `AI_VIBE_MEMORY_MAX_ROWS` | `--max-rows` | `10000` |

Precedence: CLI > env > default. `MemoryStore` constructor args override all (programmatic use).

---

## 10. Behavioral contract — mapping to pre-tester tests

The pre-tester writes `tests/test_mcp_memory_server.py` (interface tests that pass immediately against stubs; behavioral tests that fail with `NotImplementedError`). The spec below pins exact expected behavior for each mandated behavioral test:

| # | Test | Contract |
|---|------|----------|
| 1 | **CRUD round-trip** | `store("hello")` → `r`; `r["id"]` is a 32-char hex string; `retrieve(r["id"])["content"] == "hello"`; `forget(r["id"]) == {"id": r["id"], "forgotten": True}`; `retrieve(r["id"])` raises `MemoryNotFoundError`; `forget(r["id"])["forgotten"] == False` (idempotent). |
| 2 | **Semantic search** | `store("vector databases index embeddings")` then `search("embedding storage")` returns it in `results` with `score` = real cosine similarity (`> 0.0`, expect `>= 0.3` with the MiniLM model). `search` on an empty store returns `total == 0`. Embedding source must be `"sentence-transformers"` when the model is available. |
| 3 | **TTL expiry** | `store("temp", ttl_seconds=1)`; advance clock (or sleep ~1.1s); `search("temp")` excludes it and `retrieve(id)` raises `MemoryNotFoundError`; `stats()["expired"]` reflects the purged count; row is physically deleted. |
| 4 | **Importance eviction** | `MemoryStore(path, max_rows=2)`; store 3 rows with `importance` 0.1 / 0.5 / 1.0; `stats()["total"] == 2`, `stats()["evicted"] == 1`; `retrieve(low_id)` raises; high-importance rows survive. Also: under budget → **no** eviction. |
| 5 | **Persistence** | `MemoryStore(tmp_path)` → store → `close()`; new `MemoryStore(tmp_path)` → `retrieve` returns the same content. `:memory:` stores do NOT persist (file path required). |
| 6 | **MCP handshake** | spawn `python examples/mcp_memory_server.py` (stdio, `AI_VIBE_MEMORY_DB` pointed at a tmp file); `initialize` per §7.4; `tools/list` has the 5 names; `tools/call memory_stats` returns JSON text content. |

Stub contract for the pre-tester (so interface tests pass immediately):

- `ai_vibe_coding.memory_store`: `MemoryStore`, `MemoryNotFoundError`, `DEFAULT_DB_PATH`, `DEFAULT_MAX_ROWS` exist with the §6 signatures; unimplemented methods `raise NotImplementedError`.
- `ai_vibe_coding.memory_embedding`: `embed_text`, `cosine_similarity`, `serialize_vector`, `deserialize_vector`, `MODEL_NAME`, `FALLBACK_DIM` exist; unimplemented bodies `raise NotImplementedError`.
- `examples.mcp_memory_server`: module importable; `mcp`, `SERVER_NAME`, and the 5 tool functions exist; tools `raise NotImplementedError`.
- `examples.memory_client_example`: `run_demo`, `main` exist; `run_demo` `raise NotImplementedError`.

---

## 11. Integration notes (for documenter templates)

The documenter writes three templates under the new `templates/` dir. All API names below are real and MUST be used verbatim in templates/docs.

### 11.1 Agent orchestration

- Multi-agent pipelines in `src/ai_vibe_coding/agent_team.py` (`AgentPipeline`, `MessageBus`, `SharedState`) can share one `MemoryStore` as a team-wide episodic store.
- Pattern: each agent step `memory_search(query=<step intent>)` before acting (recall), `memory_store(content=<outcome summary>, metadata={"agent": "<name>", "stage": "plan"|"act"|"verify"})` after acting (commit).
- MCP path for editor agents: Cursor/Claude Desktop config pointing at `examples/mcp_memory_server.py` with `env: {"AI_VIBE_MEMORY_DB": "<shared path>", "PYTHONUNBUFFERED": "1"}` — same JSON shape as `docs/mcp-guide.md` §3/§4.

### 11.2 Prompt chaining

- `src/ai_vibe_coding/chain_templates.py` (`SequentialChain`, `ConditionalChain`, `ParallelChain`, `ChainContext`, `ChainResult`) — inject memory between steps: before step N, `memory_search(step_N_intent, limit=3)`; concatenate top results into the step prompt as `"Relevant memories:\n- ..."`; after the step, `memory_store(chain_id + step summary, metadata={"chain": id, "step": n})`.

### 11.3 Cost-tracked agents

- `src/ai_vibe_coding/cost_tracker.py`: `CostTracker`, `CostSummary.to_dict()` (`total_cost`, `total_tokens`, `per_provider`, `per_model`, `call_count`), `LLMResponse` from `src/ai_vibe_coding/llm_wrapper.py`.
- Pattern: wrap each agent run — `tracker.record(response)` per LLM call; after the run, `memory_store(f"Session {session_id} cost ${summary.total_cost:.4f}, {summary.total_tokens} tokens", metadata={"type": "cost", "session_id": session_id, "cost_usd": summary.total_cost})`; agents can then `memory_search("cost")` to recall past spend before deciding whether to continue.
- Persistence mirrors `cost_store.SqliteCostStore` (WAL, per-op connections) — memory and cost DBs are separate files by default.

---

## 12. Testability seams (already in the contract)

1. `MemoryStore(..., now=...)` clock injection — TTL tests advance time without sleeping.
2. `db_path=":memory:"` — fast isolated tests; `close()` releases the connection.
3. Small `max_rows` (2–3) — eviction tests without storing 10k rows.
4. Lazy model load — tests that don't touch embeddings run without sentence-transformers; semantic tests run with it (hard dep).
5. Importable tool functions — behavioral tests call `memory_store(...)` etc. directly without an MCP client; only handshake test spawns the process.

---

## 13. Out of scope (explicit)

- Vector index (no `sqlite-vec`, no FAISS): linear scan over ≤ 10k rows is fine; note as future work.
- Graph memory, memory consolidation/dedup, encryption-at-rest, multi-user auth.
- Streaming/SSE transport (stdio only; `mcp.run(transport="sse")` is a one-line change if ever needed).
- Changes to `docs/mcp-guide.md` (documenter may add a cross-link in README only).

---

## 14. Implementation order (mechanical)

1. `pyproject.toml`: add `sentence-transformers>=2.2.0`, bump version to `0.12.0`.
2. `src/ai_vibe_coding/memory_embedding.py` (pure functions, no DB).
3. `src/ai_vibe_coding/memory_store.py` (DDL → store/retrieve/search/forget/stats → TTL purge → eviction).
4. `examples/mcp_memory_server.py` (FastMCP shell).
5. `examples/memory_client_example.py` (cross-session demo).
6. Verify with `.venv/bin/python -m pytest` and `.venv/bin/python -m ruff`; pre-tester's suite goes green.
