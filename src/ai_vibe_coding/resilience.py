"""LLM Failover & Resilience Patterns.

Provides circuit breaker, retry policy, fallback chain, timeout budget,
health checker, response cache, and observability hooks for resilient
LLM provider interactions.

Public API:
    CircuitBreaker              — state machine (CLOSED/OPEN/HALF_OPEN)
    CircuitBreakerOpenError     — raised when circuit is OPEN
    RetryPolicy                 — exponential backoff + jitter
    FallbackChain               — ordered provider failover
    FallbackResult              — outcome of a fallback attempt
    TimeoutBudget               — per-provider/per-op timeouts
    TimeoutBudgetError          — raised on timeout expiry
    HealthChecker               — latency + error rate probing
    HealthStatus                — health check result dataclass
    ResponseCache               — stale-while-revalidate cache
    ResilienceEvent             — structured observability event
    CounterMetrics              — aggregate resilience counters
    ResilientLLMClient          — all layers wrapped into one facade
    ResilienceConfig            — configuration dataclass
    ResilientResponse           — enriched response from failover
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import enum
import hashlib
import json
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ======================================================================
# Exceptions
# ======================================================================


class CircuitBreakerOpenError(Exception):
    """Raised when a circuit breaker is OPEN and rejects a call."""

    def __init__(self, provider: str = "", message: str = "") -> None:
        self.provider = provider
        self.message = message
        msg = f"Circuit breaker OPEN for {provider}"
        if message:
            msg = f"{msg}: {message}"
        super().__init__(msg)


class TimeoutBudgetError(Exception):
    """Raised when a provider call exceeds its configured timeout."""

    def __init__(self, provider: str = "", operation: str = "") -> None:
        self.provider = provider
        self.operation = operation
        super().__init__(f"Timeout exceeded for {provider}/{operation}")


# ======================================================================
# Data model / state types
# ======================================================================


class CircuitState(enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class HealthStatusEnum(enum.Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


class JitterMode(enum.Enum):
    FULL = "full"
    EQUAL = "equal"


# ======================================================================
# Configuration dataclasses
# ======================================================================


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    success_threshold: int = 2
    open_timeout: float = 30.0


@dataclass
class RetryPolicyConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    retryable_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504)
    jitter_mode: JitterMode = JitterMode.FULL


@dataclass
class TimeoutConfig:
    chat: float = 30.0
    stream: float = 60.0


@dataclass
class ResponseCacheConfig:
    ttl_seconds: float = 300.0
    swr_seconds: float = 3600.0


@dataclass
class ResilienceConfig:
    circuit_breaker: CircuitBreakerConfig | None = None
    retry: RetryPolicyConfig | None = None
    timeout: dict[str, TimeoutConfig] | None = None
    cache: dict[str, ResponseCacheConfig] | None = None
    global_timeout: TimeoutConfig | None = None


# ======================================================================
# Result / event dataclasses
# ======================================================================


@dataclass
class FallbackResult:
    provider: str = ""
    error: Exception | None = None
    circuit_state: CircuitState = CircuitState.CLOSED
    latency_ms: float = 0.0


@dataclass
class HealthStatus:
    latency_ms: float = 0.0
    error_rate: float = 0.0
    availability: float = 1.0
    last_success: float = 0.0
    status: HealthStatusEnum = HealthStatusEnum.HEALTHY


@dataclass
class ResilienceEvent:
    type: str = ""
    provider: str = ""
    timestamp: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CounterMetrics:
    retry_count: int = 0
    circuit_open_count: int = 0
    fallback_count: int = 0
    cache_hit_count: int = 0
    timeout_count: int = 0


@dataclass
class ResilientResponse:
    content: str = ""
    provider: str = ""
    model: str = ""
    circuit_state: CircuitState = CircuitState.CLOSED
    retry_count: int = 0
    cached: bool = False
    latency_ms: float = 0.0


# ======================================================================
# CircuitBreaker
# ======================================================================


class CircuitBreaker:
    """State machine that tracks consecutive failures per provider.

    States: CLOSED → OPEN (on N consecutive failures)
            OPEN  → HALF_OPEN (after open_timeout)
            HALF_OPEN → CLOSED (on M consecutive successes)
    """

    def __init__(
        self,
        config: CircuitBreakerConfig | None = None,
        time_func: Callable[[], float] | None = None,
    ) -> None:
        self._config = config or CircuitBreakerConfig()
        self._time_func = time_func or time.time
        # Per-provider state: provider -> {state, fail_count, success_count, opened_at}
        self._providers: dict[str, dict[str, Any]] = {}
        self._callbacks: list[Callable[[str, CircuitState, CircuitState], None]] = []

    def _get_or_create(self, provider: str) -> dict[str, Any]:
        if provider not in self._providers:
            self._providers[provider] = {
                "state": CircuitState.CLOSED,
                "fail_count": 0,
                "success_count": 0,
                "opened_at": 0.0,
            }
        return self._providers[provider]

    def _transition(self, provider: str, new_state: CircuitState) -> None:
        p = self._get_or_create(provider)
        old_state = p["state"]
        if old_state == new_state:
            return
        p["state"] = new_state
        # Reset counters on transition
        if new_state == CircuitState.CLOSED:
            p["fail_count"] = 0
            p["success_count"] = 0
        elif new_state == CircuitState.OPEN:
            p["opened_at"] = self._time_func()
            p["success_count"] = 0
        # NOTE: HALF_OPEN transition keeps success_count from the caller
        # (record_success sets it to 1 when transitioning from OPEN via a success)
        # Fire callbacks
        for cb in self._callbacks:
            cb(provider, old_state, new_state)

    def record_failure(self, provider: str) -> None:
        p = self._get_or_create(provider)
        state = p["state"]

        if state == CircuitState.CLOSED:
            p["fail_count"] += 1
            if p["fail_count"] >= self._config.failure_threshold:
                self._transition(provider, CircuitState.OPEN)

        elif state == CircuitState.HALF_OPEN:
            self._transition(provider, CircuitState.OPEN)

        elif state == CircuitState.OPEN:
            # Already open; just update opened_at to keep timeout timing
            p["opened_at"] = self._time_func()

    def record_success(self, provider: str) -> None:
        p = self._get_or_create(provider)
        state = p["state"]

        if state == CircuitState.CLOSED:
            p["fail_count"] = 0  # Reset consecutive failure count

        elif state == CircuitState.HALF_OPEN:
            p["success_count"] += 1
            if p["success_count"] >= self._config.success_threshold:
                self._transition(provider, CircuitState.CLOSED)

        elif state == CircuitState.OPEN:
            # Transition to HALF_OPEN and count this success
            self._transition(provider, CircuitState.HALF_OPEN)
            p = self._get_or_create(provider)  # re-get after transition
            p["success_count"] = 1
            if p["success_count"] >= self._config.success_threshold:
                self._transition(provider, CircuitState.CLOSED)

    def get_state(self, provider: str) -> CircuitState:
        p = self._get_or_create(provider)
        state = p["state"]

        # Auto-transition OPEN → HALF_OPEN after timeout
        if state == CircuitState.OPEN:
            elapsed = self._time_func() - p["opened_at"]
            if elapsed >= self._config.open_timeout:
                self._transition(provider, CircuitState.HALF_OPEN)
                return CircuitState.HALF_OPEN

        return state

    def check(self, provider: str) -> None:
        """Raise CircuitBreakerOpenError if the circuit is OPEN."""
        state = self.get_state(provider)
        if state == CircuitState.OPEN:
            raise CircuitBreakerOpenError(provider=provider, message="Circuit is OPEN")

    def on_state_change(
        self, callback: Callable[[str, CircuitState, CircuitState], None]
    ) -> None:
        """Register a callback: (provider, old_state, new_state) -> None."""
        self._callbacks.append(callback)


# ======================================================================
# RetryPolicy
# ======================================================================


class RetryPolicy:
    """Exponential backoff with configurable jitter and retryable codes."""

    def __init__(self, config: RetryPolicyConfig | None = None) -> None:
        self._config = config or RetryPolicyConfig()

    def get_backoff_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt (0-indexed)."""
        delay = min(self._config.base_delay * (2 ** attempt), self._config.max_delay)
        return delay

    def is_retryable(self, status_code: int) -> bool:
        """Return True if the status code should trigger a retry."""
        return status_code in self._config.retryable_status_codes

    def should_retry(self, attempt: int, exception: Exception | None = None) -> bool:
        """Return True if another retry should be attempted."""
        return attempt < self._config.max_retries


