# Analysis Brief: Memory Compaction & Knowledge Distillation — Auto-Summarization, Merging & Importance Decay

**Date:** 2026-08-08
**Author:** Analyst profile (kanban task `t_4fee08cb`)
**Status:** Complete — contract for pre-tester RED suite (`t_479c12c3`)
**Repo:** `ai-vibe-coding-kit` at `/home/zoltan/ai-vibe-coding-kit` (branch `main`)
**Current version:** v0.13.0 (Redis backend released 2026-08-06)
**Target version:** v0.14.0
**Parent feature task:** `t_f257b10d`

---

## 0. Research-brief substitution note

`analysis/research-brief.md` does **not** exist in the repo (verified: only
`analysis-brief.md` and `memory-architecture.md` are present under `analysis/`).
The feature task body (`t_f257b10d`) is fully self-contained (acceptance
criteria, user stories, tech context, competitor references), so I substituted
with **direct repo inspection** of the live code at branch `main` (HEAD
`e47d19e`) plus **targeted web research** on the named competitors (Mem0 decay,
Zep summarization, Microsoft Agent Memory compaction, Hindsight
consolidation-lever framework). This substitution is noted here as required by
the task. See §9 Source Links for the research anchors.

---

## 1. Current State Assessment

### 1.1 The memory subsystem today (what compacts/decays already)

Inspected live on branch `main` (HEAD `e47d19e`, v0.13.0).

| Asset | File | Role |
|-------|------|------|
| `StorageBackend` ABC | `src/ai_vibe_coding/memory_store.py` (938 LoC) | Abstract contract: `store/retrieve/search/forget/stats`, plus internal hooks `bump_meta`, `purge_expired`, `evict_if_over_budget`, `close` |
| `RedisBackend` | same file | Hash (`aivck:memory:{id}`) + recency zset (`aivck:recency`) + meta hash (`aivck:meta`) mapping; fully implemented |
| `MemoryStore` | same file | SQLite-backed (`memories` + `meta` tables, WAL on file DBs, fresh conn per op); the public façade that delegates to a backend when `backend=`/`redis_url=` is passed |
| `MemoryNotFoundError` | same file | `KeyError` subclass for missing-id retrieval |
| `memory_embedding.py` | `src/ai_vibe_coding/memory_embedding.py` (134 LoC) | `embed_text`, `cosine_similarity`, `serialize_vector`/`deserialize_vector`, `current_mode`; all-MiniLM-L6-v2 (384-dim) + deterministic sha256 hash-fallback (256-dim), both L2-normalized |
| MCP memory server | `examples/mcp_memory_server.py` | FastMCP server `ai-vibe-memory`, stdio transport, 5 tools (`memory_store`, `memory_retrieve`, `memory_search`, `memory_forget`, `memory_stats`), CLI flags `--db`/`--max-rows`/`--redis-url`, env `AI_VIBE_MEMORY_DB/MAX_ROWS/REDIS_URL` |
| CLI entry | `src/ai_vibe_coding/cli.py` | `ai-vibe-bench` console script (benchmark + cost subcommands) — NOT the memory CLI |
| Existing tests | `tests/test_mcp_memory_server.py` (696 LoC), `tests/test_storage_backend_redis.py` | 1152 passing on both backends (per FEATURES-DONE). `FakeClock` seam (`now=` injectable), `backend_store` parametrized fixture, interface-vs-behavioral split |

**Current memory lifecycle** (all already implemented):
- `store()` → embeds content, persists, pins per-DB embedding mode/dim.
- `retrieve()` / `search()` → touch `last_accessed_at`; `search` ranks by real cosine similarity.
- TTL purge → expired rows deleted on read/write (`purge_expired`).
- **Hard eviction** → when `total > max_rows`, delete lowest `eviction_score = importance * recency_boost` where `recency_boost = e^(-age/604_800)` (7-day half-life). This is the only shrink path and it **deletes wholesale** — no distillation.
- `stats()` → `{total, expired, evicted, db_path, max_rows, embedding_mode}`.

### 1.2 The gap (what's missing)

