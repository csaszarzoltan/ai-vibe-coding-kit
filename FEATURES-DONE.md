# FEATURES-DONE

Machine-readable record of shipped features. Each entry captures the
feature name, scope, and the source artifacts that implement it.

---

## Redis-backed Storage Backend

- **Feature**: Pluggable `StorageBackend` ABC with `RedisBackend` implementation
- **Scope**: `src/ai_vibe_coding/memory_store.py` — `StorageBackend` ABC, `RedisBackend` class
- **Install**: `pip install aivck[redis]` (requires `redis>=5.0.0`, pinned in `pyproject.toml` `[project.optional-dependencies].redis`)
- **Config**: `AI_VIBE_MEMORY_REDIS_URL` env var, `--redis-url` CLI flag on `mcp_memory_server.py`, or `MemoryStore(redis_url=...)` constructor
- **Redis layout**:
  - `aivck:memory:{id}` — Redis hash per memory (content, metadata, embedding, timestamps, importance)
  - `aivck:recency` — sorted set (member=id, score=timestamp) for recency-based eviction
  - `aivck:meta` — hash for embedding mode, embedding dim, evicted_total counter
- **API**: Same interface as SQLite — `store()`, `retrieve()`, `search()`, `forget()`, `stats()`
- **Test coverage**: 8 Redis-specific unit tests + 16 parametrized backend-agnostic tests (SQLite + Redis) in `tests/test_storage_backend_redis.py`; MCP Redis stdio integration tests in `tests/test_mcp_memory_server.py`
- **Verification**: 1152 tests pass on both backends (junitxml-verified, parent task t_1a4d5efc)
- **Docs**: README.md "Pluggable Storage Backend / Redis Backend" section, README.md "Redis Memory Backend" quick-start, `examples/redis_memory_client_example.py`

---

## Memory Compaction & Knowledge Distillation

- **Feature**: On-demand compaction of agent memory — stale low-importance clusters are distilled into summaries (originals archived, never deleted), near-duplicates merged, importance decayed over time, with an extended stats surface and a compaction log
- **Scope**: `src/ai_vibe_coding/memory_compaction.py` (new, deterministic pure-function engine), `src/ai_vibe_coding/memory_store.py` (`MemoryStore.compact`, `impact_decay`, `memory_stats`; `StorageBackend` ABC +9 abstract methods), `src/ai_vibe_coding/cli.py` (`ai-vibe-bench memory` subcommand), `examples/mcp_memory_server.py` (`memory_compact` MCP tool)
- **Defaults**: `compaction_age_days=30`, `compaction_importance_threshold=0.3`, `merge_threshold=0.82` (cosine), `decay_days=7`, `decay_halflife=2.0` periods, `min_importance=0.1` — all locked by `tests/test_memory_compaction.py`
- **API**:
  - `MemoryStore.compact(dry_run=True)` → plan (`candidate_distill_clusters`, `candidate_merges`, counts); `compact(dry_run=False)` → `{run_id, mode, distilled, archived, merged, skipped, cluster_count, merge_count}`
  - `MemoryStore.impact_decay(dry_run=...)` → `{decayed, eligible_for_compaction, min_importance, dry_run}`; writes `decay_log` on apply
  - `MemoryStore.memory_stats()` → base stats + `distilled_count`, `archived_count`, `merged_count`, `decayed_count`, `last_compaction`, `compact_runs`, `decay_events`
  - CLI: `ai-vibe-bench memory compact|decay|stats` (dry-run by default, `--apply` to mutate; `--age-days` / `--importance-threshold` / `--merge-threshold` / `--decay-days` / `--db` overrides)
  - MCP: `memory_compact(mode="dry-run"|"apply", age_days, importance_threshold, merge_threshold)`
- **Backend status**: SQLite implemented; RedisBackend declares the 9 new ABC methods but they raise `NotImplementedError` (Redis parity pending, tracked separately)
- **Test coverage**: 58 tests in `tests/test_memory_compaction.py` (interface + behavioral: distill/archive, merge, decay + decay_log, idempotent re-run, compaction log, stats)
- **Verification**: full suite 1210 passed (tester gate t_9f97f39b, commit 9138cbf), ruff clean on src/
- **Docs**: README.md "Memory Compaction & Knowledge Distillation" section + quick start, docs/memory-guide.md "Memory Compaction & Knowledge Distillation" guide, `examples/compaction_client_example.py` (verified runnable), CHANGELOG.md [0.14.0]
