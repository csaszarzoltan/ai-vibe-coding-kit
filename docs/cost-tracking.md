# Cost Tracking Guide — Persistent Storage, Budget Alerts & Cost Comparison

Track, store, and alert on LLM API costs beyond in-memory aggregation. This guide covers SQLite-backed cost persistence, threshold-based budget alerts, and historical cost comparison — all from Python or the REST API.

---

## Overview

Three modules work together to turn ad-hoc cost tracking into a durable, queryable system:

| Module | Class / Functions | Purpose |
|--------|-------------------|---------|
| `cost_store.py` | `SqliteCostStore`, `CostPricingTable` | SQLite persistence for cost records, daily rollups, latency percentiles |
| `budget_alert.py` | `BudgetAlertEngine`, `BudgetConfig`, `AlertThreshold` | Threshold-based alerting on cost/tokens/latency |
| `cost_comparison.py` | `compare_actual_costs`, `compare_estimated_vs_actual`, `get_cost_trend` | Historical cost analysis and trend reporting |

The existing `CostTracker` extends seamlessly — call `set_store(store)` to delegate queries to SQLite while keeping in-memory aggregation for real-time use.

---

## 1. SQLite Cost Store

### 1.1 Quick Start

```python
from ai_vibe_coding.cost_store import SqliteCostStore

store = SqliteCostStore("llm_costs.db")

store.record_request(
    provider="openai",
    model="gpt-4",
    input_tokens=500,
    output_tokens=200,
    cost_usd=0.0270,
    latency_ms=1200.0,
    session_id="session-abc",
    tags={"project": "docs", "user": "zoltan"},
)

# Daily rollup
rollup = store.run_daily_rollup()
print(f"Rolled up {rollup['dates_rolled_up']} date(s)")
```

### 1.2 Database Schema

The SQLite database creates these tables automatically on first use:

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `cost_log` | Individual API call records | provider, model, tokens, cost_usd, latency_ms, session_id, tags, created_at |
| `daily_rollup` | Pre-computed daily aggregates | date, total_cost, total_tokens, request_count, avg_latency_ms |

Indexes on `provider`, `model`, `created_at`, and `session_id` for fast queries.

### 1.3 Querying Cost Data

```python
# Total cost with date/provider filters
total = store.get_total_cost(
    start_date="2026-07-01",
    end_date="2026-07-30",
    provider="openai",
)
print(f"OpenAI spend (July): ${total:.4f}")

# Daily breakdown
daily = store.get_daily_rollup(
    start_date="2026-07-01",
    end_date="2026-07-30",
)
for d in daily:
    print(f"{d['date']}: ${d['total_cost']:.4f} ({d['request_count']} calls, avg {d['avg_latency_ms']:.0f}ms)")

# Provider breakdown
for row in store.get_cost_by_provider():
    print(f"{row['provider']:12s} ${row['total_cost']:.4f}  {row['total_tokens']:>8} tokens  {row['request_count']:>4} calls")

# Model breakdown
for row in store.get_cost_by_model():
    print(f"{row['model']:20s} ${row['total_cost']:.4f}")

# User/session breakdown
for row in store.get_cost_by_user():
    print(f"{row['session_id']:20s} ${row['total_cost']:.4f}")

# Latency percentiles
p50 = store.get_latency_percentiles(percentile=50.0)
p95 = store.get_latency_percentiles(percentile=95.0, provider="openai")
p99 = store.get_latency_percentiles(percentile=99.0)
print(f"p50={p50:.0f}ms  p95={p95:.0f}ms  p99={p99:.0f}ms")
```

All query methods accept optional `start_date` / `end_date` ISO date strings and `provider` filters.

### 1.4 In-Memory Mode

Pass `:memory:` as the database path for testing or ephemeral workflows. The store keeps a single persistent connection so all queries in the same instance see consistent data.

```python
store = SqliteCostStore(":memory:")
```

### 1.5 Pricing Table

`CostPricingTable` manages per-model pricing rates in memory.

