"""Pre-development acceptance tests for Rate Limiting & Quota Management.

Test categories:
  1. Interface Smoke Tests       ( 8 tests)
  2. RateLimitExceeded Tests      ( 4 tests)
  3. TokenBucket Tests           (12 tests)
  4. SlidingWindowCounter Tests  (12 tests)
  5. AdaptiveRateLimiter Tests   (10 tests)
  6. QuotaManager Tests          (12 tests)
  7. CostAwareDistribution Tests  ( 6 tests)
  8. Integration Tests            ( 6 tests)
                                -----
    Total:                        70 tests
"""

from __future__ import annotations

import pytest

try:
    from ai_vibe_coding.rate_limiting import (
        AdaptiveRateLimiter,
        CostAwareAllocation,
        QuotaConfig,
        QuotaManager,
        QuotaPeriod,
        QuotaUsage,
        RateLimiterState,
        RateLimitExceeded,
        SlidingWindowCounter,
        TokenBucket,
    )
    MODULE_EXISTS = True
except ImportError:
    MODULE_EXISTS = False


def test_rate_limiting_module_must_exist() -> None:
    """RED phase: rate_limiting.py must exist for tests to run."""
    if not MODULE_EXISTS:
        pytest.fail(
            "Module 'ai_vibe_coding.rate_limiting' not found. "
            "This is expected in RED phase — create the module with "
            "stub classes to proceed."
        )


# ====================================================================
# Interface Smoke Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="rate_limiting not impl")
class TestInterfaceSmoke:
    """Verify API surface — all classes, enums, and dataclasses exist."""

    def test_token_bucket_instantiation(self) -> None:
        tb = TokenBucket(capacity=10.0, refill_rate=1.0)
        assert tb.capacity == 10.0
        assert tb.refill_rate == 1.0

    def test_sliding_window_counter_instantiation(self) -> None:
        sw = SlidingWindowCounter(window_size=60.0, max_requests=100)
        assert sw.window_size == 60.0
        assert sw.max_requests == 100

    def test_adaptive_rate_limiter_instantiation(self) -> None:
        arl = AdaptiveRateLimiter(max_rate=10.0, min_rate=0.5)
        assert arl.state == RateLimiterState.NORMAL

    def test_quota_manager_instantiation(self) -> None:
        qm = QuotaManager()
        assert qm is not None

    def test_quota_config_dataclass(self) -> None:
        cfg = QuotaConfig(provider="openai", user="test", max_daily_tokens=1_000_000)
        assert cfg.provider == "openai"
        assert cfg.user == "test"

    def test_quota_usage_dataclass(self) -> None:
        usage = QuotaUsage(provider="openai", user="test")
        assert usage.tokens_used_today == 0.0

    def test_cost_aware_allocation_dataclass(self) -> None:
        alloc = CostAwareAllocation(provider="openai", user="test", allocated_tokens=100.0)
        assert alloc.allocated_tokens == 100.0

    def test_rate_limiter_state_enum(self) -> None:
        assert RateLimiterState.NORMAL.value == "NORMAL"
        assert RateLimiterState.THROTTLED.value == "THROTTLED"
        assert RateLimiterState.BACKED_OFF.value == "BACKED_OFF"
        assert RateLimiterState.STOPPED.value == "STOPPED"


# ====================================================================
# RateLimitExceeded Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="rate_limiting not impl")
class TestRateLimitExceeded:
    """Test the RateLimitExceeded exception class."""

    def test_rate_limit_exceeded_is_exception(self) -> None:
        err = RateLimitExceeded()
        assert isinstance(err, Exception)

    def test_rate_limit_exceeded_with_limiter_type(self) -> None:
        err = RateLimitExceeded(limiter_type="TokenBucket", resource="openai")
        assert "TokenBucket" in str(err)

    def test_rate_limit_exceeded_with_message(self) -> None:
        err = RateLimitExceeded(message="too fast")
        assert "too fast" in str(err)

    def test_rate_limit_exceeded_attributes(self) -> None:
        err = RateLimitExceeded(limiter_type="token", resource="rsc", message="msg")
        assert err.limiter_type == "token"
        assert err.resource == "rsc"
        assert err.message == "msg"