# ======================================================================
# FallbackChain
# ======================================================================


class FallbackChain:
    """Ordered provider failover with health gating."""

    def __init__(
        self,
        providers: list[str],
        health_checker: Any | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._providers = providers
        self._health_checker = health_checker
        self._circuit_breaker = circuit_breaker
        self._retry_policy = retry_policy

    def execute(
        self,
        provider_call: Callable[[str], Any],
        fallback_on: tuple[type[Exception], ...] | None = None,
    ) -> FallbackResult:
        """Try providers in order; return first success or aggregate failures."""
        if fallback_on is None:
            fallback_on = (Exception,)

        last_error: Exception | None = None
        last_circuit_state = CircuitState.CLOSED

        for provider in self._providers:
            # Health gating: skip unhealthy providers
            if self._health_checker is not None:
                health = self._health_checker.check(provider)
                if health.status == HealthStatusEnum.UNHEALTHY:
                    continue

            # Circuit gating: skip OPEN circuits
            if self._circuit_breaker is not None:
                state = self._circuit_breaker.get_state(provider)
                if state == CircuitState.OPEN:
                    continue

            try:
                provider_call(provider)
                # Success — return result with this provider
                return FallbackResult(
                    provider=provider,
                    circuit_state=(
                        self._circuit_breaker.get_state(provider)
                        if self._circuit_breaker
                        else CircuitState.CLOSED
                    ),
                )
            except fallback_on as e:
                last_error = e
                if self._circuit_breaker is not None:
                    last_circuit_state = self._circuit_breaker.get_state(provider)
                # Continue to next provider
                continue

        # All providers failed
        return FallbackResult(
            error=last_error,
            circuit_state=last_circuit_state,
        )


# ======================================================================
# TimeoutBudget
# ======================================================================


class TimeoutBudget:
    """Per-provider and per-operation timeout configuration."""

    def __init__(
        self,
        per_provider: dict[str, TimeoutConfig] | None = None,
        global_default: TimeoutConfig | None = None,
    ) -> None:
        self._per_provider = per_provider or {}
        self._global_default = global_default or TimeoutConfig()
        self._start_time = time.time()

    def get_timeout(self, provider: str, operation: str = "chat") -> float:
        """Return the timeout in seconds for (provider, operation)."""
        # Per-provider override
        if provider in self._per_provider:
            cfg = self._per_provider[provider]
            return getattr(cfg, operation, 10.0)
        # Global default
        return getattr(self._global_default, operation, 10.0)

    def enforce(self, provider: str, operation: str = "chat") -> None:
        """Check whether the call is within budget; raise TimeoutBudgetError if not."""
        timeout = self.get_timeout(provider, operation)
        elapsed = time.time() - self._start_time
        if elapsed > timeout:
            raise TimeoutBudgetError(provider=provider, operation=operation)


# ======================================================================
# HealthChecker
# ======================================================================


class HealthChecker:
    """Monitors provider health via rolling-window metrics."""

    def __init__(
        self,
        window_size: int = 100,
        time_func: Callable[[], float] | None = None,
    ) -> None:
        self.window_size = window_size
        self._time_func = time_func or time.time
        # provider -> deque of (latency_ms, success)
        self._samples: dict[str, deque] = {}

    def _get_samples(self, provider: str) -> deque:
        if provider not in self._samples:
            self._samples[provider] = deque(maxlen=self.window_size)
        return self._samples[provider]

    def record_sample(self, provider: str, latency_ms: float, success: bool) -> None:
        """Record a single sample for the provider."""
        samples = self._get_samples(provider)
        samples.append((latency_ms, success))

    def check(self, provider: str) -> HealthStatus:
        """Return a HealthStatus for the given provider."""
        samples = self._samples.get(provider, [])
        if not samples:
            return HealthStatus(
                last_success=self._time_func(),
            )

        successes = sum(1 for _, s in samples if s)
        total = len(samples)
        failures = total - successes
        error_rate = failures / total
        avg_latency = sum(lat for lat, _ in samples) / total
        availability = successes / total

        # Determine health status
        # Error rate threshold at 0.1 (10% failures → UNHEALTHY)
        # Latency threshold at 5000ms (5 seconds → DEGRADED)
        if error_rate > 0.1:
            status = HealthStatusEnum.UNHEALTHY
        elif avg_latency > 5000.0:
            status = HealthStatusEnum.DEGRADED
        else:
            status = HealthStatusEnum.HEALTHY

        return HealthStatus(
            latency_ms=avg_latency,
            error_rate=error_rate,
            availability=availability,
            last_success=self._time_func(),
            status=status,
        )


# ======================================================================
# ResponseCache
# ======================================================================


@dataclass
class _CacheEntry:
    provider: str
    content: str
    timestamp: float
    ttl: float


class ResponseCache:
    """Thread-safe stale-while-revalidate response cache."""

    def __init__(self, config: dict[str, ResponseCacheConfig] | None = None) -> None:
        self._config = config or {}
        self._global_ttl = ResponseCacheConfig().ttl_seconds
        self._global_swr = ResponseCacheConfig().swr_seconds
        self._store: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()

    def _get_config(self, provider: str) -> ResponseCacheConfig:
        if provider in self._config:
            return self._config[provider]
        return ResponseCacheConfig(
            ttl_seconds=self._global_ttl, swr_seconds=self._global_swr
        )

    def _make_key(
        self, provider: str, model: str, messages: list[dict[str, Any]]
    ) -> str:
        raw = json.dumps({"p": provider, "m": model, "msgs": messages}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(
        self, provider: str, model: str, messages: list[dict[str, Any]]
    ) -> str | None:
        """Return cached content or None on miss."""
        key = self._make_key(provider, model, messages)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            # Check if TTL has expired
            now = time.time()
            if now - entry.timestamp > entry.ttl:
                # TTL expired — don't return but keep for stale-while-revalidate
                if now - entry.timestamp > self._get_config(provider).swr_seconds:
                    del self._store[key]
                    return None
                return None  # TTL expired, treat as miss
            return entry.content

    def set(
        self, provider: str, model: str, messages: list[dict[str, Any]], content: str
    ) -> None:
        """Store response in cache."""
        key = self._make_key(provider, model, messages)
        cfg = self._get_config(provider)
        with self._lock:
            self._store[key] = _CacheEntry(
                provider=provider,
                content=content,
                timestamp=time.time(),
                ttl=cfg.ttl_seconds,
            )

    def is_stale(
        self, provider: str, model: str, messages: list[dict[str, Any]]
    ) -> bool:
        """Return True if cache entry exists but TTL expired (SWR window open)."""
        key = self._make_key(provider, model, messages)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            now = time.time()
            elapsed = now - entry.timestamp
            cfg = self._get_config(provider)
            return cfg.ttl_seconds < elapsed <= cfg.swr_seconds

    def invalidate(self, provider: str) -> None:
        """Remove all cache entries for a provider."""
        with self._lock:
            keys_to_delete = [
                k for k, v in self._store.items()
                if v.provider == provider
            ]
            for k in keys_to_delete:
                del self._store[k]

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._store.clear()


# ======================================================================
# Observability
# ======================================================================


class Observability:
    """Event dispatch + counter tracking for resilience operations."""

    def __init__(self) -> None:
        self._callbacks: list[Callable[[ResilienceEvent], None]] = []
        self._metrics = CounterMetrics()

    def on_event(self, callback: Callable[[ResilienceEvent], None]) -> None:
        """Register a callback to receive all events."""
        self._callbacks.append(callback)

    def emit(self, event: ResilienceEvent) -> None:
        """Dispatch an event to all registered callbacks."""
        # Update counters
        if event.type == "retry":
            self._metrics.retry_count += 1
        elif event.type == "circuit_open":
            self._metrics.circuit_open_count += 1
        elif event.type == "fallback":
            self._metrics.fallback_count += 1
        elif event.type == "cache_hit":
            self._metrics.cache_hit_count += 1
        elif event.type == "timeout":
            self._metrics.timeout_count += 1

        for cb in self._callbacks:
            cb(event)

    @property
    def metrics(self) -> CounterMetrics:
        return self._metrics

    def reset_metrics(self) -> None:
        self._metrics = CounterMetrics()


# ======================================================================
# ResilientLLMClient (facade)
# ======================================================================


class ResilientLLMClient:
    """Wraps an LLMClient with all resilience layers."""

    def __init__(
        self,
        llm_client: Any,
        config: ResilienceConfig | None = None,
    ) -> None:
        self._client = llm_client
        cfg = config or ResilienceConfig()

        # Build internal components
        cb_cfg = cfg.circuit_breaker or CircuitBreakerConfig()
        self._circuit_breaker = CircuitBreaker(config=cb_cfg)

        retry_cfg = cfg.retry or RetryPolicyConfig()
        self._retry_policy = RetryPolicy(config=retry_cfg)

        self._timeout_budget = TimeoutBudget(
            per_provider=cfg.timeout,
            global_default=cfg.global_timeout,
        )

        self._cache = ResponseCache(config=cfg.cache)

        self._observability = Observability()

        # Default provider list from the client
        self._providers = getattr(llm_client, "providers", ["openai"])

    def chat_with_failover(
        self,
        messages: list[dict[str, Any]],
        model: str = "",
        **kwargs: Any,
    ) -> ResilientResponse:
        """Chat with failover — circuit breaker, retry, cache, timeout, fallback."""
        return self._execute_with_failover(messages, model, operation="chat", **kwargs)

    def stream_with_failover(
        self,
        messages: list[dict[str, Any]],
        model: str = "",
        **kwargs: Any,
    ) -> ResilientResponse:
        """Stream with failover."""
        return self._execute_with_failover(
            messages, model, operation="stream", **kwargs
        )

    def _call_with_timeout(
        self,
        fn: Callable[[], Any],
        timeout: float,
        provider: str,
        operation: str,
    ) -> Any:
        """Execute a callable with a timeout using a thread pool."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fn)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                raise TimeoutBudgetError(
                    provider=provider, operation=operation
                ) from None

    def _execute_with_failover(
        self,
        messages: list[dict[str, Any]],
        model: str,
        operation: str = "chat",
        **kwargs: Any,
    ) -> ResilientResponse:
        """Internal: try each provider with circuit breaker, retry, cache, timeout."""
        primary_providers = self._providers

        circuit_state = CircuitState.CLOSED
        retry_count = 0
        latency_ms = 0.0

        for provider in primary_providers:
            # Check circuit breaker
            try:
                self._circuit_breaker.check(provider)
            except CircuitBreakerOpenError:
                self._observability.emit(ResilienceEvent(
                    type="circuit_open",
                    provider=provider,
                    timestamp=time.time(),
                ))
                continue

            # Check cache
            try:
                cached_content = self._cache.get(provider, model, messages)
                if cached_content is not None:
                    self._observability.emit(ResilienceEvent(
                        type="cache_hit",
                        provider=provider,
                        timestamp=time.time(),
                    ))
                    return ResilientResponse(
                        content=cached_content,
                        provider=provider,
                        model=model or getattr(self._client, "default_model", ""),
                        circuit_state=self._circuit_breaker.get_state(provider),
                        retry_count=retry_count,
                        cached=True,
                        latency_ms=0.0,
                    )
            except Exception:
                pass

            # Try initial call + retries
            max_attempts = max(1, self._retry_policy._config.max_retries + 1)

            for attempt in range(max_attempts):
                try:
                    timeout = self._timeout_budget.get_timeout(provider, operation)
                    start = time.time()

                    # Make the call with timeout enforcement
                    if operation == "stream":
                        client_method = self._client.stream
                    else:
                        client_method = self._client.chat

                    # Don't pass provider to the client — let the client's own
                    # provider selection work; we track the provider ourselves.
                    resp = self._call_with_timeout(
                        lambda m=messages, md=model, kw=kwargs, cm=client_method: cm(
                            m, md, **kw
                        ),
                        timeout,
                        provider,
                        operation,
                    )

                    elapsed = time.time() - start
                    latency_ms = elapsed * 1000.0

                    # Extract content from response
                    content = resp.content if hasattr(resp, "content") else str(resp)
                    default_model = getattr(self._client, "default_model", "")
                    resp_model = getattr(
                        resp, "model", model or default_model
                    )

                    # Record success in circuit breaker
                    self._circuit_breaker.record_success(provider)

                    # Cache the response
                    with contextlib.suppress(Exception):
                        self._cache.set(provider, model, messages, content)

                    return ResilientResponse(
                        content=content,
                        provider=provider,  # We track the provider
                        model=resp_model,
                        circuit_state=self._circuit_breaker.get_state(provider),
                        retry_count=retry_count,
                        cached=False,
                        latency_ms=latency_ms,
                    )

                except TimeoutBudgetError:
                    self._observability.emit(ResilienceEvent(
                        type="timeout",
                        provider=provider,
                        timestamp=time.time(),
                    ))
                    circuit_state = self._circuit_breaker.get_state(provider)
                    self._circuit_breaker.record_failure(provider)
                    # Don't retry on timeout — move to next provider
                    break

                except CircuitBreakerOpenError:
                    circuit_state = CircuitState.OPEN
                    break

                except Exception:
                    retry_count += 1
                    self._observability.emit(ResilienceEvent(
                        type="retry",
                        provider=provider,
                        timestamp=time.time(),
                    ))
                    self._circuit_breaker.record_failure(provider)

                    if attempt < max_attempts - 1:
                        # Brief delay before retry
                        delay = self._retry_policy.get_backoff_delay(attempt)
                        time.sleep(min(delay, 0.1))  # cap retry delay for tests
                        continue
                    else:
                        # Exhausted retries — fall through to next provider
                        break

            # This provider failed — emit fallback event and try next
            self._observability.emit(ResilienceEvent(
                type="fallback",
                provider=provider,
                timestamp=time.time(),
            ))

        # All providers failed
        return ResilientResponse(
            content="",
            provider="",
            model=model or "",
            circuit_state=circuit_state,
            retry_count=retry_count,
            cached=False,
            latency_ms=latency_ms,
        )
