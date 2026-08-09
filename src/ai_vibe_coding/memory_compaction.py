"""Compaction & knowledge-distillation engine for agent memory (v0.14.0).

Contract: analysis/analysis-brief.md §4.4–4.5.

All public functions are deterministic, dependency-free pure functions.
Stateful orchestration lives in ``MemoryStore.compact`` /
``MemoryStore.impact_decay`` — this module contains the *policy*, not the
*storage*.
"""

from __future__ import annotations

from datetime import UTC, datetime
from math import floor

# ── defaults (locked by TestMemoryCompactionEngineInterface) ───────────

DEFAULT_COMPACTION_AGE_DAYS: float = 30
DEFAULT_COMPACTION_IMPORTANCE_THRESHOLD: float = 0.3
DEFAULT_MERGE_THRESHOLD: float = 0.82
DEFAULT_DECAY_DAYS: float = 7
DEFAULT_DECAY_HALFLIFE: float = 2.0
DEFAULT_MIN_IMPORTANCE: float = 0.1


# ── summariser (deterministic, no LLM) ────────────────────────────────

def summarize(
    sources: list[str],
    *,
    source_ids: list[str] | None = None,
    created_range: tuple[str, str] | None = None,
) -> str:
    """Concatenate deduplicated source lines into a compact summary string.

    The output is a deterministic template: non-duplicate lines joined by
    newlines, prefixed with a header naming the source count and date
    range when provided.  No LLM call is made.

    Args:
        sources: Raw content strings to summarise.
        source_ids: Optional identifiers (names/ids) for provenance header.
        created_range: Optional (earliest, latest) ISO timestamps for the
            header.

    Returns:
        A single summary string containing every distinct source line.
    """
    if not sources:
        return ""

    # Deduplicate while preserving insertion order
    seen: set[str] = set()
    unique: list[str] = []
    for line in sources:
        if line not in seen:
            seen.add(line)
            unique.append(line)

    parts: list[str] = []

    # Header
    id_count = len(source_ids) if source_ids else 0
    header_bits: list[str] = [f"Distilled from {id_count} source(s)"]
    if created_range is not None and len(created_range) == 2:
        header_bits.append(f"date range: {created_range[0]} → {created_range[1]}")
    parts.append(" | ".join(header_bits))

    # Body
    parts.extend(unique)
    return "\n".join(parts)


# ── cluster selection ──────────────────────────────────────────────────

def _parse_ts(ts: str | datetime) -> datetime:
    """Parse an ISO timestamp string to a tz-aware datetime."""
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=UTC)
    return datetime.fromisoformat(ts)


def _age_days(created_at: str | datetime, now: str | datetime) -> float:
    """Return the age of a memory in whole days."""
    created = _parse_ts(created_at)
    current = _parse_ts(now)
    return (current - created).total_seconds() / 86400.0


