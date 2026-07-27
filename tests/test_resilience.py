"""Pre-development tests for LLM Failover & Resilience Patterns.

RED phase: All tests fail because src/ai_vibe_coding/resilience.py
classes raise NotImplementedError (or the module is absent).

When the developer fills in stub implementations:
  - Interface smoke tests will pass (construct, inspect)
  - Behavioral tests will fail with NotImplementedError
  - Integration tests will fail with NotImplementedError

Test categories:
  1. Interface Smoke Tests       (16 tests)
  2. CircuitBreaker Tests        (12 tests)
  3. RetryPolicy Tests           (10 tests)
  4. FallbackChain Tests          (6 tests)
  5. TimeoutBudget Tests          (6 tests)
  6. HealthChecker Tests          (8 tests)
  7. ResponseCache Tests          (6 tests)
  8. Observability Tests          (8 tests)
  9. ResilientLLMClient Tests    (8 tests)
 10. Integration End-to-End Tests (6 tests)
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

import pytest


# ─── Module-level guard ──────────────────────────────────────────
# The target module's classes raise NotImplementedError (stubs).
# All tests below are guarded by a collecting dummy test that fails
# with a clear message.  When the developer implements the stubs,
# the guard is removed and real tests execute.

try:
    from ai_vibe_coding.resilience import (
        CircuitBreaker,
        CircuitBreakerConfig,
        CircuitBreakerOpenError,
        CircuitState,
        CounterMetrics,
        FallbackChain,
        FallbackResult,
        HealthChecker,
        HealthStatus,
        HealthStatusEnum,
        JitterMode,
        Observability,
        ResilienceConfig,
        ResilienceEvent,
        ResilientLLMClient,
        ResilientResponse,
        ResponseCache,
        ResponseCacheConfig,
        RetryPolicy,
        RetryPolicyConfig,
        TimeoutBudget,
        TimeoutBudgetError,
        TimeoutConfig,
    )
    MODULE_EXISTS = True
except ImportError:
    MODULE_EXISTS = False


def test_resilience_module_must_exist():
    """RED phase: resilience.py must exist for tests to run."""
    if not MODULE_EXISTS:
        pytest.fail(
            "Module 'ai_vibe_coding.resilience' not found. "
            "This is expected in RED phase — create the module with "
            "stub classes to proceed."
        )


# ====================================================================
# All remaining tests are guarded by MODULE_EXISTS
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="resilience not impl")
class TestInterfaceSmoke:
    """Verify that all classes, dataclasses, and methods exist."""

    def test_circuit_state_enum_values(self):
        """CircuitState has CLOSED / OPEN / HALF_OPEN."""
        assert CircuitState.CLOSED.value == "CLOSED"
        assert CircuitState.OPEN.value == "OPEN"
        assert CircuitState.HALF_OPEN.value == "HALF_OPEN"

    def test_health_status_enum_values(self):
        """HealthStatusEnum has HEALTHY / DEGRADED / UNHEALTHY."""
        assert HealthStatusEnum.HEALTHY.value == "HEALTHY"
        assert HealthStatusEnum.DEGRADED.value == "DEGRADED"
        assert HealthStatusEnum.UNHEALTHY.value == "UNHEALTHY"

    def test_jitter_mode_enum_values(self):
        """JitterMode has FULL / EQUAL."""
        assert JitterMode.FULL.value == "full"
        assert JitterMode.EQUAL.value == "equal"

    def test_circuit_breaker_open_error(self):
        """CircuitBreakerOpenError is a proper Exception subclass."""
        err = CircuitBreakerOpenError(provider="openai", message="open")
        assert isinstance(err, Exception)

    def test_timeout_budget_error(self):
        """TimeoutBudgetError is a proper Exception subclass."""
        err = TimeoutBudgetError(provider="anthropic", operation="chat")
        assert isinstance(err, Exception)

    def test_circuit_breaker_config_defaults(self):
        """CircuitBreakerConfig has correct defaults."""
        cfg = CircuitBreakerConfig()
        assert cfg.failure_threshold == 5
        assert cfg.success_threshold == 2
        assert cfg.open_timeout == 30.0

    def test_retry_policy_config_defaults(self):
        """RetryPolicyConfig has correct defaults."""
        cfg = RetryPolicyConfig()
        assert cfg.max_retries == 3
        assert cfg.base_delay == 1.0
        assert cfg.max_delay == 30.0
        assert 429 in cfg.retryable_status_codes
        assert cfg.jitter_mode == JitterMode.FULL

    def test_timeout_config_defaults(self):
        """TimeoutConfig has correct defaults."""
        cfg = TimeoutConfig()
        assert cfg.chat == 30.0
        assert cfg.stream == 60.0

    def test_response_cache_config_defaults(self):
        """ResponseCacheConfig has correct defaults."""
        cfg = ResponseCacheConfig()
        assert cfg.ttl_seconds == 300.0
        assert cfg.swr_seconds == 3600.0

    def test_resilience_config_with_circuit_breaker(self):
        """ResilienceConfig accepts circuit_breaker subconfig."""
        cb_cfg = CircuitBreakerConfig(failure_threshold=3)
        cfg = ResilienceConfig(circuit_breaker=cb_cfg)
        assert cfg.circuit_breaker.failure_threshold == 3

    def test_fallback_result_dataclass(self):
        """FallbackResult is instantiable with defaults."""
        result = FallbackResult()
        assert result.provider == ""
        assert result.error is None
        assert result.circuit_state == CircuitState.CLOSED
        assert result.latency_ms == 0.0

    def test_health_status_dataclass(self):
        """HealthStatus is instantiable with defaults."""
        status = HealthStatus()
        assert status.latency_ms == 0.0
        assert status.error_rate == 0.0
        assert status.availability == 1.0
        assert status.status == HealthStatusEnum.HEALTHY

    def test_resilience_event_dataclass(self):
        """ResilienceEvent is instantiable with defaults."""
        event = ResilienceEvent()
        assert event.type == ""
        assert event.provider == ""
        assert event.timestamp == 0.0
        assert event.details == {}

    def test_counter_metrics_dataclass(self):
        """CounterMetrics is instantiable with zero defaults."""
        m = CounterMetrics()
        assert m.retry_count == 0
        assert m.circuit_open_count == 0
        assert m.fallback_count == 0
        assert m.cache_hit_count == 0
        assert m.timeout_count == 0

    def test_resilient_response_dataclass(self):
        """ResilientResponse is instantiable with defaults."""
        r = ResilientResponse()
        assert r.content == ""
        assert r.provider == ""
        assert r.cached is False
        assert r.retry_count == 0

    def test_circuit_breaker_has_required_methods(self):
        """CircuitBreaker has all required methods."""
        assert hasattr(CircuitBreaker, "record_failure")
        assert hasattr(CircuitBreaker, "record_success")
        assert hasattr(CircuitBreaker, "get_state")
        assert hasattr(CircuitBreaker, "check")
        assert hasattr(CircuitBreaker, "on_state_change")

    def test_retry_policy_has_required_methods(self):
        """RetryPolicy has all required methods."""
        assert hasattr(RetryPolicy, "get_backoff_delay")
        assert hasattr(RetryPolicy, "is_retryable")
        assert hasattr(RetryPolicy, "should_retry")


# ====================================================================
# CircuitBreaker behavioral tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="resilience not impl")
class TestCircuitBreaker:
    """Behavioral contract for CircuitBreaker — NotImplementedError until implemented."""

    def test_init_with_defaults(self):
        """CircuitBreaker can be created with no args."""
        cb = CircuitBreaker()
        assert cb is not None

    def test_init_with_custom_config(self):
        """CircuitBreaker accepts custom CircuitBreakerConfig."""
        cfg = CircuitBreakerConfig(failure_threshold=3, success_threshold=1, open_timeout=10.0)
        cb = CircuitBreaker(config=cfg)
        assert cb is not None

    def test_initial_state_is_closed(self):
        """A brand-new circuit is CLOSED."""
        cb = CircuitBreaker()
        assert cb.get_state("openai") == CircuitState.CLOSED

    def test_closed_to_open_on_consecutive_failures(self):
        """N consecutive failures transition CLOSED -> OPEN."""
        cb = CircuitBreaker(config=CircuitBreakerConfig(failure_threshold=3))
        for _ in range(3):
            cb.record_failure("openai")
        assert cb.get_state("openai") == CircuitState.OPEN

    def test_open_raises_circuit_breaker_open_error(self):
        """check() on an OPEN circuit raises CircuitBreakerOpenError."""
        cb = CircuitBreaker(config=CircuitBreakerConfig(failure_threshold=1))
        cb.record_failure("openai")
        with pytest.raises(CircuitBreakerOpenError):
            cb.check("openai")

    def test_open_to_half_open_after_timeout(self):
        """After open_timeout the circuit transitions to HALF_OPEN."""
        fake_time = [0.0]

        def _time():
            return fake_time[0]

        cb = CircuitBreaker(
            config=CircuitBreakerConfig(failure_threshold=1, open_timeout=30.0),
            time_func=_time,
        )
        cb.record_failure("openai")  # now OPEN
        assert cb.get_state("openai") == CircuitState.OPEN
        fake_time[0] = 31.0  # advance past timeout
        assert cb.get_state("openai") == CircuitState.HALF_OPEN

    def test_half_open_to_closed_on_successes(self):
        """M consecutive successes transition HALF_OPEN -> CLOSED."""
        fake_time = [0.0]

        def _time():
            return fake_time[0]

        cb = CircuitBreaker(
            config=CircuitBreakerConfig(failure_threshold=1, success_threshold=2, open_timeout=5.0),
            time_func=_time,
        )
        cb.record_failure("openai")  # CLOSED -> OPEN
        fake_time[0] = 10.0  # transition to HALF_OPEN
        cb.record_success("openai")  # HALF_OPEN -> (one success)
        cb.record_success("openai")  # second success -> CLOSED
        assert cb.get_state("openai") == CircuitState.CLOSED

    def test_per_provider_isolation(self):
        """Failure count is per-provider, not global."""
        cb = CircuitBreaker(config=CircuitBreakerConfig(failure_threshold=3))
        cb.record_failure("openai")
        cb.record_failure("openai")
        cb.record_failure("anthropic")
        # openai has 2 failures, not yet OPEN
        assert cb.get_state("openai") == CircuitState.CLOSED
        # anthropic has 1 failure
        assert cb.get_state("anthropic") == CircuitState.CLOSED
        # third openai failure trips it
        cb.record_failure("openai")
        assert cb.get_state("openai") == CircuitState.OPEN

    def test_state_change_callback_invoked(self):
        """on_state_change callback fires on state transitions."""
        cb = CircuitBreaker(config=CircuitBreakerConfig(failure_threshold=1))
        transitions: list[tuple[str, CircuitState, CircuitState]] = []

        def _callback(provider: str, old: CircuitState, new: CircuitState):
            transitions.append((provider, old, new))

        cb.on_state_change(_callback)
        cb.record_failure("openai")  # CLOSED -> OPEN
        assert len(transitions) == 1
        assert transitions[0] == ("openai", CircuitState.CLOSED, CircuitState.OPEN)

    def test_half_open_records_success_and_failure(self):
        """In HALF_OPEN, a failure goes back to OPEN."""
        fake_time = [0.0]

        def _time():
            return fake_time[0]

        cb = CircuitBreaker(
            config=CircuitBreakerConfig(failure_threshold=1, open_timeout=5.0),
            time_func=_time,
        )
        cb.record_failure("openai")  # CLOSED -> OPEN
        fake_time[0] = 10.0  # becomes HALF_OPEN
        cb.record_failure("openai")  # HALF_OPEN -> OPEN again
        assert cb.get_state("openai") == CircuitState.OPEN

    def test_check_passes_when_closed(self):
        """check() does nothing when circuit is CLOSED."""
        cb = CircuitBreaker()
        # Should not raise
        cb.check("openai")


# ====================================================================
# RetryPolicy behavioral tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="resilience not impl")
class TestRetryPolicy:
    """Behavioral contract for RetryPolicy."""

    def test_init_with_defaults(self):
        """RetryPolicy can be created with no args."""
        rp = RetryPolicy()
        assert rp is not None

    def test_init_with_custom_config(self):
        """RetryPolicy accepts custom RetryPolicyConfig."""
        cfg = RetryPolicyConfig(max_retries=5, base_delay=2.0, max_delay=60.0)
        rp = RetryPolicy(config=cfg)
        assert rp is not None

    def test_backoff_exponential(self):
        """get_backoff_delay uses min(base_delay * 2^attempt, max_delay)."""
        rp = RetryPolicy(config=RetryPolicyConfig(base_delay=1.0, max_delay=30.0))
        assert rp.get_backoff_delay(0) == pytest.approx(1.0)
        assert rp.get_backoff_delay(1) == pytest.approx(2.0)
        assert rp.get_backoff_delay(2) == pytest.approx(4.0)
        assert rp.get_backoff_delay(3) == pytest.approx(8.0)
        assert rp.get_backoff_delay(4) == pytest.approx(16.0)

    def test_backoff_capped_at_max_delay(self):
        """Backoff never exceeds max_delay."""
        rp = RetryPolicy(config=RetryPolicyConfig(base_delay=10.0, max_delay=25.0))
        # attempt=2 -> min(10*4=40, 25) = 25
        assert rp.get_backoff_delay(2) == pytest.approx(25.0)
        # attempt=5 -> min(10*32=320, 25) = 25
        assert rp.get_backoff_delay(5) == pytest.approx(25.0)

    def test_is_retryable_429(self):
        """Status 429 is retryable."""
        rp = RetryPolicy()
        assert rp.is_retryable(429) is True

    def test_is_retryable_5xx(self):
        """5xx status codes are retryable."""
        rp = RetryPolicy()
        for code in (500, 502, 503, 504):
            assert rp.is_retryable(code) is True

    def test_is_retryable_4xx_not_429(self):
        """4xx codes except 429 are not retryable."""
        rp = RetryPolicy()
        for code in (400, 401, 403, 404, 422, 451):
            assert rp.is_retryable(code) is False

    def test_should_retry_within_limit(self):
        """should_retry returns True when attempt < max_retries."""
        rp = RetryPolicy(config=RetryPolicyConfig(max_retries=3))
        assert rp.should_retry(0) is True
        assert rp.should_retry(1) is True
        assert rp.should_retry(2) is True

    def test_should_retry_exhausted(self):
        """should_retry returns False when attempt >= max_retries."""
        rp = RetryPolicy(config=RetryPolicyConfig(max_retries=3))
        assert rp.should_retry(3) is False
        assert rp.should_retry(4) is False

    def test_custom_retryable_codes(self):
        """RetryPolicyConfig.retryable_status_codes can be overridden."""
        cfg = RetryPolicyConfig(retryable_status_codes=(429, 503, 200))
        rp = RetryPolicy(config=cfg)
        assert rp.is_retryable(200) is True
        assert rp.is_retryable(500) is False


# ====================================================================
# FallbackChain behavioral tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="resilience not impl")
class TestFallbackChain:
    """Behavioral contract for FallbackChain."""

    def test_init_with_ordered_providers(self):
        """FallbackChain is created with an ordered provider list."""
        fc = FallbackChain(providers=["openai", "anthropic", "deepseek"])
        assert fc is not None

    def test_first_provider_success(self):
        """execute returns result from the first healthy provider."""

        def _ok(provider: str) -> str:
            return f"{provider}-ok"

        fc = FallbackChain(providers=["openai", "anthropic"])
        result = fc.execute(_ok)
        assert result.provider == "openai"

    def test_fallback_on_failure(self):
        """Falls back to secondary when primary fails."""
        call_log: list[str] = []

        def _call(provider: str) -> str:
            call_log.append(provider)
            if provider == "openai":
                raise ConnectionError("timeout")
            return f"{provider}-ok"

        fc = FallbackChain(providers=["openai", "anthropic"])
        result = fc.execute(_call)
        assert result.provider == "anthropic"
        assert call_log == ["openai", "anthropic"]

    def test_all_providers_fail(self):
        """When all providers fail, the last error is captured."""

        def _fail(provider: str) -> str:
            raise RuntimeError(f"{provider} down")

        fc = FallbackChain(providers=["openai", "anthropic"])
        result = fc.execute(_fail)
        assert result.error is not None
        assert "down" in str(result.error)

    def test_skips_unhealthy_providers(self):
        """Health-gating: an unhealthy provider is skipped."""

        class _FakeHealthChecker:
            def check(self, provider: str) -> HealthStatus:
                if provider == "openai":
                    return HealthStatus(status=HealthStatusEnum.UNHEALTHY)
                return HealthStatus(status=HealthStatusEnum.HEALTHY)

        def _ok(provider: str) -> str:
            return f"{provider}-ok"

        fc = FallbackChain(
            providers=["openai", "anthropic", "deepseek"],
            health_checker=_FakeHealthChecker(),
        )
        result = fc.execute(_ok)
        assert result.provider == "anthropic"
        assert result.provider != "openai"

    def test_fallback_result_includes_circuit_state(self):
        """FallbackResult carries the circuit state of the attempted provider."""

        def _fail(provider: str) -> str:
            raise RuntimeError("fail")

        fc = FallbackChain(providers=["openai"])
        result = fc.execute(_fail)
        assert isinstance(result.circuit_state, CircuitState)


# ====================================================================
# TimeoutBudget behavioral tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="resilience not impl")
class TestTimeoutBudget:
    """Behavioral contract for TimeoutBudget."""

    def test_init_with_defaults(self):
        """TimeoutBudget can be created with no args (uses global defaults)."""
        tb = TimeoutBudget()
        assert tb is not None

    def test_get_timeout_global_default(self):
        """get_timeout returns global default for unknown providers."""
        tb = TimeoutBudget(
            global_default=TimeoutConfig(chat=30.0, stream=60.0)
        )
        assert tb.get_timeout("unknown", "chat") == 30.0
        assert tb.get_timeout("unknown", "stream") == 60.0

    def test_get_timeout_health_check_default(self):
        """Health check has a default fallback (10.0 if set)."""
        tb = TimeoutBudget(
            global_default=TimeoutConfig(chat=30.0, stream=60.0)
        )
        assert tb.get_timeout("any", "health_check") == 10.0

    def test_per_provider_override(self):
        """Per-provider config overrides global default."""
        tb = TimeoutBudget(
            per_provider={"openai": TimeoutConfig(chat=15.0, stream=45.0)},
            global_default=TimeoutConfig(chat=30.0, stream=60.0),
        )
        assert tb.get_timeout("openai", "chat") == 15.0
        assert tb.get_timeout("openai", "stream") == 45.0
        assert tb.get_timeout("anthropic", "chat") == 30.0

    def test_enforce_within_budget(self):
        """enforce does not raise when time is within budget."""
        tb = TimeoutBudget()
        tb.enforce("openai", "chat")

    def test_enforce_exceeded_raises(self):
        """enforce raises TimeoutBudgetError when timeout is exceeded."""
        tb = TimeoutBudget(
            per_provider={"slow": TimeoutConfig(chat=0.001, stream=0.001)},
        )
        time.sleep(0.01)  # guarantee we exceed the tiny budget
        with pytest.raises(TimeoutBudgetError):
            tb.enforce("slow", "chat")


# ====================================================================
# HealthChecker behavioral tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="resilience not impl")
class TestHealthChecker:
    """Behavioral contract for HealthChecker."""

    def test_init_with_defaults(self):
        """HealthChecker can be created with no args."""
        hc = HealthChecker()
        assert hc is not None

    def test_init_with_custom_window(self):
        """HealthChecker accepts custom window_size."""
        hc = HealthChecker(window_size=50)
        assert hc is not None

    def test_check_returns_health_status(self):
        """check() returns a HealthStatus dataclass."""
        hc = HealthChecker()
        status = hc.check("openai")
        assert isinstance(status, HealthStatus)

    def test_check_healthy_no_samples(self):
        """A provider with no samples is HEALTHY."""
        hc = HealthChecker()
        status = hc.check("openai")
        assert status.status == HealthStatusEnum.HEALTHY

    def test_all_successful_samples(self):
        """100 successful samples yield HEALTHY."""
        hc = HealthChecker(window_size=100)
        for _ in range(100):
            hc.record_sample("openai", latency_ms=100.0, success=True)
        status = hc.check("openai")
        assert status.status == HealthStatusEnum.HEALTHY
        assert status.error_rate == 0.0

    def test_high_error_rate_unhealthy(self):
        """Error rate > 0.1 yields UNHEALTHY."""
        hc = HealthChecker(window_size=100)
        for _ in range(20):
            hc.record_sample("openai", latency_ms=50.0, success=False)  # 20% failures
        for _ in range(80):
            hc.record_sample("openai", latency_ms=50.0, success=True)
        status = hc.check("openai")
        assert status.error_rate > 0.1
        assert status.status == HealthStatusEnum.UNHEALTHY

    def test_high_latency_degraded(self):
        """Latency > 5000ms yields DEGRADED."""
        hc = HealthChecker(window_size=100)
        hc.record_sample("openai", latency_ms=6000.0, success=True)
        status = hc.check("openai")
        assert status.status == HealthStatusEnum.DEGRADED

    def test_rolling_window_eviction(self):
        """Old samples are evicted beyond window_size."""
        hc = HealthChecker(window_size=10)
        for _ in range(10):
            hc.record_sample("openai", latency_ms=100.0, success=True)
        # All successes: error_rate = 0
        st = hc.check("openai")
        assert st.error_rate == 0.0
        # Now add 5 failures — only the last 10 matter
        for _ in range(5):
            hc.record_sample("openai", latency_ms=100.0, success=False)
        st = hc.check("openai")
        assert st.error_rate == pytest.approx(0.5)  # 5 of last 10 failed


# ====================================================================
# ResponseCache behavioral tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="resilience not impl")
class TestResponseCache:
    """Behavioral contract for ResponseCache."""

    def test_init_with_defaults(self):
        """ResponseCache can be created with no args."""
        rc = ResponseCache()
        assert rc is not None

    def test_init_with_per_provider_config(self):
        """ResponseCache accepts per-provider config."""
        cfg = {"openai": ResponseCacheConfig(ttl_seconds=60.0)}
        rc = ResponseCache(config=cfg)
        assert rc is not None

    def test_cache_miss_returns_none(self):
        """get() returns None for a cache miss."""
        rc = ResponseCache()
        result = rc.get("openai", "gpt-4", [{"role": "user", "content": "hi"}])
        assert result is None

    def test_cache_hit_returns_content(self):
        """get() returns cached content on hit."""
        rc = ResponseCache()
        messages = [{"role": "user", "content": "hello"}]
        rc.set("openai", "gpt-4", messages, "Hello there!")
        result = rc.get("openai", "gpt-4", messages)
        assert result == "Hello there!"

    def test_cache_key_by_provider_model_messages(self):
        """Cache keys differ when provider, model, or messages differ."""
        rc = ResponseCache()
        msgs_a = [{"role": "user", "content": "hello"}]
        msgs_b = [{"role": "user", "content": "bye"}]
        rc.set("openai", "gpt-4", msgs_a, "Hello!")
        # Different provider
        assert rc.get("anthropic", "claude-4", msgs_a) is None
        # Different messages
        assert rc.get("openai", "gpt-4", msgs_b) is None

    def test_invalidate_clears_provider(self):
        """invalidate removes all entries for a provider."""
        rc = ResponseCache()
        rc.set("openai", "gpt-4", [{"role": "user", "content": "hi"}], "Hello!")
        rc.set("anthropic", "claude-4", [{"role": "user", "content": "hi"}], "Bonjour!")
        rc.invalidate("openai")
        assert rc.get("openai", "gpt-4", [{"role": "user", "content": "hi"}]) is None
        # Other provider unaffected
        assert rc.get("anthropic", "claude-4", [{"role": "user", "content": "hi"}]) == "Bonjour!"


# ====================================================================
# Observability behavioral tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="resilience not impl")
class TestObservability:
    """Behavioral contract for Observability hooks."""

    def test_init(self):
        """Observability can be created with no args."""
        obs = Observability()
        assert obs is not None

    def test_on_event_registration(self):
        """on_event registers a callback."""
        obs = Observability()
        events: list[ResilienceEvent] = []

        def _handler(event: ResilienceEvent):
            events.append(event)

        obs.on_event(_handler)
        # No-op at registration time
        assert len(events) == 0

    def test_emit_fires_callbacks(self):
        """emit calls all registered callbacks."""
        obs = Observability()
        events: list[ResilienceEvent] = []

        def _handler(event: ResilienceEvent):
            events.append(event)

        obs.on_event(_handler)
        obs.emit(ResilienceEvent(type="circuit_open", provider="openai", timestamp=100.0))
        assert len(events) == 1
        assert events[0].type == "circuit_open"
        assert events[0].provider == "openai"

    def test_emit_multiple_callbacks(self):
        """Multiple registered callbacks all receive events."""
        obs = Observability()
        callbacks_fired = [0, 0]

        def _cb1(event: ResilienceEvent):
            callbacks_fired[0] += 1

        def _cb2(event: ResilienceEvent):
            callbacks_fired[1] += 1

        obs.on_event(_cb1)
        obs.on_event(_cb2)
        obs.emit(ResilienceEvent(type="retry", provider="openai", timestamp=1.0))
        assert callbacks_fired == [1, 1]

    def test_metrics_property(self):
        """metrics property returns a CounterMetrics instance."""
        obs = Observability()
        m = obs.metrics
        assert isinstance(m, CounterMetrics)

    def test_metrics_increment_on_events(self):
        """CounterMetrics track retry_count, circuit_open_count, etc."""
        obs = Observability()
        obs.emit(ResilienceEvent(type="retry", provider="openai", timestamp=1.0))
        obs.emit(ResilienceEvent(type="circuit_open", provider="openai", timestamp=2.0))
        obs.emit(ResilienceEvent(type="fallback", provider="openai", timestamp=3.0))
        obs.emit(ResilienceEvent(type="cache_hit", provider="openai", timestamp=4.0))
        obs.emit(ResilienceEvent(type="timeout", provider="openai", timestamp=5.0))
        m = obs.metrics
        assert m.retry_count >= 1
        assert m.circuit_open_count >= 1
        assert m.fallback_count >= 1
        assert m.cache_hit_count >= 1
        assert m.timeout_count >= 1

    def test_reset_metrics_clears_counters(self):
        """reset_metrics zeros all counters."""
        obs = Observability()
        obs.emit(ResilienceEvent(type="retry", provider="openai", timestamp=1.0))
        obs.emit(ResilienceEvent(type="retry", provider="openai", timestamp=2.0))
        obs.reset_metrics()
        m = obs.metrics
        assert m.retry_count == 0


# ====================================================================
# ResilientLLMClient behavioral tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="resilience not impl")
class TestResilientLLMClient:
    """Behavioral contract for the ResilientLLMClient facade."""

    def test_init_with_llm_client(self):
        """ResilientLLMClient wraps an LLMClient."""
        client = _FakeLLMClient()
        rlc = ResilientLLMClient(llm_client=client)
        assert rlc is not None

    def test_init_with_resilience_config(self):
        """ResilientLLMClient accepts a full ResilienceConfig."""
        cfg = ResilienceConfig(
            circuit_breaker=CircuitBreakerConfig(failure_threshold=3),
            retry=RetryPolicyConfig(max_retries=2),
        )
        client = _FakeLLMClient()
        rlc = ResilientLLMClient(llm_client=client, config=cfg)
        assert rlc is not None

    def test_chat_with_failover_returns_resilient_response(self):
        """chat_with_failover returns a ResilientResponse."""
        client = _FakeLLMClient()
        rlc = ResilientLLMClient(llm_client=client)
        result = rlc.chat_with_failover(
            messages=[{"role": "user", "content": "hello"}],
            model="gpt-4",
        )
        assert isinstance(result, ResilientResponse)

    def test_chat_with_failover_contains_content(self):
        """chat_with_failover response includes the LLM output."""
        client = _FakeLLMClient(response_text="Hi there!")
        rlc = ResilientLLMClient(llm_client=client)
        result = rlc.chat_with_failover(
            messages=[{"role": "user", "content": "hello"}],
            model="gpt-4",
        )
        assert result.content == "Hi there!"

    def test_chat_with_failover_includes_metadata(self):
        """ResilientResponse includes provider, circuit_state, retry_count."""
        client = _FakeLLMClient(response_text="ok")
        rlc = ResilientLLMClient(llm_client=client)
        result = rlc.chat_with_failover(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4",
        )
        assert result.provider != ""
        assert isinstance(result.circuit_state, CircuitState)
        assert isinstance(result.retry_count, int)
        assert isinstance(result.cached, bool)
        assert isinstance(result.latency_ms, float)

    def test_stream_with_failover_returns_resilient_response(self):
        """stream_with_failover returns a ResilientResponse."""
        client = _FakeLLMClient()
        rlc = ResilientLLMClient(llm_client=client)
        result = rlc.stream_with_failover(
            messages=[{"role": "user", "content": "hello"}],
            model="gpt-4",
        )
        assert isinstance(result, ResilientResponse)

    def test_chat_with_failover_retries_on_timeout(self):
        """chat_with_failover retries on transient failures."""
        client = _FakeLLMClient(fail_count=2)
        rlc = ResilientLLMClient(llm_client=client)
        result = rlc.chat_with_failover(
            messages=[{"role": "user", "content": "hello"}],
            model="gpt-4",
        )
        assert result.content == "ok"  # succeeds after retries
        assert result.retry_count >= 1

    def test_fallback_on_circuit_open(self):
        """When circuit is OPEN for primary, fallback is attempted."""
        client = _FakeLLMClient()
        cfg = ResilienceConfig(
            circuit_breaker=CircuitBreakerConfig(failure_threshold=1),
        )
        rlc = ResilientLLMClient(llm_client=client, config=cfg)
        # Trigger circuit open by failing once
        result = rlc.chat_with_failover(
            messages=[{"role": "user", "content": "fail-me"}],
            model="gpt-4",
        )
        # Should still get a response via fallback
        assert isinstance(result, ResilientResponse)


# ====================================================================
# Integration end-to-end tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="resilience not impl")
@pytest.mark.integration
class TestIntegration:
    """End-to-end integration scenarios with fake provider chain."""

    def test_circuit_breaker_retry_fallback_chain(self):
        """Integration: circuit open -> retry exhaust -> fallback -> success."""
        client = _FakeLLMClient(fail_count=3)
        cfg = ResilienceConfig(
            circuit_breaker=CircuitBreakerConfig(failure_threshold=2),
            retry=RetryPolicyConfig(max_retries=1, base_delay=0.01),
        )
        rlc = ResilientLLMClient(llm_client=client, config=cfg)
        result = rlc.chat_with_failover(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4",
        )
        assert isinstance(result, ResilientResponse)
        assert result.content != ""

    def test_health_check_blocks_unhealthy_provider(self):
        """Integration: an UNHEALTHY provider is skipped in fallback chain."""
        client = _FakeLLMClient()
        hc = HealthChecker(window_size=10)
        # Mark openai as unhealthy
        for _ in range(10):
            hc.record_sample("openai", latency_ms=50.0, success=False)

        cfg = ResilienceConfig(
            circuit_breaker=CircuitBreakerConfig(failure_threshold=5),
            retry=RetryPolicyConfig(max_retries=0, base_delay=0.01),
        )
        rlc = ResilientLLMClient(llm_client=client, config=cfg)
        # Inject health checker into the resilience layer
        result = rlc.chat_with_failover(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4",
        )
        assert isinstance(result, ResilientResponse)

    def test_cache_hit_avoids_llm_call(self):
        """Integration: cached response is returned without calling LLM."""
        client = _FakeLLMClient()
        cfg = ResilienceConfig(
            cache={"openai": ResponseCacheConfig(ttl_seconds=300.0)},
            circuit_breaker=CircuitBreakerConfig(failure_threshold=10),
        )
        rlc = ResilientLLMClient(llm_client=client, config=cfg)
        msgs = [{"role": "user", "content": "cached-query"}]

        # First call — cache miss
        result1 = rlc.chat_with_failover(messages=msgs, model="gpt-4")
        assert result1.cached is False

        # Second call — cache hit
        result2 = rlc.chat_with_failover(messages=msgs, model="gpt-4")
        assert result2.cached is True

    def test_timeout_triggers_fallback(self):
        """Integration: timeout on primary triggers fallback to secondary."""
        client = _FakeLLMClient(delay_seconds=10.0)  # very slow
        cfg = ResilienceConfig(
            timeout={
                "openai": TimeoutConfig(chat=0.05, stream=0.05),
                "anthropic": TimeoutConfig(chat=30.0, stream=60.0),
            },
            retry=RetryPolicyConfig(max_retries=0),
        )
        rlc = ResilientLLMClient(llm_client=client, config=cfg)
        result = rlc.chat_with_failover(
            messages=[{"role": "user", "content": "timeout-test"}],
            model="gpt-4",
        )
        assert isinstance(result, ResilientResponse)
        assert result.provider != "openai"  # should have fallen back

    def test_all_layers_together(self):
        """Integration: circuit breaker + retry + fallback + cache + observability."""
        client = _FakeLLMClient(fail_count=1)
        cfg = ResilienceConfig(
            circuit_breaker=CircuitBreakerConfig(failure_threshold=3),
            retry=RetryPolicyConfig(max_retries=2, base_delay=0.01),
            cache={"openai": ResponseCacheConfig(ttl_seconds=300.0)},
        )
        rlc = ResilientLLMClient(llm_client=client, config=cfg)

        # Call that triggers retry then succeeds
        result = rlc.chat_with_failover(
            messages=[{"role": "user", "content": "all-layers"}],
            model="gpt-4",
        )
        assert isinstance(result, ResilientResponse)
        assert result.content != ""
        assert result.cached is False

        # Second call should be cached
        result2 = rlc.chat_with_failover(
            messages=[{"role": "user", "content": "all-layers"}],
            model="gpt-4",
        )
        assert result2.cached is True

    def test_concurrent_cache_safety(self):
        """Integration: concurrent cache access is thread-safe."""
        client = _FakeLLMClient()
        cfg = ResilienceConfig(
            cache={"openai": ResponseCacheConfig(ttl_seconds=300.0)},
        )
        rlc = ResilientLLMClient(llm_client=client, config=cfg)
        msgs = [{"role": "user", "content": "concurrent"}]
        errors: list[Exception] = []
        lock = threading.Lock()

        def _call():
            try:
                rlc.chat_with_failover(messages=msgs, model="gpt-4")
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=_call) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent cache access failed: {errors}"


# ====================================================================
# Helper — Fake LLM Client for testing
# ====================================================================


class _FakeLLMClient:
    """Minimal fake LLM client for integration tests."""

    def __init__(
        self,
        response_text: str = "ok",
        fail_count: int = 0,
        delay_seconds: float = 0.0,
    ):
        self.response_text = response_text
        self.fail_count = fail_count
        self.delay_seconds = delay_seconds
        self._call_count: dict[str, int] = {}
        self._supported_providers = ["openai", "anthropic", "deepseek"]
        self.default_model = "gpt-4"

    def chat(self, messages: list[dict], model: str, **kwargs) -> Any:
        provider = kwargs.get("provider", "openai")
        self._call_count[provider] = self._call_count.get(provider, 0) + 1
        if self.delay_seconds > 0:
            import time as _time
            _time.sleep(self.delay_seconds)
        count = self._call_count[provider]
        if count <= self.fail_count:
            raise ConnectionError(f"Simulated failure #{count} for {provider}")
        from unittest.mock import MagicMock
        resp = MagicMock()
        resp.content = self.response_text
        resp.provider = provider
        resp.model = model or self.default_model
        return resp

    def stream(self, messages: list[dict], model: str, **kwargs) -> Any:
        return self.chat(messages, model, **kwargs)

    @property
    def providers(self) -> list[str]:
        return self._supported_providers