```python
from ai_vibe_coding.cost_store import CostPricingTable
from ai_vibe_coding.llm_wrapper import PRICING

pricing = CostPricingTable({})

# Seed from the built-in PRICING dict
count = pricing.seed_from_pricing_dict(PRICING)
print(f"Seeded {count} pricing entries")

# Get rate for a specific model
rate = pricing.get_pricing("openai", "gpt-4")
print(f"GPT-4: ${rate['input']:.4f}/1K in, ${rate['output']:.4f}/1K out")

# Add or update custom pricing
pricing.upsert_pricing("my-provider", "my-model", input_rate=0.005, output_rate=0.015)
```

---

## 2. Integrating with CostTracker

The in-memory `CostTracker` delegates to `SqliteCostStore` when connected:

```python
from ai_vibe_coding.cost_tracker import CostTracker
from ai_vibe_coding.cost_store import SqliteCostStore
from ai_vibe_coding import LLMClient

store = SqliteCostStore("costs.db")
tracker = CostTracker()
tracker.set_store(store)

client = LLMClient(provider="openai")

for prompt in prompts:
    response = client.chat(prompt)
    tracker.record(response)

# In-memory summary (always available)
summary = tracker.get_summary()
print(summary.to_table())

# Store-backed daily breakdown
daily = tracker.get_daily_cost(start_date="2026-07-01")
print(f"Daily costs: {len(daily)} days")

# Store-backed latency percentile
p95 = tracker.get_latency_percentiles(percentile=95.0)
print(f"p95 latency: {p95:.0f}ms")
```

When no store is set, `get_daily_cost()` and `get_latency_percentiles()` fall back to in-memory records.

---

## 3. Budget Alerts

### 3.1 Defining Budgets

#### In Code

```python
from ai_vibe_coding.budget_alert import (
    BudgetAlertEngine, BudgetConfig, AlertThreshold,
)

engine = BudgetAlertEngine()

config = BudgetConfig(
    name="monthly-llm-budget",
    max_budget=100.0,
    period="monthly",
    thresholds=[
        AlertThreshold(metric="cost", operator="gt",
                       value=80.0, label="80% spend warning"),
        AlertThreshold(metric="cost", operator="gt",
                       value=100.0, label="budget exceeded"),
        AlertThreshold(metric="tokens", operator="gt",
                       value=10_000_000, label="10M monthly tokens"),
    ],
    notification_channels=["console", "slack"],
    enabled=True,
)
engine.add_config(config)
```

#### From YAML

```yaml
# budgets.yaml
name: monthly-llm-budget
max_budget: 100.0
period: monthly
thresholds:
  - metric: cost
    operator: gt
    value: 80.0
    label: "80% spend warning"
  - metric: tokens
    operator: gt
    value: 10000000
    label: "10M monthly tokens"
notification_channels:
  - console
  - slack
enabled: true
```

```python
config = BudgetConfig.from_yaml("budgets.yaml")
engine.add_config(config)
```

### 3.2 Checking Budgets

```python
# With explicit spend value
alerts = engine.check_budgets(current_spend=85.0)

# Without argument — engine queries the cost store (or returns zeros)
alerts = engine.check_budgets()

for alert in alerts:
    print(f"[{alert['name']}] {alert['message']} at {alert['timestamp']}")
    # name, metric, actual, threshold, message, timestamp
```

### 3.3 Alert History

```python
history = engine.get_alert_history()
for entry in history:
    print(f"{entry['timestamp']} — {entry['name']}: {entry['message']}")
```

### 3.4 Alert Fields

Each alert dict has:

| Field | Type | Example |
|-------|------|---------|
| `name` | `str` | `"80% spend warning"` |
| `metric` | `str` | `"cost"` |
| `actual` | `float` | `85.0` |
| `threshold` | `float` | `80.0` |
| `message` | `str` | `"cost threshold breached: 85.0000 gt 80.0000"` |
| `timestamp` | `str` | `"2026-07-30T14:30:00"` |

---

## 4. Cost Comparison & Trends

### 4.1 Compare Actual Provider Costs

```python
from ai_vibe_coding.cost_comparison import compare_actual_costs

results = compare_actual_costs(
    start_date="2026-07-01",
    end_date="2026-07-30",
)
for r in results:
    print(f"{r['provider']:12s} ${r['total_cost']:.4f}  "
          f"({r['request_count']} calls, {r['cost_per_1k_tokens']:.6f}/1K tokens)")
```

Filter to specific providers:

```python
results = compare_actual_costs(
    providers=["openai", "anthropic", "deepseek"],
)
```

### 4.2 Estimated vs Actual