The store grows monotonically under `max_rows` and **only shrinks by hard
deletion**. There is:
- ❌ No compaction job (CLI or MCP `memory_compact`), no `--dry-run`/`--apply`.
- ❌ No summarization/distillation of stale low-importance clusters; no `archived` status with provenance.
- ❌ No duplicate/overlap **merge** via cosine similarity.
- ❌ No **importance decay** over time (only the passive half-life used inside eviction); no `decay_log`.
- ❌ No compaction/decay stats in `memory_stats` (distilled/archived/merged/decayed counts + compaction log).
- ❌ No backend-parity compaction path on the `StorageBackend` ABC (both SQLite and Redis).

### 1.3 Gap analysis table

| Capability | Status | Priority | Notes |
|-----------|--------|----------|-------|
| Store/retrieve/search/forget/stats | ✅ Exists | — | SQLite + Redis via `StorageBackend` ABC |
| Importance × recency hard eviction | ✅ Exists | — | Only shrink path; deletes wholesale. Decay foundation |
| Real cosine embedding + fallback | ✅ Exists | — | `memory_embedding.py`; reuse for merge scoring |
| TTL purge / clock seam (`now=`) | ✅ Exists | — | Reuse the same `FakeClock` pattern for age-based compaction |
| **Compaction job** (CLI + MCP `memory_compact`, `--dry-run`/`--apply`) | ❌ Missing | **P0** | US-001 |
| **Auto-summarization** of stale low-importance clusters → distilled entry, originals `archived` | ❌ Missing | **P0** | US-001 |
| **Duplicate/overlap merging** (cosine ≥ `merge_threshold` → one merged, older archived) | ❌ Missing | **P1** | US-002 |
| **Importance decay** (`decay_days`/curve, rarely-accessed reduce, `decay_log`) | ❌ Missing | **P1** | US-003 |
| **Idempotent partial-failure recovery** | ❌ Missing | **P2** | US-004 |
| **Stats** (distilled/archived/merged/decayed + compaction log in `memory_stats`) | ❌ Missing | **P1** | Acceptance #6 |
| **Backend parity** (SQLite + Redis) | ❌ Missing | **P0** | Acceptance #7; ABC is the seam |

### 1.4 Key risks

| Risk | Context | Mitigation |
|------|---------|------------|
| Backend parity drift | Compaction must run on both SQLite and Redis; easy to implement for one only | Put policy in shared pure code; add new `StorageBackend` ABC methods; reuse `TestBackendAgnosticBehavior` param fixture |
| LLM-free deterministic requirement | "no other server does **offline deterministic** merge + decay"; tests ban mocking merge/summarize | Summarize/merge must be **deterministic pure functions** (concatenation + template, embedding-similarity merge), not an LLM call; summarizer needs no runtime deps |
| Data loss / destructive re-run | Re-running after partial failure must not double-archive or delete | `archived` is a **status flag**, never delete; skip already-archived rows; unit-of-work per cluster/merge |
| Provenance | Originals must survive summarization | Mark `archived`, keep row; search filters archived out but retrieval-by-id still resolves them |
| Schema migration | Adding `status`, `archived_at`, `last_decayed_at`, `compaction_log` table | `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ... ADD COLUMN` guarded by PRAGMA introspection to stay idempotent across existing DBs |
| `search` semantics change | Archived rows must be excluded from `search` results (US-001) but not from `retrieve` | Add `WHERE status != 'archived'` to search; only `retrieve` grants access to archived |

---

## 2. Clustered Options

### Option A (RECOMMENDED): Deterministic, backend-agnostic compaction engine layered on the existing `StorageBackend` ABC

New pure engine module (`memory_compaction.py`) holds all policy (selection,
summarization, merge scoring, decay math) as **deterministic, dependency-free
functions**. The `StorageBackend` ABC gains new abstract methods (`archive`,
`merge`, `decay_run`, `distill`, `compaction_log`/`decay_log` reads) implemented
by both SQLite and Redis. `MemoryStore` exposes `compact(dry_run/apply)` +
`impact_decay()` + extended `stats()`. Thin CLI + MCP tools wrap them.

