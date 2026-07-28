"""Rate Limiting & Quota Management for LLM Pipelines.

Provides:
    TokenBucket           — fixed-capacity token bucket with refill
    SlidingWindowCounter  — per-window request counting
    AdaptiveRateLimiter   — rate adaption based on provider health
    QuotaManager          — per-provider/user quota with cost-aware allocation

All rate limiters are thread-safe and use monotonic time.
"""

from __future__ import annotations

import enum
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# ======================================================================
# RateLimitExceeded exception
# ======================================================================


class RateLimitExceeded(Exception):
    """Raised when a rate limit or quota is exceeded."""

    def __init__(
        self,
        limiter_type: str = "",
        resource: str = "",
        message: str = "",
    ) -> None:
        self.limiter_type = limiter_type
        self.resource = resource
        self.message = message
        parts = [f"Rate limit exceeded for {limiter_type}"]
        if resource:
            parts.append(f"resource={resource}")
        if message:
            parts.append(message)
        super().__init__(": ".join(parts))


# ======================================================================
# Enums
# ======================================================================


class RateLimiterState(enum.Enum):
    """State of an adaptive rate limiter."""

    NORMAL = "NORMAL"
    THROTTLED = "THROTTLED"
    BACKED_OFF = "BACKED_OFF"
    STOPPED = "STOPPED"


class QuotaPeriod(enum.Enum):
    """Time period for quota tracking."""

    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    MONTH = "month"


# ======================================================================
# TokenBucket
# ======================================================================