# ====================================================================
# TokenBucket Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="rate_limiting not impl")
class TestTokenBucket:
    """Test TokenBucket behavior — consume, refill, reset."""

    def test_initial_tokens_equal_capacity(self) -> None:
        tb = TokenBucket(capacity=10.0, refill_rate=1.0)
        assert tb.available_tokens == 10.0

    def test_consume_reduces_tokens(self) -> None:
        tb = TokenBucket(capacity=10.0, refill_rate=1.0)
        assert tb.consume(5.0) is True
        assert tb.available_tokens == pytest.approx(5.0, abs=0.001)

    def test_consume_returns_false_when_insufficient(self) -> None:
        tb = TokenBucket(capacity=1.0, refill_rate=1.0)
        assert tb.consume(1.0) is True
        assert tb.consume(1.0) is False

    def test_consume_raises_on_zero(self) -> None:
        tb = TokenBucket(capacity=10.0, refill_rate=1.0)
        with pytest.raises(ValueError, match="positive"):
            tb.consume(0.0)

    def test_consume_raises_on_exceeding_capacity(self) -> None:
        tb = TokenBucket(capacity=5.0, refill_rate=1.0)
        with pytest.raises(ValueError, match="exceeds"):
            tb.consume(10.0)

    def test_refill_to_full(self) -> None:
        tb = TokenBucket(capacity=10.0, refill_rate=1.0)
        tb.consume(5.0)
        tb.refill()
        assert tb.available_tokens == 10.0

    def test_refill_partial(self) -> None:
        tb = TokenBucket(capacity=10.0, refill_rate=1.0)
        tb.consume(8.0)
        tb.refill(tokens=3.0)
        assert tb.available_tokens == pytest.approx(5.0, abs=0.001)  # capped at capacity

    def test_auto_refill_over_time(self) -> None:
        """Bucket refills based on elapsed time."""
        fake_time: list[float] = [0.0]

        def _time() -> float:
            return fake_time[0]

        tb = TokenBucket(capacity=10.0, refill_rate=2.0, time_func=_time)
        tb.consume(10.0)  # empty the bucket
        assert tb.available_tokens == 0.0

        fake_time[0] = 3.0  # 3 seconds later → 6 tokens refilled
        assert tb.available_tokens == 6.0

    def test_reset_restores_full_capacity(self) -> None:
        tb = TokenBucket(capacity=10.0, refill_rate=1.0)
        tb.consume(7.0)
        tb.reset()
        assert tb.available_tokens == 10.0

    def test_consume_one_default(self) -> None:
        tb = TokenBucket(capacity=5.0, refill_rate=1.0)
        assert tb.consume() is True  # default tokens=1
        assert tb.available_tokens == pytest.approx(4.0, abs=0.001)

    def test_raises_on_invalid_capacity(self) -> None:
        with pytest.raises(ValueError, match="capacity"):
            TokenBucket(capacity=0, refill_rate=1.0)

    def test_raises_on_invalid_refill_rate(self) -> None:
        with pytest.raises(ValueError, match="refill_rate"):
            TokenBucket(capacity=10.0, refill_rate=0)