+ Single policy source, testable without backend
+ Satisfies "LLM-free deterministic" + "no mocks for merge/summarize" + backend parity
+ Reuses existing `embed_text`/`cosine_similarity`, `FakeClock` tests, `backend_store` fixture
− Adds abstract methods to `StorageBackend` (both backends must implement; Redis already implements the ABC)

### Option B: SQLite-only compaction, Redis deferred

Implement compaction only on the SQLite `MemoryStore` path; leave Redis a
follow-up.

+ Less work now
− **Fails acceptance #7 (backend parity)** — unacceptable for this feature

### Option C: LLM-driven summarizer (call an LLM to distill)

Use an LLM call to write the distilled entry.

+ "Higher-quality" summaries
− Requires API keys, network, and is non-deterministic; **violates the entire
  self-hosted/offline and no-mock requirement**; breaks tests and parity.
  Rejected outright.

**Decision: Option A**, scoped as P0 (distill) → P1 (merge, decay, stats) → P2
(idempotent recovery hardening). The summarizer is a **deterministic template
summarizer** (concatenate + dedupe + header), documented as non-LLM per the
feature's differentiation claim.

---

## 3. Chosen Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Compaction engine | `src/ai_vibe_coding/memory_compaction.py` (NEW, pure) | Deterministic policy functions; zero new runtime deps; unit-testable with no backend |
| Similarity scoring | Reuse `memory_embedding.cosine_similarity` + `embed_text` | Already shipped; real cosine, no mock |
| Summarizer | Deterministic template summarizer in `memory_compaction.py` | LLM-free; concatenates sources, strips near-duplicate lines, wraps in metadata header; deterministic by construction |
| Storage seam | Extend `StorageBackend` ABC + add `archived`/`last_decayed_at` columns + `compaction_log` + `decay_log` tables (SQLite) and equivalent keys (Redis) | Backend parity via the existing ABC; both backends implement the same new methods |
| Clock / age | Reuse injectable `now=` seam | Age-based selection (`compaction_age_days`) testable without `sleep()` |
| Config | Module-level constants + env overrides + CLI/MCP kwargs: `compaction_age_days`, `compaction_importance_threshold`, `merge_threshold`, `decay_days`, `max_rows` unchanged | Layered config matching repo precedence (CLI > env > default) |
| Decay curve | `importance *= 0.5^(decay_periods_elapsed / decay_halflife)`, floored at a `min_importance` | Matches existing half-life math; Ebbinghaus-style; deterministic |
| CLI | `examples/mcp_memory_server.py` gains `memory_compact` + `memory_decay` tools; a `--dry-run`/`--apply` mode exposed via tool arg | Follows existing `@mcp.tool()` pattern in the same file |
| Tests | `tests/test_memory_compaction.py` (+ optionally `test_<subsection>`) | Pre-tester RED suite |

**No new runtime dependencies.** Everything is stdlib + already-shipped
`sentence-transformers`/fallback.

---

## 4. Data model & contract (locked for the pre-tester)

### 4.1 Memory status model

Each memory gains a `status` field with one of:
- `active` (default; the only state returned by `search`)
- `archived` (originals preserved after distill/merge; NOT deleted; excluded from `search`, resolvable via `retrieve`)
- `distilled` (a generated distilled entry — active in search)

New SQLite columns on `memories`: `status TEXT NOT NULL DEFAULT 'active'`,
`archived_at TEXT`, `last_decayed_at TEXT`. New tables:
```
CREATE TABLE IF NOT EXISTS compaction_log (
    run_id      TEXT PRIMARY KEY,
    mode        TEXT NOT NULL,             -- 'dry-run' | 'apply'
    started_at  TEXT NOT NULL,
    distilled   INTEGER NOT NULL DEFAULT 0,
    archived    INTEGER NOT NULL DEFAULT 0,
    merged      INTEGER NOT NULL DEFAULT 0,
    summary     TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS decay_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id   TEXT NOT NULL,
    happened_at TEXT NOT NULL,
    old_score   REAL NOT NULL,
    new_score   REAL NOT NULL
);
```

