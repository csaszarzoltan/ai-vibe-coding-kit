"""Example: Rate Limiting + Resilience integration.

Demonstrates combining TokenBucket rate limiting with existing
circuit breaker and retry patterns for resilient LLM calls.
"""

from __future__ import annotations

from ai_vibe_coding.rate_limiting import (
    AdaptiveRateLimiter,
    QuotaConfig,
    QuotaManager,
    SlidingWindowCounter,
    TokenBucket,
)


def token_bucket_example() -> None:
    """Basic TokenBucket usage."""
    print("=== TokenBucket Example ===")
    bucket = TokenBucket(capacity=10.0, refill_rate=2.0)
    # Consume tokens for API calls
    for i in range(12):
        allowed = bucket.consume()
        print(f"  Request {i+1}: {'ALLOWED' if allowed else 'DENIED (rate limit)'}")
        if not allowed:
            print(f"  → Waiting for refill... tokens: {bucket.available_tokens:.1f}")
            bucket.refill()
            print(f"  → After refill: {bucket.available_tokens:.1f} tokens available")


def sliding_window_example() -> None:
    """SlidingWindowCounter usage."""
    print("\n=== SlidingWindowCounter Example ===")
    limiter = SlidingWindowCounter(window_size=10.0, max_requests=5)
    for i in range(7):
        allowed = limiter.allow()
        print(f"  Request {i+1}: {'ALLOWED' if allowed else 'BLOCKED'}")
        if allowed:
            print(f"    Remaining: {limiter.remaining()}")


def adaptive_rate_limiter_example() -> None:
    """Adaptive rate limiting based on provider health."""
    print("\n=== AdaptiveRateLimiter Example ===")
    limiter = AdaptiveRateLimiter(max_rate=10.0, min_rate=0.5, health_threshold=0.3)

    print("  Initial state:", limiter.state.value, "Rate:", limiter.current_rate)

    # Provider healthy
    limiter.update_health(0.9)
    print("  Health=0.9 →", limiter.state.value, "Rate:", round(limiter.current_rate, 1))

    # Provider degraded
    limiter.update_health(0.2)
    print("  Health=0.2 →", limiter.state.value, "Rate:", round(limiter.current_rate, 1))

    # Provider down
    limiter.update_health(0.0)
    print("  Health=0.0 →", limiter.state.value, "Rate:", round(limiter.current_rate, 1))

    limiter.reset()
    print("  After reset →", limiter.state.value, "Rate:", limiter.current_rate)


def quota_manager_example() -> None:
    """Quota management with cost-aware allocation."""
    print("\n=== QuotaManager Example ===")

    qm = QuotaManager()
    qm.add_quota(QuotaConfig(
        provider="openai",
        user="project-alpha",
        max_daily_tokens=100_000,
        max_monthly_cost=50.0,
        burst_limit=5,
        cost_per_token=0.00001,
    ))

    # Check burst capacity
    for i in range(6):
        burst = qm.allocate_burst("openai", "project-alpha")
        print(f"  Burst request {i+1}: {'ALLOWED' if burst else 'DENIED (burst exhausted)'}")

    # Cost-aware allocation
    alloc = qm.cost_aware_allocation("openai", "project-alpha", 10_000)
    print(f"\n  Cost-aware allocation:")
    print(f"    Requested: 10,000 tokens")
    print(f"    Allocated: {alloc.allocated_tokens:.0f} tokens")
    print(f"    Estimated cost: ${alloc.estimated_cost:.4f}")
    print(f"    Remaining budget: ${alloc.remaining_budget:.2f}")

    # Record usage
    qm.record_usage("openai", "project-alpha", tokens=10_000, cost=0.10)
    usage = qm.get_usage("openai", "project-alpha")
    if usage:
        print(f"\n  Usage snapshot:")
        print(f"    Tokens today: {usage.tokens_used_today:.0f}")
        print(f"    Cost today: ${usage.cost_today:.4f}")
        print(f"    Requests today: {usage.requests_today}")
        print(f"    Burst used: {usage.burst_used}/{usage.burst_used}")


def combined_with_resilience_pattern() -> None:
    """Demonstrates combining rate limiting with resilience patterns
    (circuit breaker, retry from resilience.py).

    This is a conceptual example — the actual integration would wrap
    LLM calls through both layers.
    """
    print("\n=== Combined Rate Limiting + Resilience ===")
    print("""
    ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
    │ Rate Limit  │────→│ Circuit      │────→│ Retry        │────→ LLM Call
    │ (TokenBucket)│     │ Breaker      │     │ Policy       │
    └─────────────┘     └──────────────┘     └──────────────┘
           │                   │                     │
           ▼                   ▼                     ▼
    QuotaManager        HealthChecker          FallbackChain
    (cost/budget)       (provider health)      (provider failover)
    """)
    print("  Flow:")
    print("  1. TokenBucket: burst control + sustained rate")
    print("  2. QuotaManager: daily/monthly budget check")
    print("  3. CircuitBreaker: skip unhealthy providers")
    print("  4. RetryPolicy: exponential backoff on transient errors")
    print("  5. FallbackChain: try next provider on failure")


if __name__ == "__main__":
    token_bucket_example()
    sliding_window_example()
    adaptive_rate_limiter_example()
    quota_manager_example()
    combined_with_resilience_pattern()