# ====================================================================
# SlidingWindowCounter Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="rate_limiting not impl")
class TestSlidingWindowCounter:
    """Test SlidingWindowCounter — allow, remaining, trim."""

    def test_allow_returns_true_within_limit(self) -> None:
        sw = SlidingWindowCounter(window_size=60.0, max_requests=10)
        assert sw.allow() is True

    def test_allow_returns_false_when_exceeded(self) -> None:
        sw = SlidingWindowCounter(window_size=60.0, max_requests=3)
        assert sw.allow() is True
        assert sw.allow() is True
        assert sw.allow() is True
        assert sw.allow() is False

    def test_remaining_count(self) -> None:
        sw = SlidingWindowCounter(window_size=60.0, max_requests=10)
        sw.allow()
        sw.allow()
        assert sw.remaining() == 8

    def test_remaining_returns_max_when_empty(self) -> None:
        sw = SlidingWindowCounter(window_size=60.0, max_requests=10)
        assert sw.remaining() == 10

    def test_reset_clears_counters(self) -> None:
        sw = SlidingWindowCounter(window_size=60.0, max_requests=3)
        sw.allow()
        sw.allow()
        sw.allow()
        sw.reset()
        assert sw.remaining() == 3

    def test_request_count_property(self) -> None:
        sw = SlidingWindowCounter(window_size=60.0, max_requests=10)
        sw.allow()
        sw.allow()
        assert sw.request_count == 2

    def test_window_expires_old_requests(self) -> None:
        fake_time: list[float] = [0.0]

        def _time() -> float:
            return fake_time[0]

        sw = SlidingWindowCounter(max_requests=2, window_size=10.0, time_func=_time)
        assert sw.allow() is True
        assert sw.allow() is True
        assert sw.allow() is False  # limit reached

        fake_time[0] = 15.0  # window expired
        assert sw.allow() is True  # old entries dropped

    def test_time_until_next_slot_zero_when_not_full(self) -> None:
        sw = SlidingWindowCounter(window_size=60.0, max_requests=10)
        assert sw.time_until_next_slot() == 0.0

    def test_time_until_next_slot_positive_when_full(self) -> None:
        fake_time: list[float] = [10.0]

        def _time() -> float:
            return fake_time[0]

        sw = SlidingWindowCounter(max_requests=2, window_size=10.0, time_func=_time)
        assert sw.allow() is True
        assert sw.allow() is True  # full
        # oldest timestamp is at 10.0, window ends at 20.0, current time is 10.0
        assert sw.time_until_next_slot() == 10.0

    def test_raises_on_invalid_window_size(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            SlidingWindowCounter(window_size=0, max_requests=10)

    def test_raises_on_invalid_max_requests(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            SlidingWindowCounter(window_size=60.0, max_requests=0)


# ====================================================================
# AdaptiveRateLimiter Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="rate_limiting not impl")
class TestAdaptiveRateLimiter:
    """Test AdaptiveRateLimiter — health-based rate adaptation."""

    def test_initial_state_is_normal(self) -> None:
        arl = AdaptiveRateLimiter(max_rate=10.0)
        assert arl.state == RateLimiterState.NORMAL

    def test_full_health_allows_request(self) -> None:
        arl = AdaptiveRateLimiter(max_rate=10.0, min_rate=0.5)
        arl.update_health(1.0)
        assert arl.state == RateLimiterState.NORMAL
        assert arl.allow() is True

    def test_low_health_triggers_throttled(self) -> None:
        arl = AdaptiveRateLimiter(max_rate=10.0, min_rate=0.5, health_threshold=0.3)
        arl.update_health(0.2)
        assert arl.state == RateLimiterState.THROTTLED

    def test_zero_health_triggers_backed_off(self) -> None:
        arl = AdaptiveRateLimiter(max_rate=10.0, min_rate=0.5, health_threshold=0.3)
        arl.update_health(0.0)
        assert arl.state == RateLimiterState.BACKED_OFF

    def test_reset_restores_normal(self) -> None:
        arl = AdaptiveRateLimiter(max_rate=10.0)
        arl.update_health(0.0)
        arl.reset()
        assert arl.state == RateLimiterState.NORMAL
        assert arl.current_rate == 10.0

    def test_allow_fails_when_exhausted(self) -> None:
        """Rate is so low that requests are denied."""
        arl = AdaptiveRateLimiter(max_rate=0.1, min_rate=0.01, health_threshold=0.3)
        arl.update_health(0.0)  # rate drops to near zero
        # With rate that low, immediate consume should fail
        assert arl.allow() is False

    def test_update_health_raises_on_invalid(self) -> None:
        arl = AdaptiveRateLimiter()
        with pytest.raises(ValueError, match="health_score"):
            arl.update_health(-0.1)

    def test_raises_on_invalid_max_rate(self) -> None:
        with pytest.raises(ValueError, match="max_rate"):
            AdaptiveRateLimiter(max_rate=0)

    def test_raises_on_invalid_health_threshold(self) -> None:
        with pytest.raises(ValueError, match="health_threshold"):
            AdaptiveRateLimiter(health_threshold=-0.1)

    def test_current_rate_property(self) -> None:
        arl = AdaptiveRateLimiter(max_rate=20.0)
        assert arl.current_rate == 20.0
        arl.update_health(0.5)
        assert arl.current_rate <= 20.0


# ====================================================================
# QuotaManager Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="rate_limiting not impl")
class TestQuotaManager:
    """Test QuotaManager — per-provider/user quota management."""

    def test_add_quota(self) -> None:
        qm = QuotaManager()
        qm.add_quota(QuotaConfig(provider="openai", user="user1", max_daily_tokens=500))
        assert qm.check_quota("openai", "user1") is True

    def test_remove_quota(self) -> None:
        qm = QuotaManager()
        qm.add_quota(QuotaConfig(provider="openai", user="user1", max_daily_tokens=500))
        qm.remove_quota("openai", "user1")
        assert qm.check_quota("openai", "user1") is True  # no quota = no limit

    def test_check_quota_returns_false_when_exceeded(self) -> None:
        qm = QuotaManager()
        qm.add_quota(QuotaConfig(provider="openai", user="user1", max_daily_tokens=100))
        qm.record_usage("openai", "user1", tokens=200)
        assert qm.check_quota("openai", "user1") is False

    def test_record_usage_updates_counters(self) -> None:
        qm = QuotaManager()
        qm.add_quota(QuotaConfig(provider="openai", user="user1", max_daily_tokens=1000))
        qm.record_usage("openai", "user1", tokens=100, cost=0.05)
        usage = qm.get_usage("openai", "user1")
        assert usage is not None
        assert usage.tokens_used_today == 100.0
        assert usage.cost_today == 0.05

    def test_record_usage_returns_false_when_exceeded(self) -> None:
        qm = QuotaManager()
        qm.add_quota(QuotaConfig(
            provider="openai", user="user1",
            max_daily_tokens=100, max_monthly_cost=1.0,
        ))
        result = qm.record_usage("openai", "user1", tokens=200, cost=2.0)
        assert result is False

    def test_allocate_burst_within_limit(self) -> None:
        qm = QuotaManager()
        qm.add_quota(QuotaConfig(provider="openai", user="user1", burst_limit=5))
        assert qm.allocate_burst("openai", "user1") is True

    def test_allocate_burst_exceeds_limit(self) -> None:
        qm = QuotaManager()
        qm.add_quota(QuotaConfig(provider="openai", user="user1", burst_limit=2))
        assert qm.allocate_burst("openai", "user1") is True
        assert qm.allocate_burst("openai", "user1") is True
        assert qm.allocate_burst("openai", "user1") is False

    def test_get_usage_returns_none_for_unknown(self) -> None:
        qm = QuotaManager()
        assert qm.get_usage("unknown", "user1") is None

    def test_cost_aware_allocation_within_budget(self) -> None:
        qm = QuotaManager()
        qm.add_quota(QuotaConfig(
            provider="openai", user="user1",
            max_daily_tokens=1000, max_monthly_cost=100.0,
            cost_per_token=0.001,
        ))
        alloc = qm.cost_aware_allocation("openai", "user1", 500)
        assert alloc.allocated_tokens == 500.0

    def test_cost_aware_allocation_budget_exceeded(self) -> None:
        qm = QuotaManager()
        qm.add_quota(QuotaConfig(
            provider="openai", user="user1",
            max_daily_tokens=1000, max_monthly_cost=1.0,
            cost_per_token=0.01,
        ))
        alloc = qm.cost_aware_allocation("openai", "user1", 500)
        # max_monthly_cost=1.0, cost_per_token=0.01 → max_tokens_by_cost=100
        assert alloc.allocated_tokens == 100.0


# ====================================================================
# CostAwareDistribution Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="rate_limiting not impl")
class TestCostAwareDistribution:
    """Test cost-aware allocation with multiple providers."""

    def test_multiple_providers_allocated(self) -> None:
        qm = QuotaManager()
        qm.add_quota(QuotaConfig(provider="openai", user="u1", max_daily_tokens=500, cost_per_token=0.01))
        qm.add_quota(QuotaConfig(provider="anthropic", user="u1", max_daily_tokens=300, cost_per_token=0.015))
        alloc1 = qm.cost_aware_allocation("openai", "u1", 1000)
        alloc2 = qm.cost_aware_allocation("anthropic", "u1", 1000)
        assert alloc1.allocated_tokens <= 500
        assert alloc2.allocated_tokens <= 300

    def test_zero_allocated_when_no_budget(self) -> None:
        qm = QuotaManager()
        qm.add_quota(QuotaConfig(
            provider="openai", user="u1",
            max_daily_tokens=0, max_monthly_cost=0,
        ))
        alloc = qm.cost_aware_allocation("openai", "u1", 100)
        assert alloc.allocated_tokens == 0.0

    def test_burst_tracked_in_usage(self) -> None:
        qm = QuotaManager()
        qm.add_quota(QuotaConfig(provider="openai", user="u1", burst_limit=3))
        qm.allocate_burst("openai", "u1")
        qm.allocate_burst("openai", "u1")
        usage = qm.get_usage("openai", "u1")
        assert usage is not None
        assert usage.burst_used == 2

    def test_cost_aware_allocation_estimates_cost(self) -> None:
        qm = QuotaManager()
        qm.add_quota(QuotaConfig(
            provider="openai", user="u1",
            max_daily_tokens=1000, cost_per_token=0.002,
        ))
        alloc = qm.cost_aware_allocation("openai", "u1", 500)
        assert alloc.estimated_cost == 1.0  # 500 * 0.002

    def test_no_config_no_limits(self) -> None:
        qm = QuotaManager()
        assert qm.check_quota("openai", "nobody") is True
        assert qm.record_usage("openai", "nobody", tokens=999999) is True

    def test_monthly_cost_limit(self) -> None:
        qm = QuotaManager()
        qm.add_quota(QuotaConfig(
            provider="openai", user="u1",
            max_monthly_cost=10.0,
        ))
        assert qm.record_usage("openai", "u1", cost=8.0) is True
        assert qm.record_usage("openai", "u1", cost=5.0) is False


# ====================================================================
# Integration Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="rate_limiting not impl")
class TestIntegration:
    """Integration tests combining multiple rate-limiting components."""

    def test_token_bucket_with_sliding_window(self) -> None:
        """TokenBucket + SlidingWindowCounter combined."""
        tb = TokenBucket(capacity=5.0, refill_rate=1.0)
        sw = SlidingWindowCounter(window_size=60.0, max_requests=10)

        # Must pass both rate limiters to proceed
        for _ in range(5):
            assert tb.consume() is True
            assert sw.allow() is True

        # Bucket empty but window still has room
        assert tb.consume() is False
        assert tb.available_tokens < 1.0

    def test_quota_manager_with_burst(self) -> None:
        """QuotaManager burst + token usage."""
        qm = QuotaManager()
        qm.add_quota(QuotaConfig(
            provider="openai", user="u1",
            max_daily_tokens=1000, burst_limit=3,
        ))

        for _ in range(3):
            assert qm.allocate_burst("openai", "u1") is True

        assert qm.allocate_burst("openai", "u1") is False
        qm.record_usage("openai", "u1", tokens=100)
        usage = qm.get_usage("openai", "u1")
        assert usage is not None
        assert usage.tokens_used_today == 100.0
        assert usage.burst_used == 3

    def test_adaptive_limiter_health_transitions(self) -> None:
        """AdaptiveRateLimiter state transitions."""
        arl = AdaptiveRateLimiter(max_rate=10.0, min_rate=0.5)

        arl.update_health(1.0)
        assert arl.state == RateLimiterState.NORMAL
        assert arl.current_rate >= 9.0  # near max

        arl.update_health(0.2)
        assert arl.state in (RateLimiterState.THROTTLED, RateLimiterState.NORMAL)

        arl.update_health(0.0)
        assert arl.state == RateLimiterState.BACKED_OFF
        assert arl.current_rate < 0.5  # should be severely throttled

    def test_quota_manager_cost_aware_multiple_calls(self) -> None:
        """Multiple cost-aware allocations accumulate correctly."""
        qm = QuotaManager()
        qm.add_quota(QuotaConfig(
            provider="openai", user="u1",
            max_daily_tokens=1000, max_monthly_cost=5.0,
            cost_per_token=0.001,
        ))

        alloc1 = qm.cost_aware_allocation("openai", "u1", 600)
        assert alloc1.allocated_tokens == 600.0
        qm.record_usage("openai", "u1", tokens=600, cost=0.6)

        alloc2 = qm.cost_aware_allocation("openai", "u1", 600)
        assert alloc2.allocated_tokens == 400.0  # limited by max_daily_tokens

    def test_sliding_window_auto_trim(self) -> None:
        """Old entries are trimmed automatically."""
        fake_time: list[float] = [0.0]

        def _time() -> float:
            return fake_time[0]

        sw = SlidingWindowCounter(max_requests=3, window_size=10.0, time_func=_time)
        sw.allow()
        sw.allow()
        sw.allow()

        fake_time[0] = 20.0
        assert sw.allow() is True  # all previous expired
        assert sw.request_count == 1

    def test_token_bucket_long_refill(self) -> None:
        """Token bucket refills correctly over time."""
        fake_time: list[float] = [0.0]

        def _time() -> float:
            return fake_time[0]

        tb = TokenBucket(capacity=10.0, refill_rate=5.0, time_func=_time)
        tb.consume(10.0)
        fake_time[0] = 10.0
        assert tb.available_tokens == 10.0  # fully refilled
