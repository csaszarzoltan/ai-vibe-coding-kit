"""
Persistent Cost Tracking with SQLite — Working Example
======================================================

Demonstrates:
  - SqliteCostStore: record requests, daily rollups, provider breakdowns
  - CostTracker: extend with SQLite store delegation
  - BudgetAlertEngine: define budgets and check thresholds
  - CostPricingTable: manage per-model pricing

Run:
    cd ai-vibe-coding-kit
    python examples/cost_tracking_persistence_example.py
"""

from ai_vibe_coding.budget_alert import (
    AlertThreshold,
    BudgetAlertEngine,
    BudgetConfig,
)
from ai_vibe_coding.cost_comparison import (
    compare_actual_costs,
    compare_estimated_vs_actual,
    get_cost_trend,
)
from ai_vibe_coding.cost_store import CostPricingTable, SqliteCostStore
from ai_vibe_coding.cost_tracker import CostTracker
from ai_vibe_coding.llm_wrapper import PRICING, LLMResponse


def demo_sqlite_cost_store():
    """Create an in-memory store, record requests, and run queries."""
    print("=" * 60)
    print("1. SqliteCostStore — Record & Query")
    print("=" * 60)

    store = SqliteCostStore(":memory:")

    # Simulate LLM API calls
    requests = [
        ("openai", "gpt-4", 500, 200, 0.0270, 1200.0, "session-a"),
        ("openai", "gpt-4", 300, 100, 0.0150, 950.0, "session-a"),
        ("anthropic", "claude-4-sonnet", 400, 150, 0.0060, 800.0, "session-b"),
        ("deepseek", "deepseek-v3", 600, 300, 0.00252, 1500.0, "session-b"),
        ("mimo", "mimo-v2.5", 1000, 500, 0.0014, 2000.0, "session-c"),
    ]

    for prov, model, inp, out, cost, lat, sid in requests:
        store.record_request(
            provider=prov,
            model=model,
            input_tokens=inp,
            output_tokens=out,
            cost_usd=cost,
            latency_ms=lat,
            session_id=sid,
        )

    # Daily rollup
    rollup = store.run_daily_rollup()
    print(f"Daily rollup: {rollup['dates_rolled_up']} date(s) processed\n")

    # Provider breakdown
    print("Provider breakdown:")
    for row in store.get_cost_by_provider():
        print(f"  {row['provider']:12s}  ${row['total_cost']:.4f}  "
              f"{row['total_tokens']:>6} tokens  {row['request_count']} calls")

    # Model breakdown
    print("\nModel breakdown:")
    for row in store.get_cost_by_model():
        print(f"  {row['model']:20s}  ${row['total_cost']:.4f}")

    # User/session breakdown
    print("\nUser/session breakdown:")
    for row in store.get_cost_by_user():
        print(f"  {row['session_id']:20s}  ${row['total_cost']:.4f}")

    # Total cost
    total = store.get_total_cost()
    print(f"\nTotal cost across all providers: ${total:.4f}")

    # Latency percentiles
    print("\nLatency percentiles:")
    print(f"  p50 = {store.get_latency_percentiles(50.0):.0f}ms")
    print(f"  p95 = {store.get_latency_percentiles(95.0):.0f}ms")

    return store


def demo_pricing_table():
    """Seed and query the CostPricingTable."""
    print("\n" + "=" * 60)
    print("2. CostPricingTable — Pricing Management")
    print("=" * 60)

    pricing = CostPricingTable({})
    count = pricing.seed_from_pricing_dict(PRICING)
    print(f"Seeded {count} pricing entries from PRICING dict")

    # Query a rate
    rate = pricing.get_pricing("openai", "gpt-4")
    if rate:
        print(f"GPT-4: ${rate['input']:.4f}/1K in, ${rate['output']:.4f}/1K out")

    # Add custom pricing
    pricing.upsert_pricing("my-provider", "my-model", 0.005, 0.015)
    custom = pricing.get_pricing("my-provider", "my-model")
    print(f"Custom: ${custom['input']:.4f}/1K in, ${custom['output']:.4f}/1K out")


