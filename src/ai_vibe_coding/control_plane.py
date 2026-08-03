# ruff: noqa: E501
"""Durable application layer for the AI engineering control plane.

The module intentionally depends only on the standard library. It owns workflow
invariants and persistence; HTTP and HTML delivery live in separate modules.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import secrets
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


class PermissionDenied(RuntimeError):
    """Raised when a fail-closed policy rejects an operation."""


class InvalidTransition(RuntimeError):
    """Raised when a workflow transition violates its state machine."""


_SECRET_KEYS = {"api_key", "authorization", "token", "secret", "password"}
_PAGES = {
    "providers": (
        "Provider control plane",
        "Route models, issue scoped keys, and enforce quotas.",
    ),
    "traces": (
        "Trace explorer",
        "Reconstruct requests, retries, tools, latency, and cost.",
    ),
    "evaluations": (
        "Evaluation studio",
        "Compare candidates and block quality regressions.",
    ),
    "security": (
        "AI security center",
        "Test prompt, data, tool, and agency boundaries.",
    ),
    "budgets": (
        "Budget guardrails",
        "Forecast and enforce spend before a request runs.",
    ),
    "agents": (
        "Agent debugger",
        "Inspect checkpoints and resume approved workflows safely.",
    ),
}


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: "[REDACTED]" if k.lower() in _SECRET_KEYS else _redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(
            r"(?i)(token|api[_-]?key|secret|password)=\S+", r"\1=[REDACTED]", value
        )
        value = re.sub(r"(?i)bearer\s+\S+", "Bearer [REDACTED]", value)
    return value


class ControlPlane:
    """Transactional repository and domain service for six control-plane workflows."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        with self._db() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS providers(id TEXT PRIMARY KEY, models TEXT, state TEXT, updated REAL);
                CREATE TABLE IF NOT EXISTS virtual_keys(id TEXT PRIMARY KEY, digest TEXT UNIQUE, tenant TEXT, models TEXT, budget REAL, spent REAL, state TEXT);
                CREATE TABLE IF NOT EXISTS spend(id TEXT PRIMARY KEY, key_id TEXT, amount REAL, run_id TEXT UNIQUE, created REAL);
                CREATE TABLE IF NOT EXISTS traces(id TEXT PRIMARY KEY, tenant TEXT, name TEXT, attributes TEXT, state TEXT, created REAL);
                CREATE TABLE IF NOT EXISTS spans(id TEXT PRIMARY KEY, trace_id TEXT, kind TEXT, state TEXT, duration_ms REAL, cost REAL, data TEXT, created REAL);
                CREATE TABLE IF NOT EXISTS experiments(id TEXT PRIMARY KEY, candidate TEXT, thresholds TEXT, state TEXT, created REAL);
                CREATE TABLE IF NOT EXISTS scores(id TEXT PRIMARY KEY, experiment_id TEXT, metric TEXT, value REAL, UNIQUE(experiment_id,metric));
                CREATE TABLE IF NOT EXISTS scans(id TEXT PRIMARY KEY, target TEXT, profiles TEXT, state TEXT, created REAL);
                CREATE TABLE IF NOT EXISTS findings(id TEXT PRIMARY KEY, scan_id TEXT, category TEXT, severity TEXT, evidence TEXT, blocking INTEGER);
                CREATE TABLE IF NOT EXISTS agent_runs(id TEXT PRIMARY KEY, workflow TEXT, steps TEXT, state TEXT, created REAL);
                CREATE TABLE IF NOT EXISTS checkpoints(id TEXT PRIMARY KEY, run_id TEXT, step TEXT, state TEXT, output TEXT, requester TEXT, reviewer TEXT, UNIQUE(run_id,step));
                CREATE TABLE IF NOT EXISTS idempotency(key TEXT PRIMARY KEY, resource_id TEXT, created REAL);
                """
            )

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _idem(self, key: str | None, factory: Any) -> str:
        if not key:
            return factory()
        with self._db() as db:
            row = db.execute(
                "SELECT resource_id FROM idempotency WHERE key=?", (key,)
            ).fetchone()
            if row:
                return str(row[0])
        resource = factory()
        with self._db() as db:
            db.execute(
                "INSERT INTO idempotency VALUES (?,?,?)", (key, resource, time.time())
            )
        return resource

    def upsert_provider(
        self, provider_id: str, models: list[str], *, enabled: bool
    ) -> None:
        clean = sorted({m.strip() for m in models if m.strip()})
        if not provider_id.strip() or not clean:
            raise ValueError("PROVIDER_INPUT_INVALID")
        with self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO providers VALUES (?,?,?,?)",
                (
                    provider_id,
                    json.dumps(clean),
                    "ACTIVE" if enabled else "DISABLED",
                    time.time(),
                ),
            )

    def create_virtual_key(self, tenant: str, models: list[str], budget: float) -> str:
        if not tenant or not models or budget < 0:
            raise ValueError("VIRTUAL_KEY_INPUT_INVALID")
        raw = f"avk_{secrets.token_urlsafe(24)}"
        with self._db() as db:
            db.execute(
                "INSERT INTO virtual_keys VALUES (?,?,?,?,?,0,'ACTIVE')",
                (
                    _id("key"),
                    hashlib.sha256(raw.encode()).hexdigest(),
                    tenant,
                    json.dumps(sorted(set(models))),
                    budget,
                ),
            )
        return raw

    def _key(self, raw_key: str) -> sqlite3.Row:
        digest = hashlib.sha256(raw_key.encode()).hexdigest()
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM virtual_keys WHERE digest=?", (digest,)
            ).fetchone()
        if not row or row["state"] != "ACTIVE":
            raise PermissionDenied("KEY_INVALID")
        return row

    def authorize(
        self, raw_key: str, model: str, *, estimated_cost: float
    ) -> dict[str, Any]:
        row = self._key(raw_key)
        if model not in json.loads(row["models"]):
            raise PermissionDenied("MODEL_NOT_ALLOWED")
        if estimated_cost < 0 or row["spent"] + estimated_cost > row["budget"]:
            raise PermissionDenied("BUDGET_EXCEEDED")
        return {
            "tenant": row["tenant"],
            "remaining": round(row["budget"] - row["spent"], 6),
        }

    def record_spend(self, raw_key: str, amount: float, run_id: str) -> None:
        row = self._key(raw_key)
        if amount < 0:
            raise ValueError("SPEND_INVALID")
        with self._db() as db:
            try:
                db.execute(
                    "INSERT INTO spend VALUES (?,?,?,?,?)",
                    (_id("spend"), row["id"], amount, run_id, time.time()),
                )
            except sqlite3.IntegrityError:
                return
            db.execute(
                "UPDATE virtual_keys SET spent=spent+? WHERE id=?", (amount, row["id"])
            )

    def budget_summary(self, raw_key: str) -> dict[str, float | str]:
        row = self._key(raw_key)
        return {
            "tenant": row["tenant"],
            "budget": row["budget"],
            "spent": row["spent"],
            "remaining": round(row["budget"] - row["spent"], 6),
        }

    def start_trace(
        self,
        tenant: str,
        name: str,
        attributes: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> str:
        def create() -> str:
            trace_id = _id("trace")
            with self._db() as db:
                db.execute(
                    "INSERT INTO traces VALUES (?,?,?,?,?,?)",
                    (
                        trace_id,
                        tenant,
                        name,
                        json.dumps(_redact(attributes), sort_keys=True),
                        "OPEN",
                        time.time(),
                    ),
                )
            return trace_id

        return self._idem(idempotency_key, create)

    def add_span(
        self,
        trace_id: str,
        kind: str,
        state: str,
        duration_ms: float,
        cost: float,
        data: dict[str, Any],
    ) -> str:
        if (
            state not in {"OPEN", "COMPLETE", "FAILED", "PARTIAL"}
            or duration_ms < 0
            or cost < 0
        ):
            raise ValueError("SPAN_INPUT_INVALID")
        span_id = _id("span")
        with self._db() as db:
            if not db.execute(
                "SELECT 1 FROM traces WHERE id=?", (trace_id,)
            ).fetchone():
                raise KeyError(trace_id)
            db.execute(
                "INSERT INTO spans VALUES (?,?,?,?,?,?,?,?)",
                (
                    span_id,
                    trace_id,
                    kind,
                    state,
                    duration_ms,
                    cost,
                    json.dumps(_redact(data), sort_keys=True),
                    time.time(),
                ),
            )
            if state == "FAILED":
                db.execute("UPDATE traces SET state='PARTIAL' WHERE id=?", (trace_id,))
        return span_id

    def trace(self, trace_id: str) -> dict[str, Any]:
        with self._db() as db:
            row = db.execute("SELECT * FROM traces WHERE id=?", (trace_id,)).fetchone()
            if not row:
                raise KeyError(trace_id)
            spans = [
                dict(x)
                for x in db.execute(
                    "SELECT * FROM spans WHERE trace_id=? ORDER BY created", (trace_id,)
                )
            ]
        result = dict(row)
        result["attributes"] = json.loads(result["attributes"])
        for span in spans:
            span["data"] = json.loads(span["data"])
        result["spans"] = spans
        result["cost"] = round(sum(x["cost"] for x in spans), 6)
        return result

    def export_trace(self, trace_id: str) -> str:
        return json.dumps(self.trace(trace_id), sort_keys=True)

    def create_experiment(self, candidate: str, thresholds: dict[str, float]) -> str:
        if not candidate or not thresholds:
            raise ValueError("EXPERIMENT_INPUT_INVALID")
        experiment_id = _id("exp")
        with self._db() as db:
            db.execute(
                "INSERT INTO experiments VALUES (?,?,?,'RUNNING',?)",
                (
                    experiment_id,
                    candidate,
                    json.dumps(thresholds, sort_keys=True),
                    time.time(),
                ),
            )
        return experiment_id

    def record_score(self, experiment_id: str, metric: str, value: float) -> None:
        with self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO scores VALUES (?,?,?,?)",
                (_id("score"), experiment_id, metric, value),
            )

    def evaluate_gate(self, experiment_id: str) -> dict[str, Any]:
        with self._db() as db:
            exp = db.execute(
                "SELECT * FROM experiments WHERE id=?", (experiment_id,)
            ).fetchone()
            if not exp:
                raise KeyError(experiment_id)
            scores = {
                x[0]: x[1]
                for x in db.execute(
                    "SELECT metric,value FROM scores WHERE experiment_id=?",
                    (experiment_id,),
                )
            }
            thresholds = json.loads(exp["thresholds"])
            violations = sorted(
                k
                for k, target in thresholds.items()
                if k not in scores
                or (
                    scores[k] > target
                    if "latency" in k or "cost" in k
                    else scores[k] < target
                )
            )
            state = "FAILED" if violations else "PASSED"
            db.execute(
                "UPDATE experiments SET state=? WHERE id=?", (state, experiment_id)
            )
        return {
            "id": experiment_id,
            "state": state,
            "violations": violations,
            "scores": scores,
        }

    def start_security_scan(self, target: str, profiles: list[str]) -> str:
        if not target or not profiles:
            raise ValueError("SCAN_INPUT_INVALID")
        scan_id = _id("scan")
        with self._db() as db:
            db.execute(
                "INSERT INTO scans VALUES (?,?,?,'SCANNING',?)",
                (scan_id, target, json.dumps(profiles), time.time()),
            )
        return scan_id

    def record_finding(
        self,
        scan_id: str,
        category: str,
        severity: str,
        evidence: str,
        *,
        blocking: bool,
    ) -> str:
        finding_id = _id("finding")
        safe = _redact(evidence)
        with self._db() as db:
            db.execute(
                "INSERT INTO findings VALUES (?,?,?,?,?,?)",
                (finding_id, scan_id, category, severity, safe, int(blocking)),
            )
            if blocking:
                db.execute("UPDATE scans SET state='FAILED' WHERE id=?", (scan_id,))
        return finding_id

    def security_report(self, scan_id: str) -> dict[str, Any]:
        with self._db() as db:
            scan = db.execute("SELECT * FROM scans WHERE id=?", (scan_id,)).fetchone()
            if not scan:
                raise KeyError(scan_id)
            findings = [
                dict(x)
                for x in db.execute(
                    "SELECT category,severity,evidence,blocking FROM findings WHERE scan_id=?",
                    (scan_id,),
                )
            ]
        result = dict(scan)
        result["profiles"] = json.loads(result["profiles"])
        result["findings"] = findings
        return result

    def create_agent_run(self, workflow: str, steps: list[str]) -> str:
        clean = list(dict.fromkeys(steps))
        if not workflow or not clean:
            raise ValueError("AGENT_RUN_INPUT_INVALID")
        run_id = _id("run")
        with self._db() as db:
            db.execute(
                "INSERT INTO agent_runs VALUES (?,?,?,'RUNNING',?)",
                (run_id, workflow, json.dumps(clean), time.time()),
            )
        return run_id

    def complete_agent_step(
        self, run_id: str, step: str, output: dict[str, Any]
    ) -> None:
        with self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO checkpoints VALUES (?,?,?,?,?,?,?)",
                (
                    _id("cp"),
                    run_id,
                    step,
                    "COMPLETED",
                    json.dumps(_redact(output)),
                    None,
                    None,
                ),
            )

    def request_agent_approval(self, run_id: str, step: str, requester: str) -> None:
        with self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO checkpoints VALUES (?,?,?,?,?,?,?)",
                (_id("cp"), run_id, step, "WAITING_APPROVAL", "{}", requester, None),
            )
            db.execute(
                "UPDATE agent_runs SET state='WAITING_APPROVAL' WHERE id=?", (run_id,)
            )

    def decide_agent_approval(
        self, run_id: str, step: str, reviewer: str, *, approved: bool
    ) -> None:
        with self._db() as db:
            row = db.execute(
                "SELECT requester,state FROM checkpoints WHERE run_id=? AND step=?",
                (run_id, step),
            ).fetchone()
            if not row or row["state"] != "WAITING_APPROVAL":
                raise InvalidTransition("APPROVAL_NOT_PENDING")
            if row["requester"] == reviewer:
                raise PermissionDenied("SELF_APPROVAL_DENIED")
            state = "APPROVED" if approved else "REJECTED"
            db.execute(
                "UPDATE checkpoints SET state=?,reviewer=? WHERE run_id=? AND step=?",
                (state, reviewer, run_id, step),
            )
            db.execute(
                "UPDATE agent_runs SET state=? WHERE id=?",
                ("PAUSED" if approved else "FAILED", run_id),
            )

    def resume_agent_run(self, run_id: str) -> list[str]:
        with self._db() as db:
            run = db.execute(
                "SELECT * FROM agent_runs WHERE id=?", (run_id,)
            ).fetchone()
            if not run:
                raise KeyError(run_id)
            checkpoints = {
                x[0]: x[1]
                for x in db.execute(
                    "SELECT step,state FROM checkpoints WHERE run_id=?", (run_id,)
                )
            }
            remaining = [
                x
                for x in json.loads(run["steps"])
                if checkpoints.get(x) not in {"COMPLETED", "APPROVED"}
            ]
            db.execute(
                "UPDATE agent_runs SET state=? WHERE id=?",
                ("COMPLETED" if not remaining else "RUNNING", run_id),
            )
        return remaining

    def list_rows(self, table: str, limit: int = 50) -> list[dict[str, Any]]:
        allowed = {
            "providers",
            "traces",
            "experiments",
            "scans",
            "virtual_keys",
            "agent_runs",
        }
        if table not in allowed:
            raise ValueError("TABLE_INVALID")
        limit = max(1, min(limit, 200))
        with self._db() as db:
            # table is allowlisted above; only the literal names in `allowed`
            # can reach this query string, and limit is a bound parameter.
            stmt = "SELECT * FROM " + table + " ORDER BY rowid DESC LIMIT ?"
            return [dict(x) for x in db.execute(stmt, (limit,))]


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render_console(page: str, control: ControlPlane) -> str:
    """Render an accessible server-side command-center view."""
    if page not in _PAGES:
        raise KeyError(page)
    title, subtitle = _PAGES[page]
    table = {
        "providers": "providers",
        "traces": "traces",
        "evaluations": "experiments",
        "security": "scans",
        "budgets": "virtual_keys",
        "agents": "agent_runs",
    }[page]
    rows = control.list_rows(table)
    nav = "".join(
        f'<a href="/control/{slug}"{" aria-current=page" if slug == page else ""}>{_esc(label)}</a>'
        for slug, (label, _) in _PAGES.items()
    )
    cards = "".join(
        f'<article><strong>{_esc(next(iter(row.values())))}</strong><p>{_esc(row.get("state", "Ready"))}</p><button type="button">Open details</button></article>'
        for row in rows
    )
    empty = (
        ""
        if cards
        else '<section class="empty"><h2>No items yet</h2><p>Create the first object or use the API to ingest one.</p><button class="primary">Get started</button></section>'
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{_esc(title)} | AI Vibe</title><link rel="stylesheet" href="/static/control.css"></head><body><a class="skip" href="#main">Skip to content</a><header><span class="logo">AV</span><div><strong>AI Vibe</strong><small>Command center</small></div><button aria-label="Open command palette">⌘ K</button></header><div class="shell"><nav aria-label="Control plane">{nav}</nav><main id="main" tabindex="-1"><div class="heading"><div><p class="eyebrow">Command center</p><h1>{_esc(title)}</h1><p>{_esc(subtitle)}</p></div><button class="primary">Create new</button></div><div class="status" aria-live="polite">Data is current</div><section class="metrics"><article><small>Objects</small><strong>{len(rows)}</strong></article><article><small>Health</small><strong>Operational</strong></article><article><small>Recovery</small><strong>Enabled</strong></article></section><section class="toolbar"><label>Search<input type="search" placeholder="Search this workspace"></label><label>Status<select><option>All states</option><option>Active</option><option>Failed</option></select></label></section><section class="cards">{cards}</section>{empty}<section class="recovery"><h2>Need to recover?</h2><p>The last stable state and successful sub-operations are preserved.</p><button>Try again</button><button>View audit trail</button></section></main></div></body></html>"""