### 4.2 StorageBackend ABC — new abstract methods

```python
def archive(self, memory_id: str, *, archived_at: str) -> dict:
    """Mark a memory 'archived' (never delete). Returns {id, status}."""
def list_memories(self, include_archived: bool = False) -> list[dict]:
    """Return all memory rows (content, embedding, created_at, last_accessed_at,
       importance, status) for the compaction engine to plan over."""
def batch_update_status(self, ids: list[str], status: str, *, archived_at: str | None = None) -> int:
    """Atomic status update for a set of ids; returns rows affected (idempotent:
       re-running with already-archived ids returns 0 new changes)."""
def write_distilled(self, content: str, sources: list[str], importance: float) -> dict:
    """Persist a distilled entry with status='distilled' and provenance metadata
       (source_ids). Returns the new memory dict."""
def record_compaction_run(self, run_id: str, *, mode: str, distilled: int, archived: int, merged: int, summary: str) -> None:
    """Append a compaction_log row (no-op duplicate if run_id exists)."""
def list_compaction_log(self, limit: int = 20) -> list[dict]:
    """Return recent compaction runs (newest first)."""
def record_decay(self, memory_id: str, *, old_score: float, new_score: float, happened_at: str) -> None:
    """Append a decay_log row."""
def list_decay_log(self, limit: int = 50) -> list[dict]:
    """Return recent decay events (newest first)."""
def set_importance(self, memory_id: str, importance: float, *, last_decayed_at: str) -> dict:
    """Update importance + last_decayed_at atomically; return the row."""
```
All methods are backend-agnostic contracts; `MemoryStore` delegates to the
bound backend exactly as today, and the SQLite implementation lives in
`MemoryStore`; the Redis implementation in `RedisBackend`.

### 4.3 `MemoryStore` public API additions

```python
def compact(self, *, dry_run: bool = True,
            age_days: float | None = None,
            importance_threshold: float | None = None,
            merge_threshold: float | None = None) -> dict:
    """Run the compaction job. dry_run=True (default) returns a PLAN dict
       (candidate_distill_clusters, candidate_merges, estimated counts) and
       mutates nothing. dry_run=False applies: distills stale clusters,
       archives originals, merges duplicates, records a compaction_log entry.
       Idempotent: already-archived rows are skipped; a partial failure leaves
       the state consistent so a re-run finishes without double-archiving.
       Returns {run_id, mode, distilled, archived, merged, skipped,
                cluster_count, merge_count, dry_run}."""

def impact_decay(self, *, decay_days: float | None = None,
                 dry_run: bool = False) -> dict:
    """Reduce importance of rarely-accessed old memories per the decay curve,
       record decay_log events, mark eligible ones for compaction.
       Returns {decayed, eligible_for_compaction, min_importance, dry_run}."""

def memory_stats(self) -> dict:
    """Extended stats: existing keys + distilled_count, archived_count,
       merged_count, decayed_count, last_compaction, compact_runs (from
       compaction_log), decay_events (from decay_log)."""
```

### 4.4 Compaction policy (deterministic)

1. **Select stale candidate clusters** — memories with `status == 'active'`,
   age since `created_at` > `compaction_age_days` (default e.g. 30), and
   `importance < compaction_importance_threshold` (default e.g. 0.3).
2. **Cluster** by embedding similarity (cosine ≥ `merge_threshold`, default
   e.g. 0.82, computed over stored embeddings via `cosine_similarity`).
3. **Distill** each cluster: `distilled_content = summarize(sources)` where
   `summarize` is the deterministic template summarizer (concatenate non-duplicate
   lines, wrap in a header naming source ids + date range).
4. **Archive** each original (`status='archived'`, `archived_at` set). Write the
   distilled entry with `status='distilled'`, provenance `source_ids` in metadata.
5. **Merge** clusters of active duplicates with cosine ≥ `merge_threshold`:
   keep the newest/highest-importance as merged entry, archive the rest, combine
   content into merged content, record provenance.
