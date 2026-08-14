"""Chaos Engineering for LLM Pipelines.

Provides fault injection, experiment lifecycle management, and
observability hooks for testing LLM pipeline resilience.

Classes:
    FaultInjector       — injects faults (timeout, rate-limit, etc.)
    ChaosScenario       — describes a chaos experiment (target, fault profile, duration)
    ExperimentRunner    — manages experiment lifecycle
    ObservabilityHook   — captures metrics during chaos experiments

Integrates with existing resilience.py circuit breaker and retry patterns.
"""

from __future__ import annotations

import enum
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ======================================================================
# Enums
# ======================================================================


class FaultType(enum.Enum):
    """Types of faults that can be injected."""

    TIMEOUT = "timeout"
    RATE_LIMIT = "rate-limit"
    PARTIAL_RESPONSE = "partial-response"
    PROVIDER_FAILURE = "provider-failure"
    LATENCY_SPIKE = "latency-spike"
    EMPTY_RESPONSE = "empty-response"
    MALFORMED_RESPONSE = "malformed-response"


class ExperimentPhase(enum.Enum):
    """Phases of a chaos experiment."""

    PENDING = "pending"
    PREPARING = "preparing"
    INJECTING = "injecting"
    OBSERVING = "observing"
    CLEANING = "cleaning"
    COMPLETED = "completed"
    FAILED = "failed"


class ExperimentStatus(enum.Enum):
    """Final status of a completed experiment."""

    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    ERROR = "error"


# ======================================================================
# Data classes
# ======================================================================


@dataclass
class FaultProfile:
    """Configuration for a fault injection."""

    fault_type: FaultType = FaultType.TIMEOUT
    duration_ms: float = 1000.0
    probability: float = 1.0
    error_code: int = 500
    error_message: str = "Simulated fault"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChaosScenario:
    """Description of a single chaos experiment scenario.

    Attributes:
        name:                Human-readable experiment name.
        target_provider:     Provider to target (e.g. "openai", "anthropic").
        fault_profile:       Type and parameters of the fault to inject.
        duration_seconds:    How long the experiment runs.
        conditions:          Pre/post conditions dict (e.g. {"min_health": 0.5}).
        abort_on_failure:    Whether to abort the experiment if a check fails.
        tags:                Optional tags for filtering/grouping experiments.
    """

    name: str = ""
    target_provider: str = ""
    fault_profile: FaultProfile = field(default_factory=FaultProfile)
    duration_seconds: float = 10.0
    conditions: dict[str, Any] = field(default_factory=dict)
    abort_on_failure: bool = True
    tags: list[str] = field(default_factory=list)


@dataclass
class ExperimentResult:
    """Result of a completed chaos experiment."""

    scenario_name: str = ""
    target_provider: str = ""
    status: ExperimentStatus = ExperimentStatus.PASSED
    phase: ExperimentPhase = ExperimentPhase.COMPLETED
    duration_ms: float = 0.0
    faults_injected: int = 0
    errors_caught: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    details: str = ""


@dataclass
class MetricSnapshot:
    """A metrics snapshot captured during an experiment."""

    timestamp: float = 0.0
    phase: ExperimentPhase = ExperimentPhase.OBSERVING
    latency_ms: float = 0.0
    error_count: int = 0
    request_count: int = 0
    circuit_state: str = "CLOSED"
    health_score: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ======================================================================
# FaultInjector
# ======================================================================


