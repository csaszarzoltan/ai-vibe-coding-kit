"""Memory client example — cross-session store/retrieve/search demo (spec §8).

Proves that memories stored through the MCP memory server's core
``MemoryStore`` persist across a simulated agent restart: session 1 stores
and searches, the store is closed, then session 2 reopens the same SQLite
file and retrieves the earlier memories.

Usage:
    python examples/memory_client_example.py --db /tmp/memory-demo.db
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_vibe_coding.memory_store import DEFAULT_DB_PATH, MemoryStore


def run_demo(db_path: str | Path = DEFAULT_DB_PATH) -> dict:
    """Prove memory persists across sessions; return a summary dict.

    Args:
        db_path: SQLite file to store memories in.

    Returns:
        A dict summarizing what was stored, retrieved and left behind.
    """
    print(f"=== Memory client demo (db: {db_path}) ===")

    # --- Session 1: store + search -------------------------------------
    print("\n[Session 1] storing memories...")
    store = MemoryStore(db_path)
    id_sqlite = store.store(
        "SQLite is a file-backed relational database with WAL journaling",
        metadata={"topic": "sqlite"},
        importance=0.9,
    )["id"]
    id_mcp = store.store(
        "MCP lets agents expose tools over stdio",
        metadata={"topic": "mcp"},
        ttl_seconds=3600,
        importance=0.7,
    )["id"]
    id_embeddings = store.store(
        "vector databases index embeddings for semantic search",
        importance=0.8,
    )["id"]
    print(f"  stored: {id_sqlite}, {id_mcp}, {id_embeddings}")

    hits1 = store.search("sqlite persistence", limit=3)
    print(f"\n[Session 1] search 'sqlite persistence' -> {hits1['total']} hit(s)")
    for hit in hits1["results"]:
        print(f"  {hit['score']:.3f}  {hit['content'][:60]}")

    print("\n[Session 1] closing store (simulated agent restart)...")
    store.close()

    # --- Session 2: reopen the same file, retrieve + search -------------
    print("\n[Session 2] reopening the same database file...")
    store2 = MemoryStore(db_path)
    retrieved = store2.retrieve(id_sqlite)
    assert retrieved["content"].startswith("SQLite"), "content mismatch across restart"
    print(f"  retrieved session-1 memory: {retrieved['content'][:60]}")
    print(f"  metadata survived: {retrieved['metadata']}")

    hits2 = store2.search("embeddings", limit=3)
    print(f"\n[Session 2] search 'embeddings' -> {hits2['total']} hit(s)")

    forgotten = store2.forget(id_embeddings)
    print(f"\n[Session 2] forgot one memory: {forgotten}")

    stats = store2.stats()
    print(f"\n[Session 2] stats: {stats}")
    store2.close()

    return {
        "stored": [id_sqlite, id_mcp, id_embeddings],
        "retrieved": retrieved["content"],
        "search_results_session_2": [r["id"] for r in hits2["results"]],
        "forgotten": forgotten["forgotten"],
        "total_after_forget": stats["total"],
    }


def main() -> None:
    """CLI entry point: parse --db, run the demo, print the summary."""
    parser = argparse.ArgumentParser(
        description="Demo the MCP memory server's cross-session persistence."
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"SQLite database path (default: {DEFAULT_DB_PATH})",
    )
    args = parser.parse_args()
    summary = run_demo(args.db)
    print(f"\n=== Summary: {summary}")


if __name__ == "__main__":
    main()
