"""Example: Chaos Engineering for LLM Pipelines.

Demonstrates fault injection, experiment lifecycle, and observability
hooks for testing LLM pipeline resilience.
"""

from __future__ import annotations

from ai_vibe_coding.chaos_engineering import (
    ChaosScenario,
    ExperimentRunner,
    ExperimentStatus,
    FaultInjector,
    FaultProfile,
    FaultType,
    ObservabilityHook,
)


def fault_injector_example() -> None:
    """Demonstrates injecting different fault types."""
    print("=== FaultInjector Example ===")

    injector = FaultInjector()

    # Register a timeout fault scenario
    timeout_scenario = ChaosScenario(
        name="openai-timeout",
        target_provider="openai",
        duration_seconds=10.0,
        fault_profile=FaultProfile(
            fault_type=FaultType.TIMEOUT,
            duration_ms=3000.0,
            error_code=504,
            error_message="Gateway Timeout (simulated)",
        ),
    )
    injector.register_scenario(timeout_scenario)
    print(f"  Registered scenario: '{timeout_scenario.name}'")

    # Inject a fault
    result = injector.inject_fault("openai")
    if result:
        print(f"  Injected fault: {result['fault_type']}")
        print(f"    Error: {result['error']}")
        print(f"    Code: {result['error_code']}")
        print(f"    Duration: {result['duration_ms']}ms")
    else:
        print("  Random chance didn't trigger this time")

    print(f"  Total injections: {injector.injection_count}")

    # Clean up
    injector.clear()


def experiment_lifecycle_example() -> None:
    """Full experiment lifecycle: prepare → inject → observe → clean."""
    print("\n=== ExperimentRunner Lifecycle Example ===")

    fixture = FaultInjector()
    hook = ObservabilityHook()
    runner = ExperimentRunner(fault_injector=fixture, observability_hook=hook)

    scenario = ChaosScenario(
        name="latency-spike-test",
        target_provider="anthropic",
        duration_seconds=5.0,
        fault_profile=FaultProfile(
            fault_type=FaultType.LATENCY_SPIKE,
            duration_ms=2000.0,
            probability=0.5,
        ),
        tags=["latency", "anthropic", "chaos"],
    )

    print(f"  Phase: {runner.phase.value}")
    runner.prepare(scenario)
    print(f"  Phase: {runner.phase.value} — scenario validated")

    runner.inject()
    print(f"  Phase: {runner.phase.value} — faults registered")

    runner.observe()
    print(f"  Phase: {runner.phase.value} — metrics captured")
    print(f"    Snapshots: {len(hook.snapshots)}")

    result = runner.clean()
    print(f"  Phase: {runner.phase.value}")
    print(f"  Result: {result.status.value}")
    print(f"    Duration: {result.duration_ms:.1f}ms")
    print(f"    Faults injected: {result.faults_injected}")


def all_fault_types_example() -> None:
    """Demonstrates all supported fault types."""
    print("\n=== All Fault Types ===")

    injector = FaultInjector()

    fault_types = [
        FaultType.TIMEOUT,
        FaultType.RATE_LIMIT,
        FaultType.PARTIAL_RESPONSE,
        FaultType.PROVIDER_FAILURE,
        FaultType.LATENCY_SPIKE,
        FaultType.EMPTY_RESPONSE,
        FaultType.MALFORMED_RESPONSE,
    ]

    for ft in fault_types:
        scenario = ChaosScenario(
            name=f"test-{ft.value}",
            target_provider="openai",
            duration_seconds=1.0,
            fault_profile=FaultProfile(fault_type=ft, probability=1.0),
        )
        injector.clear()
        injector.register_scenario(scenario)
        result = injector.inject_fault("openai")
        if result:
            print(f"  {ft.value:20s} → {result.get('error', 'ok'):30s}")

    injector.clear()


def observability_hook_example() -> None:
    """ObservabilityHook with callbacks."""
    print("\n=== ObservabilityHook with Callbacks ===")

    hook = ObservabilityHook()

    # Register a callback
    def snapshot_logger(snapshot):
        print(f"    [snapshot] phase={snapshot.phase.value}, "
              f"latency={snapshot.latency_ms:.0f}ms, "
              f"errors={snapshot.error_count}")

    hook.on_snapshot(snapshot_logger)

    from ai_vibe_coding.chaos_engineering import ExperimentPhase
    hook.capture(phase=ExperimentPhase.INJECTING, latency_ms=150.0, error_count=0, request_count=10)
    hook.capture(phase=ExperimentPhase.OBSERVING, latency_ms=320.0, error_count=2, request_count=10)

    print(f"  Average latency: {hook.get_average_latency():.1f}ms")
    print(f"  Error rate: {hook.get_error_rate():.2%}")


def composition_with_resilience() -> None:
    """Conceptual integration with circuit breaker and retry patterns."""
    print("\n=== Composition with Resilience Patterns ===")
    print("""
    ┌─────────────────────────────────────────────────────┐
    │ Chaos Experiment                                   │
    │  ┌──────────┐  ┌───────────┐  ┌──────────────────┐ │
    │  │Fault     │  │Circuit    │  │ObservabilityHook │ │
    │  │Injector  │→→│Breaker    │→→│(metrics capture) │ │
    │  └──────────┘  └───────────┘  └──────────────────┘ │
    └─────────────────────────────────────────────────────┘
              │
              ▼
    ┌─────────────────────────────────────────────────────┐
    │ Resilient LLM Pipeline                              │
    │  ┌──────────────┐  ┌────────────┐  ┌─────────────┐ │
    │  │TokenBucket   │  │RetryPolicy │  │FallbackChain│ │
    │  │(rate limit)  │→→│(backoff)   │→→│(failover)   │ │
    │  └──────────────┘  └────────────┘  └─────────────┘ │
    └─────────────────────────────────────────────────────┘
    """)
    print("  Chaos experiments validate that the resilience layers")
    print("  correctly handle: timeouts, rate limits, provider failures,")
    print("  partial responses, and latency spikes.")


if __name__ == "__main__":
    fault_injector_example()
    experiment_lifecycle_example()
    all_fault_types_example()
    observability_hook_example()
    composition_with_resilience()