class FaultInjector:
    """Injects faults into LLM provider calls for chaos testing.

    Supports injecting timeouts, rate-limit errors, partial responses,
    provider failures, latency spikes, empty responses, and malformed responses.
    """

    def __init__(
        self,
        time_func: Callable[[], float] | None = None,
    ) -> None:
        self._time_func = time_func or time.time
        self._active_faults: list[tuple[ChaosScenario, float]] = []
        self._lock = threading.Lock()
        self._injection_count = 0

    @property
    def injection_count(self) -> int:
        return self._injection_count

    def register_scenario(self, scenario: ChaosScenario) -> None:
        """Register a chaos scenario for injection.

        The scenario's fault will be injected on matching calls until
        the scenario's duration expires.
        """
        with self._lock:
            self._active_faults.append((scenario, self._time_func()))

    def unregister_scenario(self, scenario_name: str) -> None:
        """Remove a scenario by name."""
        with self._lock:
            self._active_faults = [
                (s, t) for s, t in self._active_faults if s.name != scenario_name
            ]

    def _get_active_faults(
        self, provider: str
    ) -> list[tuple[ChaosScenario, float]]:
        """Return active (non-expired) scenarios for the given provider."""
        now = self._time_func()
        active: list[tuple[ChaosScenario, float]] = []
        expired: list[tuple[ChaosScenario, float]] = []
        for scenario, start_time in self._active_faults:
            elapsed = (now - start_time) * 1000.0
            if elapsed >= scenario.duration_seconds * 1000.0:
                expired.append((scenario, start_time))
            elif scenario.target_provider == provider:
                active.append((scenario, start_time))
        # Clean up expired
        for item in expired:
            self._active_faults.remove(item)
        return active

    def should_inject(self, provider: str) -> bool:
        """Check if any active fault scenario targets the given provider."""
        with self._lock:
            faults = self._get_active_faults(provider)
            if not faults:
                return False
            # Check probability for each scenario
            for scenario, _ in faults:
                if random.random() < scenario.fault_profile.probability:
                    return True
            return False

    def inject_fault(self, provider: str) -> dict[str, Any] | None:
        """Inject a fault for the given provider.

        Returns a fault response dict if a fault matches, or None if no
        fault should be injected (call proceeds normally).
        """
        with self._lock:
            faults = self._get_active_faults(provider)
            if not faults:
                return None

            for scenario, _ in faults:
                profile = scenario.fault_profile
                if random.random() < profile.probability:
                    self._injection_count += 1
                    return self._build_fault_response(profile)

            return None

    def _build_fault_response(self, profile: FaultProfile) -> dict[str, Any]:
        """Build a fault response dict based on the fault type."""
        base: dict[str, Any] = {
            "fault_type": profile.fault_type.value,
            "error_code": profile.error_code,
            "error_message": profile.error_message,
            "duration_ms": profile.duration_ms,
            "metadata": profile.metadata.copy(),
        }

        if profile.fault_type == FaultType.TIMEOUT:
            base["error"] = "timeout"
            return base

        if profile.fault_type == FaultType.RATE_LIMIT:
            base["error"] = "rate_limit_exceeded"
            base["retry_after_ms"] = profile.duration_ms
            return base

        if profile.fault_type == FaultType.PARTIAL_RESPONSE:
            base["error"] = "partial_response"
            base["partial_content"] = "Partial response (simulated)"
            return base

        if profile.fault_type == FaultType.PROVIDER_FAILURE:
            base["error"] = "provider_unavailable"
            return base

        if profile.fault_type == FaultType.LATENCY_SPIKE:
            base["latency_ms"] = profile.duration_ms
            base["error"] = "latency_spike"
            return base

        if profile.fault_type == FaultType.EMPTY_RESPONSE:
            base["error"] = "empty_response"
            base["content"] = ""
            return base

        if profile.fault_type == FaultType.MALFORMED_RESPONSE:
            base["error"] = "malformed_response"
            base["raw_response"] = "<<<INVALID JSON>>>"
            return base

        return base

    def clear(self) -> None:
        """Remove all active fault scenarios."""
        with self._lock:
            self._active_faults.clear()
            self._injection_count = 0


# ======================================================================
# ObservabilityHook
# ======================================================================