def select_clusters(
    memories: list[dict],
    *,
    now: str | datetime,
    age_days: float = DEFAULT_COMPACTION_AGE_DAYS,
    importance_threshold: float = DEFAULT_COMPACTION_IMPORTANCE_THRESHOLD,
    merge_threshold: float = DEFAULT_MERGE_THRESHOLD,
) -> list[list[dict]]:
    """Select clusters of stale, low-importance memories for distillation.

    A memory qualifies when:
      - ``status`` is ``'active'`` (or missing, treated as active),
      - its age (days since ``created_at``) exceeds ``age_days``, and
      - its ``importance`` is strictly below ``importance_threshold``.

    Qualified memories are grouped by embedding cosine similarity ≥
    ``merge_threshold`` using the ``embedding`` field (when present).

    Args:
        memories: Row dicts from ``list_memories(include_archived=False)``.
        now: Current time (ISO string or datetime).
        age_days: Minimum age (days) for compaction eligibility.
        importance_threshold: Memories at or above this importance are kept.
        merge_threshold: Cosine similarity threshold for clustering.

    Returns:
        A list of clusters, where each cluster is a list of memory dicts.
    """
    # Import here to avoid circular dependency at module level
    from ai_vibe_coding.memory_embedding import cosine_similarity, deserialize_vector

    now_dt = _parse_ts(now)

    # Filter to stale low-importance active memories
    candidates: list[dict] = []
    for m in memories:
        status = m.get("status", "active")
        if status != "active":
            continue
        imp = m.get("importance", 0.5)
        if imp >= importance_threshold:
            continue
        age = _age_days(m["created_at"], now_dt)
        if age < age_days:
            continue
        candidates.append(m)

    if not candidates:
        return []

    # Simple greedy clustering: union-find style via index grouping
    # For each pair, check embedding cosine similarity
    n = len(candidates)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        emb_i = candidates[i].get("embedding")
        if emb_i is None:
            continue
        vec_i = deserialize_vector(emb_i)
        for j in range(i + 1, n):
            emb_j = candidates[j].get("embedding")
            if emb_j is None:
                # If either lacks embedding, treat as non-similar
                continue
            vec_j = deserialize_vector(emb_j)
            if cosine_similarity(vec_i, vec_j) >= merge_threshold:
                union(i, j)

    # Collect clusters
    groups: dict[int, list[dict]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(candidates[i])

    return list(groups.values())


# ── merge selection ────────────────────────────────────────────────────

def select_merges(
    memories: list[dict],
    *,
    threshold: float = DEFAULT_MERGE_THRESHOLD,
) -> list[tuple[str, list[str]]]:
    """Find pairs/groups of active memories that should be merged.

    Returns a list of ``(newest_id, [older_ids])`` tuples.  The newest
    entry (by ``created_at``) is kept; older duplicates are archived.

    Args:
        memories: Row dicts (may include ``status``; archived/distilled
            entries are skipped).
        threshold: Minimum cosine similarity to consider duplicates.

    Returns:
        Merge plan: list of ``(keeper_id, [archived_ids])`` tuples.
    """
    from ai_vibe_coding.memory_embedding import cosine_similarity, deserialize_vector

    # Filter to active entries with embeddings
    active: list[dict] = []
    for m in memories:
        if m.get("status", "active") != "active":
            continue
        if m.get("embedding") is None:
            continue
        active.append(m)

    if len(active) < 2:
        return []

    n = len(active)
    used = [False] * n
    merges: list[tuple[str, list[str]]] = []

    for i in range(n):
        if used[i]:
            continue
        emb_i = deserialize_vector(active[i]["embedding"])
        group: list[int] = [i]

        for j in range(i + 1, n):
            if used[j]:
                continue
            emb_j = deserialize_vector(active[j]["embedding"])
            if cosine_similarity(emb_i, emb_j) >= threshold:
                group.append(j)

        if len(group) < 2:
            continue

        # Mark all as used
        for idx in group:
            used[idx] = True

        # Keep newest (latest created_at), archive the rest
        group_entries = [active[idx] for idx in group]
        group_entries.sort(
            key=lambda m: _parse_ts(m["created_at"]),
            reverse=True,
        )
        keeper = group_entries[0]
        archived = [m["id"] for m in group_entries[1:]]
        merges.append((keeper["id"], archived))

    return merges


# ── decay ──────────────────────────────────────────────────────────────

def compute_decay(
    row: dict,
    now: str | datetime,
    *,
    decay_days: float = DEFAULT_DECAY_DAYS,
    halflife: float = DEFAULT_DECAY_HALFLIFE,
    min_importance: float = DEFAULT_MIN_IMPORTANCE,
) -> float:
    """Compute the new importance for a memory after time-based decay.

    Decay formula (spec §4.5):
        periods = floor((now - last_decayed_at | created_at) / decay_days)
        new_importance = max(min_importance,
                            importance * 0.5 ** (periods / halflife))

    Args:
        row: Memory dict with at least ``importance``, ``created_at``,
            and optionally ``last_decayed_at``.
        now: Current time (ISO string or datetime).
        decay_days: Duration of one decay period in days.
        halflife: Number of decay periods for importance to halve.
        min_importance: Floor for importance; never decays below this.

    Returns:
        The new importance value (float).
    """
    now_dt = _parse_ts(now)
    importance = row.get("importance", 0.5)
    last_decayed = row.get("last_decayed_at") or row.get("created_at") or ""
    base = _parse_ts(last_decayed)

    elapsed_days = (now_dt - base).total_seconds() / 86400.0
    periods = floor(elapsed_days / decay_days)

    if periods <= 0:
        return importance

    new_importance = importance * (0.5 ** (periods / halflife))
    return max(min_importance, new_importance)


def build_decay_plan(
    memories: list[dict],
    *,
    now: str | datetime,
    decay_days: float = DEFAULT_DECAY_DAYS,
    halflife: float = DEFAULT_DECAY_HALFLIFE,
    min_importance: float = DEFAULT_MIN_IMPORTANCE,
    compaction_importance_threshold: float = DEFAULT_COMPACTION_IMPORTANCE_THRESHOLD,
) -> list[dict]:
    """Build a list of decay actions (dry-run planning).

    Only active, non-archived memories whose importance would actually
    decrease are included.

    Args:
        memories: Row dicts from ``list_memories(include_archived=False)``.
        now: Current time (ISO string or datetime).
        decay_days: Duration of one decay period in days.
        halflife: Number of periods for importance to halve.
        min_importance: Floor for importance.
        compaction_importance_threshold: Threshold below which memories
            become compaction-eligible (reported in the plan).

    Returns:
        A list of dicts, each with keys: ``memory_id``, ``old_importance``,
        ``new_importance``, ``eligible_for_compaction``.
    """
    plan: list[dict] = []
    for m in memories:
        if m.get("status", "active") != "active":
            continue
        old_imp = m.get("importance", 0.5)
        new_imp = compute_decay(
            m, now,
            decay_days=decay_days,
            halflife=halflife,
            min_importance=min_importance,
        )
        if new_imp < old_imp:
            plan.append({
                "memory_id": m["id"],
                "old_importance": old_imp,
                "new_importance": new_imp,
                "eligible_for_compaction": new_imp < compaction_importance_threshold,
            })
    return plan


# ── full compaction plan builder ───────────────────────────────────────

def build_plan(
    memories: list[dict],
    *,
    now: str | datetime,
    age_days: float = DEFAULT_COMPACTION_AGE_DAYS,
    importance_threshold: float = DEFAULT_COMPACTION_IMPORTANCE_THRESHOLD,
    merge_threshold: float = DEFAULT_MERGE_THRESHOLD,
) -> dict:
    """Build a dry-run compaction plan (no mutations).

    Combines ``select_clusters`` (distill candidates) and ``select_merges``
    (merge candidates) into a single plan dict.

    Args:
        memories: Full list of active memory row dicts.
        now: Current time.
        age_days: Minimum age for compaction eligibility.
        importance_threshold: Importance below which compaction is considered.
        merge_threshold: Cosine similarity threshold for merging.

    Returns:
        A dict with keys: ``candidate_distill_clusters``, ``candidate_merges``,
        ``cluster_count``, ``merge_count``, ``candidate_memory_ids``, ``dry_run``.
    """
    clusters = select_clusters(
        memories,
        now=now,
        age_days=age_days,
        importance_threshold=importance_threshold,
        merge_threshold=merge_threshold,
    )
    merges = select_merges(memories, threshold=merge_threshold)

    all_ids: list[str] = []
    for cluster in clusters:
        for m in cluster:
            all_ids.append(m["id"])
    for keeper_id, older_ids in merges:
        if keeper_id not in all_ids:
            all_ids.append(keeper_id)
        for oid in older_ids:
            if oid not in all_ids:
                all_ids.append(oid)

    return {
        "candidate_distill_clusters": clusters,
        "candidate_merges": merges,
        "cluster_count": len(clusters),
        "merge_count": len(merges),
        "candidate_memory_ids": all_ids,
        "dry_run": True,
    }