class TokenBucket:
    """A token bucket rate limiter.

    The bucket holds up to `capacity` tokens and refills at `refill_rate`
    tokens per second.  `consume(tokens)` returns True if enough tokens
    were available (and deducts them), or False otherwise.
    """

    def __init__(
        self,
        capacity: float = 10.0,
        refill_rate: float = 1.0,
        time_func: Callable[[], float] | None = None,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be positive")
        self._capacity = capacity
        self._refill_rate = refill_rate
        self._time_func = time_func or time.monotonic
        self._tokens = capacity
        self._last_refill = self._time_func()
        self._lock = threading.Lock()

    @property
    def capacity(self) -> float:
        return self._capacity

    @property
    def refill_rate(self) -> float:
        return self._refill_rate

    @property
    def available_tokens(self) -> float:
        """Return the current token count (after triggering a refill)."""
        with self._lock:
            self._refill_internal()
            return round(self._tokens, 6)

    def _refill_internal(self) -> None:
        """Refill tokens based on elapsed time (caller must hold lock)."""
        now = self._time_func()
        elapsed = now - self._last_refill
        new_tokens = elapsed * self._refill_rate
        if new_tokens > 0:
            self._tokens = min(self._capacity, self._tokens + new_tokens)
            self._last_refill = now

    def consume(self, tokens: float = 1.0) -> bool:
        """Try to consume *tokens* from the bucket.

        Returns True if tokens were available and deducted.
        Returns False if insufficient tokens remain (no-op).
        """
        if tokens <= 0:
            raise ValueError("tokens must be positive")
        if tokens > self._capacity:
            raise ValueError(
                f"Requested {tokens} tokens exceeds bucket capacity {self._capacity}"
            )

        with self._lock:
            self._refill_internal()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def refill(self, tokens: float | None = None) -> None:
        """Manually add tokens to the bucket.

        If *tokens* is None, refill to full capacity.
        """
        with self._lock:
            if tokens is None:
                self._tokens = self._capacity
            else:
                self._tokens = min(self._capacity, self._tokens + tokens)
            self._last_refill = self._time_func()

    def reset(self) -> None:
        """Reset the bucket to full capacity."""
        with self._lock:
            self._tokens = self._capacity
            self._last_refill = self._time_func()


# ======================================================================
# SlidingWindowCounter
# ======================================================================


class SlidingWindowCounter:
    """Sliding window rate limiter using a counter per time window.

    Tracks request timestamps within a sliding *window_size* (seconds).
    Returns True from allow() if the count in the window is < *max_requests*.
    """

    def __init__(
        self,
        window_size: float = 60.0,
        max_requests: int = 100,
        time_func: Callable[[], float] | None = None,
    ) -> None:
        if window_size <= 0:
            raise ValueError("window_size must be positive")
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        self._window_size = window_size
        self._max_requests = max_requests
        self._time_func = time_func or time.monotonic
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    @property
    def window_size(self) -> float:
        return self._window_size

    @property
    def max_requests(self) -> int:
        return self._max_requests

    @property
    def request_count(self) -> int:
        """Return the number of requests in the current window."""
        with self._lock:
            self._trim()
            return len(self._timestamps)

    def _trim(self) -> None:
        """Remove timestamps outside the current window (caller must hold lock)."""
        cutoff = self._time_func() - self._window_size
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    def allow(self) -> bool:
        """Check and record a request.

        Returns True if the request is within limits and was recorded.
        Returns False if the limit has been reached.
        """
        with self._lock:
            self._trim()
            if len(self._timestamps) >= self._max_requests:
                return False
            self._timestamps.append(self._time_func())
            return True

    def remaining(self) -> int:
        """Return how many requests remain before hitting the limit."""
        with self._lock:
            self._trim()
            return max(0, self._max_requests - len(self._timestamps))

    def reset(self) -> None:
        """Clear all tracked timestamps."""
        with self._lock:
            self._timestamps.clear()

    def time_until_next_slot(self) -> float:
        """Return seconds until the oldest timestamp drops out of the window."""
        with self._lock:
            self._trim()
            if len(self._timestamps) < self._max_requests:
                return 0.0
            oldest = self._timestamps[0]
            return max(0.0, oldest + self._window_size - self._time_func())


# ======================================================================
# AdaptiveRateLimiter
# ======================================================================


class AdaptiveRateLimiter:
    """Rate limiter that adjusts its max rate based on provider health metrics.

    Uses a health score (0.0–1.0) to scale the effective max request rate.
    When health drops, the limiter throttles aggressively and may enter
    BACKED_OFF or STOPPED states.
    """

    def __init__(
        self,
        max_rate: float = 10.0,
        min_rate: float = 0.5,
        health_threshold: float = 0.3,
        time_func: Callable[[], float] | None = None,
    ) -> None:
        if max_rate <= 0:
            raise ValueError("max_rate must be positive")
        if min_rate <= 0:
            raise ValueError("min_rate must be positive")
        if not 0.0 <= health_threshold <= 1.0:
            raise ValueError("health_threshold must be in [0.0, 1.0]")
        self._max_rate = max_rate
        self._min_rate = min_rate
        self._health_threshold = health_threshold
        self._time_func = time_func or time.monotonic
        # Internal state
        self._state = RateLimiterState.NORMAL
        self._current_rate = max_rate
        self._tokens = max_rate
        self._last_refill = self._time_func()
        self._lock = threading.Lock()

    @property
    def state(self) -> RateLimiterState:
        return self._state

    @property
    def current_rate(self) -> float:
        """The effective rate (requests/second) based on current health."""
        return self._current_rate

    def update_health(self, health_score: float) -> None:
        """Update the provider health score and adjust rate accordingly.

        Args:
            health_score: Provider health from 0.0 (unhealthy) to 1.0 (healthy).
        """
        if not 0.0 <= health_score <= 1.0:
            raise ValueError("health_score must be in [0.0, 1.0]")

        with self._lock:
            if health_score >= self._health_threshold:
                # Healthy or slightly degraded — scale rate linearly
                factor = health_score / self._health_threshold
                self._current_rate = min(
                    self._max_rate,
                    self._min_rate + (self._max_rate - self._min_rate) * factor,
                )
                self._state = RateLimiterState.NORMAL
            elif health_score > 0.0:
                # Below threshold — throttle significantly
                self._current_rate = max(
                    self._min_rate,
                    self._max_rate * health_score,
                )
                self._state = RateLimiterState.THROTTLED
            else:
                # Health is 0 — stop
                self._current_rate = self._min_rate * 0.1
                self._state = RateLimiterState.BACKED_OFF

            # Update internal bucket to new rate
            self._tokens = min(self._current_rate, self._tokens)

    def allow(self) -> bool:
        """Check if a request is allowed under the current adapted rate.

        Returns True if allowed, False if rate-limited.
        """
        with self._lock:
            now = self._time_func()
            elapsed = now - self._last_refill
            new_tokens = elapsed * self._current_rate
            if new_tokens > 0:
                self._tokens = min(self._current_rate, self._tokens + new_tokens)
                self._last_refill = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    def reset(self) -> None:
        """Reset to initial state with full rate."""
        with self._lock:
            self._state = RateLimiterState.NORMAL
            self._current_rate = self._max_rate
            self._tokens = self._max_rate
            self._last_refill = self._time_func()


# ======================================================================
# QuotaManager
# ======================================================================


@dataclass
class QuotaConfig:
    """Configuration for a single quota entry."""

    provider: str = ""
    user: str = ""
    max_daily_tokens: float = 1_000_000.0
    max_monthly_cost: float = 100.0
    burst_limit: int = 10
    cost_per_token: float = 0.0


@dataclass
class QuotaUsage:
    """Current usage snapshot for a quota entry."""

    provider: str = ""
    user: str = ""
    tokens_used_today: float = 0.0
    cost_today: float = 0.0
    cost_this_month: float = 0.0
    burst_used: int = 0
    requests_today: int = 0


@dataclass
class CostAwareAllocation:
    """Result of a cost-aware quota allocation decision."""

    provider: str = ""
    user: str = ""
    allocated_tokens: float = 0.0
    estimated_cost: float = 0.0
    remaining_budget: float = 0.0
    burst_used: int = 0


class QuotaManager:
    """Manages per-provider/user quotas with burst handling and cost-aware allocation.

    Tracks daily token usage, monthly cost budgets, and burst capacity.
    """

    def __init__(
        self,
        configs: list[QuotaConfig] | None = None,
        time_func: Callable[[], float] | None = None,
    ) -> None:
        self._time_func = time_func or time.time
        self._lock = threading.Lock()

        # Key: (provider, user) -> QuotaConfig
        self._configs: dict[tuple[str, str], QuotaConfig] = {}
        # Key: (provider, user) -> dict with usage counters
        self._usage: dict[tuple[str, str], dict[str, Any]] = {}

        if configs:
            for cfg in configs:
                self.add_quota(cfg)

    def add_quota(self, config: QuotaConfig) -> None:
        """Register or update a quota configuration."""
        key = (config.provider, config.user)
        with self._lock:
            self._configs[key] = config
            if key not in self._usage:
                self._usage[key] = {
                    "tokens_used_today": 0.0,
                    "cost_today": 0.0,
                    "cost_this_month": 0.0,
                    "burst_used": 0,
                    "requests_today": 0,
                    "day_start": self._time_func(),
                    "month_start": self._time_func(),
                }

    def remove_quota(self, provider: str, user: str) -> None:
        """Remove a quota configuration."""
        key = (provider, user)
        with self._lock:
            self._configs.pop(key, None)
            self._usage.pop(key, None)

    def _get_day_reset(self, usage: dict[str, Any]) -> None:
        """Reset daily counters if a new day has started."""
        now = self._time_func()
        if now - usage["day_start"] > 86400:
            usage["tokens_used_today"] = 0.0
            usage["cost_today"] = 0.0
            usage["requests_today"] = 0
            usage["burst_used"] = 0
            usage["day_start"] = now

    def _get_month_reset(self, usage: dict[str, Any]) -> None:
        """Reset monthly counters if a new month has started."""
        now = self._time_func()
        if now - usage["month_start"] > 2_592_000:  # 30 days
            usage["cost_this_month"] = 0.0
            usage["month_start"] = now

    def check_quota(self, provider: str, user: str) -> bool:
        """Check if the (provider, user) pair has remaining quota.

        Returns True if within limits, False if exceeded.
        """
        key = (provider, user)
        with self._lock:
            if key not in self._configs:
                return True  # No quota configured = no limit
            config = self._configs[key]
            usage = self._usage[key]
            self._get_day_reset(usage)
            self._get_month_reset(usage)

            if usage["tokens_used_today"] >= config.max_daily_tokens:
                return False
            return not usage["cost_this_month"] >= config.max_monthly_cost

    def record_usage(
        self,
        provider: str,
        user: str,
        tokens: float = 0.0,
        cost: float = 0.0,
    ) -> bool:
        """Record token/cost usage for a provider/user pair.

        Returns True if still within quota after recording, False if exceeded.
        """
        key = (provider, user)
        with self._lock:
            if key not in self._configs:
                return True  # No quota configured
            config = self._configs[key]
            usage = self._usage[key]
            self._get_day_reset(usage)
            self._get_month_reset(usage)

            usage["tokens_used_today"] += tokens
            usage["cost_today"] += cost
            usage["cost_this_month"] += cost
            usage["requests_today"] += 1

            # Check limits after recording
            if usage["tokens_used_today"] >= config.max_daily_tokens:
                return False
            return not usage["cost_this_month"] >= config.max_monthly_cost

    def allocate_burst(self, provider: str, user: str) -> bool:
        """Try to allocate a burst request.

        Returns True if burst capacity remains and was consumed.
        """
        key = (provider, user)
        with self._lock:
            if key not in self._configs:
                return True
            config = self._configs[key]
            usage = self._usage[key]
            self._get_day_reset(usage)

            if usage["burst_used"] < config.burst_limit:
                usage["burst_used"] += 1
                return True
            return False

    def cost_aware_allocation(
        self,
        provider: str,
        user: str,
        requested_tokens: float,
    ) -> CostAwareAllocation:
        """Perform cost-aware allocation: allocate tokens within remaining budget.

        Returns a CostAwareAllocation with the actual allocated amount and
        estimated cost.
        """
        key = (provider, user)
        with self._lock:
            if key not in self._configs:
                return CostAwareAllocation(
                    provider=provider,
                    user=user,
                    allocated_tokens=requested_tokens,
                    estimated_cost=0.0,
                    remaining_budget=0.0,
                    burst_used=0,
                )
            config = self._configs[key]
            usage = self._usage[key]
            self._get_day_reset(usage)
            self._get_month_reset(usage)

            # Calculate remaining budget
            month_remaining = config.max_monthly_cost - usage["cost_this_month"]
            day_remaining = config.max_daily_tokens - usage["tokens_used_today"]

            # Maximum tokens we can allocate
            max_by_cost = (
                month_remaining / config.cost_per_token
                if config.cost_per_token > 0
                else float("inf")
            )
            max_by_day_tokens = day_remaining
            allocatable = min(requested_tokens, max_by_day_tokens, max_by_cost)

            if allocatable <= 0:
                return CostAwareAllocation(
                    provider=provider,
                    user=user,
                    allocated_tokens=0.0,
                    estimated_cost=0.0,
                    remaining_budget=month_remaining,
                    burst_used=usage["burst_used"],
                )

            estimated_cost = allocatable * config.cost_per_token
            return CostAwareAllocation(
                provider=provider,
                user=user,
                allocated_tokens=allocatable,
                estimated_cost=estimated_cost,
                remaining_budget=month_remaining - estimated_cost,
                burst_used=usage["burst_used"],
            )

    def get_usage(self, provider: str, user: str) -> QuotaUsage | None:
        """Return the current usage snapshot for a provider/user pair."""
        key = (provider, user)
        with self._lock:
            if key not in self._configs:
                return None
            self._configs[key]
            usage = self._usage[key]
            self._get_day_reset(usage)
            self._get_month_reset(usage)

            return QuotaUsage(
                provider=provider,
                user=user,
                tokens_used_today=usage["tokens_used_today"],
                cost_today=usage["cost_today"],
                cost_this_month=usage["cost_this_month"],
                burst_used=usage["burst_used"],
                requests_today=usage["requests_today"],
            )


__all__ = [
    "AdaptiveRateLimiter",
    "CostAwareAllocation",
    "QuotaConfig",
    "QuotaManager",
    "QuotaPeriod",
    "QuotaUsage",
    "RateLimitExceeded",
    "RateLimiterState",
    "SlidingWindowCounter",
    "TokenBucket",
]