6. Record one `compaction_log` row describing the run.

### 4.5 Decay curve (deterministic)

`decay_periods = floor((now - last_decayed_at or created_at) / decay_days)`
`new_importance = max(min_importance, importance * 0.5
                      ** (decay_periods / decay_halflife))`
with `decay_halflife` (default 2.0) and `min_importance` (default 0.1). Every
actual reduction appends a `decay_log` row (`{memory_id, old, new, happened_at}`).
A decayed memory may become compaction-eligible (ties US-003 → US-001).

---

## 5. Prioritized Task List (P0/P1/P2) — task specs

Each spec includes: file/module, expected behavior, interface, dependencies,
acceptance criteria. These are the contracts the pre-tester RED suite (`t_479c12c3`)
must encode in `tests/test_memory_compaction.py` (+ split behavioral classes).

### P0-A — Compaction engine (distill + archive), US-001
- **Module:** `src/ai_vibe_coding/memory_compaction.py` (NEW); extend `memory_store.py` (`MemoryStore.compact`, `StorageBackend` new methods).
- **Behavior:** `compact(dry_run=True)` returns a non-mutating plan; `compact(dry_run=False)` distills stale low-importance clusters into one distilled entry and marks originals `archived` (never deletes). Archived excluded from `search`, still `retrieve`-able. Idempotent.
- **Interface:** §4.3 `compact`; §4.2 ABC methods (`archive`, `list_memories`, `batch_update_status`, `write_distilled`, `record_compaction_run`, `list_compaction_log`).
- **Dependencies:** `memory_embedding` (`embed_text`, `cosine_similarity`, `serialize_vector`); `MemoryStore`; clock seam.
- **Acceptance:**
  1. Seeded >N stale low-importance active memories → `compact(dry_run=True)` plan lists them/counts them, `dry_run=True` makes **zero** mutations (store unchanged).
  2. `compact(dry_run=False)` creates 1 distilled entry (status `distilled`) and marks originals `archived` (rows still exist, `status=='archived'`).
  3. `search` excludes archived rows; `retrieve(<archived-id>)` still returns it.
  4. Re-running `compact` on the same store yields `skipped >= previously-archived`, no double-archiving, no new distilled duplicates.

### P0-B — MCP + CLI `memory_compact` surface, US-001
- **Module:** extend `examples/mcp_memory_server.py` (add `memory_compact` + `memory_stats` tool) — this is both the MCP surface and the `aivck memory` CLI the task's GUI flow references.
- **Behavior:** `memory_compact(mode="dry-run"|"apply", ...)` returns the plan/result dict (JSON-serializable). `memory_stats` returns extended stats. Non-mutating for `mode="dry-run"`.
- **Interface:** `@mcp.tool()` `memory_compact(*, mode: str = "dry-run", age_days: float|None=None, importance_threshold: float|None=None, merge_threshold: float|None=None) -> dict`; `memory_stats` already exists but now returns the extended dict.
- **Dependencies:** P0-A engine; `_get_store()` singleton.
- **Acceptance:**
  1. `build_parser()`/server advertises `memory_compact` (toolname present).
  2. Calling `memory_compact(mode="dry-run")` returns a plan; no store change.
  3. Calling `memory_compact(mode="apply")` returns counts and mutates per P0-A.
  4. `memory_stats` includes `distilled_count/archived_count/merged_count/decayed_count` + `compact_runs`/`decay_events`.

### P1-A — Duplicate/overlap merge, US-002
- **Module:** extend `memory_compaction.py` (`merge` policy) + `MemoryStore.compact`.
- **Behavior:** active memories with cosine ≥ `merge_threshold` (reusing real embeddings) are merged → one merged entry (newest kept), older originals archived, content combined, provenance metadata.
- **Interface:** pure `select_merges(memories, threshold) -> list[(newest_id, [older_ids])]`; `MemoryStore.compact` applies them.
- **Dependencies:** P0-A; `cosine_similarity`.
- **Acceptance:**
  1. Two near-duplicate active memories (cosine ≥ threshold) → merged into one, older archived, merged content includes both.
  2. Below-threshold memories are untouched.
  3. No merge of archived/distilled entries.

