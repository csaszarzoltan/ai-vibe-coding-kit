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