class ObservabilityHook:
    """Captures metrics during chaos experiments.

    Records latency, error counts, request counts, circuit state, and
    health scores at intervals during an experiment.
    """

    def __init__(self) -> None:
        self._snapshots: list[MetricSnapshot] = []
        self._lock = threading.Lock()
        self._callbacks: list[Callable[[MetricSnapshot], None]] = []

    @property
    def snapshots(self) -> list[MetricSnapshot]:
        with self._lock:
            return list(self._snapshots)

    def on_snapshot(self, callback: Callable[[MetricSnapshot], None]) -> None:
        """Register a callback to receive each snapshot."""
        self._callbacks.append(callback)

    def capture(
        self,
        phase: ExperimentPhase = ExperimentPhase.OBSERVING,
        latency_ms: float = 0.0,
        error_count: int = 0,
        request_count: int = 0,
        circuit_state: str = "CLOSED",
        health_score: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> MetricSnapshot:
        """Capture a metrics snapshot at the current moment."""
        snapshot = MetricSnapshot(
            timestamp=time.time(),
            phase=phase,
            latency_ms=latency_ms,
            error_count=error_count,
            request_count=request_count,
            circuit_state=circuit_state,
            health_score=health_score,
            metadata=metadata or {},
        )
        with self._lock:
            self._snapshots.append(snapshot)
        for cb in self._callbacks:
            cb(snapshot)
        return snapshot

    def get_average_latency(self, phase: ExperimentPhase | None = None) -> float:
        """Calculate average latency across captured snapshots."""
        with self._lock:
            relevant = (
                [s for s in self._snapshots if s.phase == phase]
                if phase
                else self._snapshots
            )
            if not relevant:
                return 0.0
            return sum(s.latency_ms for s in relevant) / len(relevant)

    def get_error_rate(self) -> float:
        """Calculate error rate (total errors / total requests)."""
        with self._lock:
            total_requests = sum(s.request_count for s in self._snapshots)
            total_errors = sum(s.error_count for s in self._snapshots)
            if total_requests == 0:
                return 0.0
            return total_errors / total_requests

    def reset(self) -> None:
        """Clear all captured snapshots."""
        with self._lock:
            self._snapshots.clear()


# ======================================================================
# ExperimentRunner
# ======================================================================


class ExperimentRunner:
    """Manages the lifecycle of a chaos experiment.

    Phases: PREPARE → INJECT → OBSERVE → CLEAN
    """

    def __init__(
        self,
        fault_injector: FaultInjector | None = None,
        observability_hook: ObservabilityHook | None = None,
    ) -> None:
        self._fault_injector = fault_injector or FaultInjector()
        self._observability_hook = observability_hook or ObservabilityHook()
        self._current_scenario: ChaosScenario | None = None
        self._phase = ExperimentPhase.PENDING
        self._lock = threading.Lock()
        self._start_time: float = 0.0
        self._on_phase_change: list[
            Callable[[ExperimentPhase, ExperimentPhase], None]
        ] = []

    @property
    def phase(self) -> ExperimentPhase:
        return self._phase

    @property
    def current_scenario(self) -> ChaosScenario | None:
        return self._current_scenario

    @property
    def fault_injector(self) -> FaultInjector:
        return self._fault_injector

    @property
    def observability_hook(self) -> ObservabilityHook:
        return self._observability_hook

    def on_phase_change(
        self, callback: Callable[[ExperimentPhase, ExperimentPhase], None]
    ) -> None:
        """Register a callback: (old_phase, new_phase) -> None."""
        self._on_phase_change.append(callback)

    def _set_phase(self, new_phase: ExperimentPhase) -> None:
        with self._lock:
            old_phase = self._phase
            if old_phase == new_phase:
                return
            self._phase = new_phase
        for cb in self._on_phase_change:
            cb(old_phase, new_phase)

    def prepare(self, scenario: ChaosScenario) -> None:
        """Prepare an experiment: validate scenario, set up resources."""
        self._current_scenario = scenario
        self._set_phase(ExperimentPhase.PREPARING)

        # Validate scenario
        if not scenario.name:
            raise ValueError("Scenario name is required")
        if not scenario.target_provider:
            raise ValueError("Scenario target_provider is required")
        if scenario.duration_seconds <= 0:
            raise ValueError("Scenario duration_seconds must be positive")

        # Pre-condition checks
        min_health = scenario.conditions.get("min_health", 0.0)
        if not isinstance(min_health, int | float) or min_health < 0.0:
            raise ValueError("conditions.min_health must be a non-negative number")

        self._start_time = time.time()
        self._observability_hook.reset()

    def inject(self) -> None:
        """Start injecting faults according to the scenario."""
        if self._current_scenario is None:
            raise RuntimeError("No scenario prepared. Call prepare() first.")

        self._set_phase(ExperimentPhase.INJECTING)
        self._fault_injector.register_scenario(self._current_scenario)

        self._observability_hook.capture(
            phase=ExperimentPhase.INJECTING,
            health_score=1.0,
        )

    def observe(self) -> list[MetricSnapshot]:
        """Observe and collect metrics during the experiment.

        Captures a snapshot and returns accumulated snapshots.
        """
        if self._current_scenario is None:
            raise RuntimeError("No scenario prepared. Call prepare() first.")

        self._set_phase(ExperimentPhase.OBSERVING)

        # In a real implementation this would run for duration_seconds
        # collecting real-time metrics. For now, capture one snapshot.
        self._observability_hook.capture(
            phase=ExperimentPhase.OBSERVING,
            error_count=self._fault_injector.injection_count,
            request_count=self._fault_injector.injection_count,
            circuit_state="CLOSED",
        )
        return self._observability_hook.snapshots

    def clean(self) -> ExperimentResult:
        """Clean up: unregister faults, compile result."""
        if self._current_scenario is None:
            raise RuntimeError("No scenario prepared. Call prepare() first.")

        self._set_phase(ExperimentPhase.CLEANING)

        scenario = self._current_scenario
        self._fault_injector.unregister_scenario(scenario.name)

        elapsed_ms = (time.time() - self._start_time) * 1000.0

        # Determine status
        injections = self._fault_injector.injection_count
        error_rate = self._observability_hook.get_error_rate()
        status = ExperimentStatus.PASSED
        if error_rate > 0.5:
            status = ExperimentStatus.FAILED
        elif injections == 0:
            status = ExperimentStatus.PARTIAL

        result = ExperimentResult(
            scenario_name=scenario.name,
            target_provider=scenario.target_provider,
            status=status,
            phase=ExperimentPhase.COMPLETED,
            duration_ms=elapsed_ms,
            faults_injected=injections,
            errors_caught=0,
            metrics={
                "error_rate": error_rate,
                "avg_latency_ms": self._observability_hook.get_average_latency(),
                "snapshots_count": len(self._observability_hook.snapshots),
            },
            details=f"Experiment completed with {injections} faults injected",
        )

        self._set_phase(ExperimentPhase.COMPLETED)
        self._current_scenario = None
        return result

    def run(self, scenario: ChaosScenario) -> ExperimentResult:
        """Run a full experiment lifecycle: prepare → inject → observe → clean.

        This is a convenience method that executes all phases sequentially.
        """
        self.prepare(scenario)
        self.inject()
        self.observe()
        return self.clean()

    def is_running(self) -> bool:
        """Check if an experiment is currently in progress."""
        return self._phase in (
            ExperimentPhase.PREPARING,
            ExperimentPhase.INJECTING,
            ExperimentPhase.OBSERVING,
        )


__all__ = [
    "ChaosScenario",
    "ExperimentPhase",
    "ExperimentResult",
    "ExperimentRunner",
    "ExperimentStatus",
    "FaultInjector",
    "FaultProfile",
    "FaultType",
    "MetricSnapshot",
    "ObservabilityHook",
]