### P1-B — Importance decay, US-003
- **Module:** extend `memory_compaction.py` (`decay_scores`, `build_decay_plan`) + `MemoryStore.impact_decay`.
- **Behavior:** rarely-accessed old memories have importance reduced per the decay curve (half-life model), `decay_log` records each event, decayed rows may become compaction-eligible; `min_importance` floor.
- **Interface:** `impact_decay(*, decay_days=None, dry_run=False)` per §4.3; ABC `set_importance`, `record_decay`, `list_decay_log`; pure `compute_decay(row, now, decay_days, halflife, min_importance) -> float`.
- **Dependencies:** clock seam; schema columns `last_decayed_at`.
- **Acceptance:**
  1. Old rarely-accessed memory importance decreases; recently-accessed/mostly idle unchanged or negligible.
  2. Each reduction writes a `decay_log` row with old/new scores + timestamp.
  3. Importance is never below `min_importance`.
  4. A decayed memory below `compaction_importance_threshold` is compaction-eligible (feeds US-001).

### P1-C — Extended stats, acceptance #6
- **Module:** extend `MemoryStore.stats` / `memory_stats` / both backends' `stats`.
- **Behavior:** `memory_stats` exposes `distilled_count, archived_count, merged_count, decayed_count` and the compaction log / decay events.
- **Interface:** §4.3 `memory_stats`.
- **Dependencies:** P0-A counters + `compaction_log`/`decay_log`.
- **Acceptance:** after an apply + decay run, all counts are correct and non-decreasing logged.
- (Fold into P0-B's `memory_stats` acceptance; listed separately to keep the counter/backend work explicit.)

### P1-D — Backend parity (SQLite + Redis)
- **Module:** `RedisBackend` implements every new abstract method (mirror of SQLite logic using `aivck:memory:{id}` hashes, `aivck:meta` counters, `aivck:compaction_log` list, `aivck:decay_log` list).
- **Behavior:** all compaction/decay/stats operations behave identically on SQLite and Redis.
- **Interface:** §4.2 ABC methods on `RedisBackend`.
- **Dependencies:** P0-A; existing `TestBackendAgnosticBehavior` fixture pattern.
- **Acceptance:** the parametrized backend-agnostic suite runs the same compaction/decay assertions against both backends.

### P2-A — Idempotent partial-failure recovery, US-004
- **Module:** harden `MemoryStore.compact` (unit-of-work per cluster; `batch_update_status` idempotent; `record_compaction_run` dedupes by `run_id`).
- **Behavior:** a simulated failure mid-run (e.g. injectable flaky backend hook) leaves no double-archive; the re-run skips completed work and finishes.
- **Interface:** same `compact`; optional `now`/failure-injection seams for tests.
- **Dependencies:** P0-A, P1-A.
- **Acceptance:**
  1. Force failure after archiving cluster 1 of 2 → re-run compacts only cluster 2, cluster 1 not re-archived, no data loss.
  2. `compaction_log.run_id` collision is a no-op (no duplicate log entry).

---

## 6. Module dependency graph

```
examples/mcp_memory_server.py           (P0-B tools: memory_compact, memory_stats, ...)
        │  @mcp.tool() → _get_store()
        ▼
MemoryStore (memory_store.py)           (P0-A: compact / impact_decay / memory_stats)
        │  delegating: backend?.compact-hooks / sqlite direct
        ├──► StorageBackend ABC  ◄──  RedisBackend (P1-D)
        │        (archive, list_memories, batch_update_status, write_distilled,
        │         record_compaction_run, list_compaction_log,
        │         set_importance, record_decay, list_decay_log)
        ▼
memory_compaction.py  (P0-A/P1-A/P1-B pure policy: summarize, select_clusters,
                       select_merges, compute_decay, build plans)
        │  uses
        ▼
memory_embedding.py  (embed_text, cosine_similarity, serialize_vector)
```

---

## 7. Pre-tester module-mapping note (comment target `t_479c12c3`)

The auto-decomposer template names modules `src/hermes/...`; the repo uses
`src/ai_vibe_coding/`. I will comment the corrected mapping on `t_479c12c3`:
- New file to spec: `src/ai_vibe_coding/memory_compaction.py` (pure engine).
- Extend: `src/ai_vibe_coding/memory_store.py` (`StorageBackend` ABC, `RedisBackend`, `MemoryStore`).
- Extend: `examples/mcp_memory_server.py` (new tools).
- Test file: `tests/test_memory_compaction.py` (interface-tests-pass / behavioral-fail pattern; `FakeClock`; `backend_store` param fixture for parity).
- Do NOT write inverse stub-guard tests asserting `pytest.raises(NotImplementedError)` on feature methods.
- Stub file (scratch, uncommitted): `memory_compaction.py` raising `NotImplementedError` for the developer to replace.

---

## 8. Risk register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Backend parity drift | Med | High | Policy pure + ABC methods; backend-agnostic param suite |
| Destructive re-run / double-archive | Med | High | `archived` flag (never delete), idempotent `batch_update_status`, run_id dedupe (P2-A) |
| Schema migration on existing DBs | Med | Med | `CREATE TABLE IF NOT EXISTS` + guarded `ADD COLUMN` |
| Search returns archived | Med | Med | `WHERE status != 'archived'` in search; retrieve still resolves |
| Deterministic summarizer quality | Low | Low | Template summarizer documented as non-LLM; deterministic by construction |
| Existing 1152 tests regress | Low | Med | Extension only; `ALTER`/`CREATE IF NOT EXISTS`; run full suite in .venv |

---

## 9. Source links (research-brief substitution)

- Hindsight, *The Consolidation Problem in Agent Memory* — "four-lever framework: importance, merge, decay, eviction" (maps to US-001..004). https://hindsight.vectorize.io/blog/2026/05/21/agent-memory-consolidation
- Mem0, *Introducing Memory Decay* — recency-weighted ranking; idle memories move lower. https://mem0.ai/blog/introducing-memory-decay-in-mem0
- Mem0 / MemoryBank (via arxiv survey) — Ebbinghaus decay curve; "significance and recency, not capacity alone, govern survival". https://arxiv.org/html/2607.08032v1
- Microsoft Agent Framework, *Compaction* — "selectively removing, collapsing, or summarizing older portions ... summarization". https://learn.microsoft.com/en-us/agent-framework/agents/conversations/compaction
- Zep — temporal knowledge-graph summarization; graph carries decay/clustering/archival. https://blog.getzep.com/ ... /ZEP__USING_KNOWLEDGE_GRAPHS...pdf ; https://www.getzep.com/
- Repo ground truth: `analysis/memory-architecture.md` (v0.12.0 memory spec §1–§7), `src/ai_vibe_coding/memory_store.py`, `memory_embedding.py`, `examples/mcp_memory_server.py`, `tests/test_mcp_memory_server.py`, `tests/test_storage_backend_redis.py`.

---

## 10. Verification commands (for downstream workers)

```bash
cd /home/zoltan/ai-vibe-coding-kit
./.venv/bin/python -m pytest tests/test_memory_compaction.py -v          # new RED suite
./.venv/bin/python -m pytest -q                                          # full suite, no regressions
./.venv/bin/python -m ruff check src tests examples                      # lint
bash /home/zoltan/.hermes/scripts/tdd-gate-v3.sh /home/zoltan/ai-vibe-coding-kit
```

---

## 11. Assumptions / constraints

- Summarization is **deterministic and LLM-free** (feature's differentiator; no mocks).
- `archived` memory is **never deleted** (provenance); `forget()` may still hard-remove it explicitly.
- All new code keeps stdlib + already-shipped deps; **no new runtime dependency** beyond what exists.
- Bump `version = "0.14.0"` at release; README/CHANGELOG/FEATURES-DONE updated by later chain stages (not this analyst task).
- The repo tree already has an unrelated uncommitted edit (`docs/api-reference.md`); this brief does not modify or commit it.
