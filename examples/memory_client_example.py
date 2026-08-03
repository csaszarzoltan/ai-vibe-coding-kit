"""Pre-development stub for the memory client cross-session demo.

Contract: analysis/memory-architecture.md §8.

Public API (interface tests pass immediately against this stub):
    run_demo(db_path) — two-session store/retrieve/search/forget demo; returns
                        a summary dict
    main()            — argparse entry point (--db), calls run_demo

run_demo raises NotImplementedError until the developer implements the
cross-session demo per the spec.
"""

from __future__ import annotations

from pathlib import Path

from ai_vibe_coding.memory_store import DEFAULT_DB_PATH


def run_demo(db_path: str | Path = DEFAULT_DB_PATH) -> dict:
    """Prove memory persists across sessions; return a summary dict."""
    raise NotImplementedError("memory_client_example.run_demo not implemented yet")


def main() -> None:
    """CLI entry point: parse --db, run the demo."""
    raise NotImplementedError("memory_client_example.main not implemented yet")


if __name__ == "__main__":
    main()