```python
from ai_vibe_coding.cost_comparison import compare_estimated_vs_actual

comparison = compare_estimated_vs_actual(start_date="2026-07-01")
for c in comparison:
    print(f"{c['provider']:12s} "
          f"est=${c['estimated_cost']:.4f}  actual=${c['actual_cost']:.4f}  "
          f"({c['difference_pct']:+.1f}%)")
```

Estimates use the `PRICING` dict with a 50/50 input/output token split. The percentage delta tells you how much your actual usage pattern differs from the per-1K-token estimate.

### 4.3 Cost Trends

```python
from ai_vibe_coding.cost_comparison import get_cost_trend

# Daily trend
daily = get_cost_trend(granularity="daily")
for t in daily:
    print(f"{t['period']}: ${t['total_cost']:.4f} ({t['request_count']} calls)")

# Weekly aggregation
weekly = get_cost_trend(granularity="weekly")
for t in weekly:
    print(f"Week {t['period']}: ${t['total_cost']:.4f}")

# Monthly aggregation
monthly = get_cost_trend(granularity="monthly")
```

---

## 5. Cost Dashboard

Serve the live HTML dashboard with the FastAPI app:

```bash
uvicorn ai_vibe_coding.app:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/static/cost_dashboard.html` in a browser.

### Dashboard Features

| Feature | Detail |
|---------|--------|
| **Date range filter** | Start/end date inputs with Filter button |
| **Summary card** | Aggregate cost and token display |
| **Sparkline chart** | SVG line chart for cost-over-time visualization |
| **Bar chart** | Per-period cost comparison |
| **Data table** | Tabular view with date, provider, model, cost, tokens, latency |
| **Auto-refresh** | Meta refresh every 300s + JS `setInterval` every 30s |

The dashboard HTML file lives at `src/ai_vibe_coding/static/cost_dashboard.html`.

---

## 6. REST API Endpoints

FastAPI endpoints are defined in `src/ai_vibe_coding/cost_api.py` (route stubs on an `APIRouter` at `/api/v1/costs`):

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/costs/total` | Total cost with optional date/provider filters |
| `GET` | `/api/v1/costs/daily` | Daily cost/token breakdown |
| `GET` | `/api/v1/costs/by-provider` | Cost breakdown by provider |
| `GET` | `/api/v1/costs/by-model` | Cost breakdown by model |
| `GET` | `/api/v1/costs/by-user` | Cost breakdown by session/user |
| `GET` | `/api/v1/costs/latency/percentiles` | Latency at specified percentile |
| `GET` | `/api/v1/costs/comparison/providers` | Compare costs across providers |
| `GET` | `/api/v1/costs/trend` | Cost trend data over time |
| `GET` | `/api/v1/costs/budget/alerts` | Recent alert history |
| `POST` | `/api/v1/costs/budget/check` | Check all budgets |

---

## 7. Complete Example

```python
"""End-to-end cost tracking workflow."""
from ai_vibe_coding.cost_store import SqliteCostStore, CostPricingTable
from ai_vibe_coding.budget_alert import BudgetAlertEngine, BudgetConfig, AlertThreshold
from ai_vibe_coding.cost_comparison import compare_actual_costs
from ai_vibe_coding.llm_wrapper import PRICING

# 1. Set up persistence
store = SqliteCostStore(":memory:")
store.record_request("openai", "gpt-4", 500, 200, 0.027, 1200)
store.record_request("anthropic", "claude-4-sonnet", 400, 150, 0.006, 800)
store.record_request("deepseek", "deepseek-v3", 600, 300, 0.00252, 1500)
store.run_daily_rollup()

# 2. Pricing table
pricing = CostPricingTable({})
n = pricing.seed_from_pricing_dict(PRICING)

# 3. Check budgets
engine = BudgetAlertEngine()
engine.add_config(BudgetConfig(
    name="test", max_budget=0.02,
    thresholds=[AlertThreshold(metric="cost", operator="gt", value=0.01)],
))
alerts = engine.check_budgets(current_spend=0.035)

# 4. Compare actual costs
costs = compare_actual_costs()
for r in costs:
    print(f"{r['provider']}: ${r['total_cost']:.4f}")

print(f"Alerts fired: {len(alerts)}")
print(f"Pricing entries: {n}")
```
