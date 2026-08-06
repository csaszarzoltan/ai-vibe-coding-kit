"""Redis memory client example — cross-process store/retrieve/search demo.

Demonstrates using the Redis-backed StorageBackend for agent memory.
Requires a running Redis server and the ``aivck[redis]`` extra installed.

Usage:
    # With a local Redis server:
    python examples/redis_memory_client_example.py

    # Point at a specific Redis instance:
    python examples/redis_memory_client_example.py --redis-url redis://localhost:6379/0

    # Or via environment variable (CLI flag wins):
    #   AI_VIBE_MEMORY_REDIS_URL=redis://localhost:6379/0
"""

from __future__ import annotations

import argparse
import os
import sys

from ai_vibe_coding.memory_store import MemoryStore

REDIS_URL_ENV = "AI_VIBE_MEMORY_REDIS_URL"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def run_demo(redis_url: str) -> dict:
    """Prove memory persists via Redis; return a summary dict.

    Args:
        redis_url: Redis connection URL (redis://host:port/db).

    Returns:
        A dict summarizing what was stored, retrieved, and left behind.
    """
    print(f"=== Redis memory client demo (url: {redis_url}) ===")

    # --- Session 1: store + search -------------------------------------
    print("\n[Session 1] storing memories via Redis...")
    store = MemoryStore(redis_url=redis_url)

    id_redis = store.store(
        "Redis is an in-memory data store used as cache, database, and broker",
        metadata={"topic": "redis"},
        importance=0.9,
    )["id"]
    id_hash = store.store(
        "Consistent hashing distributes keys across Redis cluster nodes",
        metadata={"topic": "redis-cluster"},
        ttl_seconds=3600,
        importance=0.7,
    )["id"]
    id_sentinel = store.store(
        "Redis Sentinel provides high availability for Redis deployments",
        importance=0.8,
    )["id"]
    print(f"  stored: {id_redis}, {id_hash}, {id_sentinel}")

    hits1 = store.search("redis persistence", limit=3)
    print(f"\n[Session 1] search 'redis persistence' -> {hits1['total']} hit(s)")
    for hit in hits1["results"]:
        print(f"  {hit['score']:.3f}  {hit['content'][:60]}")

    print("\n[Session 1] closing store (simulated process restart)...")
    store.close()

    # --- Session 2: reopen the same Redis, retrieve + search -----------
    print("\n[Session 2] reopening the same Redis backend...")
    store2 = MemoryStore(redis_url=redis_url)
    retrieved = store2.retrieve(id_redis)
    assert retrieved["content"].startswith("Redis"), "content mismatch across restart"
    print(f"  retrieved session-1 memory: {retrieved['content'][:60]}")
    print(f"  metadata survived: {retrieved['metadata']}")

    hits2 = store2.search("cluster", limit=3)
    print(f"\n[Session 2] search 'cluster' -> {hits2['total']} hit(s)")

    forgotten = store2.forget(id_sentinel)
    print(f"\n[Session 2] forgot one memory: {forgotten}")

    stats = store2.stats()
    print(f"\n[Session 2] stats: {stats}")
    store2.close()

    return {
        "stored": [id_redis, id_hash, id_sentinel],
        "retrieved": retrieved["content"],
        "search_results_session_2": [r["id"] for r in hits2["results"]],
        "forgotten": forgotten["forgotten"],
        "total_after_forget": stats["total"],
    }


def main() -> None:
    """CLI entry point: parse --redis-url, run the demo, print the summary."""
    parser = argparse.ArgumentParser(
        description="Demo the Redis-backed agent memory store."
    )
    parser.add_argument(
        "--redis-url",
        default=os.environ.get(REDIS_URL_ENV, DEFAULT_REDIS_URL),
        help=f"Redis URL (default: {DEFAULT_REDIS_URL})",
    )
    args = parser.parse_args()

    try:
        summary = run_demo(args.redis_url)
    except Exception as exc:  # noqa: BLE001
        print(f"\nERROR: {exc}", file=sys.stderr)
        print(
            "Make sure a Redis server is running at the specified URL.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"\n=== Summary: {summary}")


if __name__ == "__main__":
    main()
