"""Memory Compaction & Knowledge Distillation Example.

Demonstrates the v0.14.0 compaction / knowledge-distillation feature:

  - ``compact(dry_run=True)``  — review the plan without mutating
  - ``compact(dry_run=False)`` — distill stale low-importance clusters into
    one distilled entry per cluster, archive the originals, merge
    near-duplicates (keep newest), and record a compaction_log row
  - ``impact_decay(dry_run=True / False)`` — decay importance over time
    (half-life curve, ``min_importance`` floor) and log decay events
  - ``memory_stats()`` — extended counters (distilled / archived / merged /
    decayed) plus the compaction log

Determinism: the example injects a ``now`` clock (the same FakeClock seam the
test suite uses) so the age-based eligibility is reproducible without waiting
30+ days. In real usage you call ``MemoryStore()`` with no clock and let
``compact()`` / ``impact_decay()`` use the system time.

Usage:
    python examples/compaction_client_example.py
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_vibe_coding.memory_store import MemoryStore  # noqa: E402


class _Clock:
    """Deterministic clock seam (same pattern as tests/test_memory_compaction.py)."""

    def __init__(self) -> None:
        self.current = datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


def main() -> None:
    # -- setup ------------------------------------------------------------
    clock = _Clock()
    store = MemoryStore(":memory:", now=clock)

    # Three stale, low-importance episodic memories about the same event.
    # After the clock advances past compaction_age_days (default 30) they
    # become distillation candidates; two of them are near-duplicates
    # (cosine similarity >= merge_threshold, default 0.82) and also merge.
    for content in (
        "The 2026-06-24 standup decided the pricing agent owns the DeepSeek "
        "comparison report",
        "Meeting on 2026-06-24: pricing agent is responsible for the DeepSeek "
        "cost report",
        "The report from the 2026-06-24 standup is owned by the pricing agent",
    ):
        store.store(content, metadata={"type": "episodic"}, importance=0.2)

    # A fresh, high-importance memory must never be compacted.
    store.store(
        "Active decision: use the Redis backend in production",
        metadata={"type": "semantic"},
        importance=0.9,
    )

    # -- 1. dry-run plan --------------------------------------------------
    clock.advance(45 * 86400)  # age everything 45 days
    plan = store.compact(dry_run=True)
    print("dry-run plan:")
    print(f"  clusters={plan['cluster_count']} merges={plan['merge_count']}")
    print(f"  candidates={sorted(plan['candidate_memory_ids'])}")
    print(f"  no mutations: total={store.stats()['total']}")

    # -- 2. apply ---------------------------------------------------------
    result = store.compact(dry_run=False)
    print("\napplied compaction:")
    print(
        f"  distilled={result['distilled']} archived={result['archived']} "
        f"merged={result['merged']} skipped={result['skipped']}"
    )

    # Re-running is idempotent: already-archived rows are skipped, no new
    # distilled entries, no double-archiving.
    again = store.compact(dry_run=False)
    print(f"  re-run: distilled={again['distilled']} skipped={again['skipped']}")

    # The distilled entry is searchable; archived originals are not.
    hits = store.search("standup pricing agent DeepSeek report", limit=5)
    print(f"  search hits: {hits['total']} total")
    if hits["results"]:
        print(f"  top hit: {hits['results'][0]['content'][:60]}...")

    # -- 3. importance decay ----------------------------------------------
    store.store(  # high-importance legacy decision
        "Legacy decision recorded for the Redis rollout",
        metadata={"type": "semantic"},
        importance=1.0,
    )
    clock.advance(60 * 86400)  # 8 full decay periods (7 days each)
    dec_plan = store.impact_decay(dry_run=True)
    print(
        f"\ndecay plan: {dec_plan['decayed']} decayed, "
        f"{dec_plan['eligible_for_compaction']} now compaction-eligible"
    )
    dec_res = store.impact_decay(dry_run=False)
    print(
        f"decay applied: {dec_res['decayed']} decayed, "
        f"floor={dec_res['min_importance']}"
    )

    # -- 4. extended stats ------------------------------------------------
    stats = store.memory_stats()
    print("\nmemory_stats():")
    for key in (
        "distilled_count",
        "archived_count",
        "merged_count",
        "decayed_count",
        "compact_runs",
        "decay_events",
    ):
        print(f"  {key}={stats[key]}")
    store.close()


if __name__ == "__main__":
    main()