def demo_cost_tracker_extension(store):
    """Extend CostTracker with a SQLite store."""
    print("\n" + "=" * 60)
    print("3. CostTracker — Store Delegation")
    print("=" * 60)

    tracker = CostTracker()
    tracker.set_store(store)

    # Manually record some responses
    responses = [
        LLMResponse(
            content="response-1",
            provider="openai",
            model="gpt-4",
            tokens_used=500,
            cost_usd=0.015,
            latency_ms=800.0,
            input_tokens=300,
            output_tokens=200,
        ),
        LLMResponse(
            content="response-2",
            provider="anthropic",
            model="claude-4-sonnet",
            tokens_used=400,
            cost_usd=0.006,
            latency_ms=700.0,
            input_tokens=250,
            output_tokens=150,
        ),
    ]

    for resp in responses:
        tracker.record(resp)

    # In-memory summary (always available)
    summary = tracker.get_summary()
    print("In-memory cost summary:")
    print(summary.to_table())

    # Store-backed daily costs
    daily = tracker.get_daily_cost()
    print(f"Store-backed daily rollups: {len(daily)} day(s)")

    # Store-backed latency percentile
    p95 = tracker.get_latency_percentiles(percentile=95.0)
    print(f"Store-backed p95 latency: {p95:.0f}ms")


def demo_budget_alerts():
    """Define budgets, check thresholds, and view alert history."""
    print("\n" + "=" * 60)
    print("4. BudgetAlertEngine — Threshold Alerts")
    print("=" * 60)

    engine = BudgetAlertEngine()

    # Build a budget config in code
    config = BudgetConfig(
        name="monthly-llm",
        max_budget=100.0,
        period="monthly",
        thresholds=[
            AlertThreshold(
                metric="cost", operator="gt",
                value=80.0, label="80% spend warning",
            ),
            AlertThreshold(
                metric="tokens", operator="gt",
                value=10_000_000, label="10M token warning",
            ),
        ],
        notification_channels=["console"],
        enabled=True,
    )
    engine.add_config(config)

    # Check budgets at 85% spend
    alerts = engine.check_budgets(current_spend=85.0)
    print(f"At spend=85.0: {len(alerts)} alert(s) fired")
    for alert in alerts:
        print(f"  [{alert['name']}] {alert['message']}")

    # Check budgets at 105% spend (over budget)
    alerts = engine.check_budgets(current_spend=105.0)
    print(f"At spend=105.0: {len(alerts)} alert(s) fired")
    for alert in alerts:
        print(f"  [{alert['name']}] {alert['message']}")

    # View alert history
    print(f"\nAlert history ({len(engine.get_alert_history())} entries):")
    for entry in engine.get_alert_history():
        print(f"  {entry['timestamp']} — {entry['name']}: {entry['message']}")


def demo_cost_comparison():
    """Compare actual costs, estimates vs actuals, and cost trends."""
    print("\n" + "=" * 60)
    print("5. Cost Comparison & Trends")
    print("=" * 60)

    # These functions create their own :memory: store,
    # so results are empty here — demonstrates the API shape
    actual = compare_actual_costs()
    print(f"Actual cost comparison: {len(actual)} provider(s)")

    comparison = compare_estimated_vs_actual()
    print(f"Estimate vs actual: {len(comparison)} provider(s)")

    trend = get_cost_trend(granularity="daily")
    print(f"Cost trend: {len(trend)} period(s)")


if __name__ == "__main__":
    store = demo_sqlite_cost_store()
    demo_pricing_table()
    demo_cost_tracker_extension(store)
    demo_budget_alerts()
    demo_cost_comparison()
    print("\n✅ All cost tracking examples completed successfully.")
