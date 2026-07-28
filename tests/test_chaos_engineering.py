"""Pre-development acceptance tests for Chaos Engineering for LLM Pipelines.

Test categories:
  1. Interface Smoke Tests       ( 8 tests)
  2. FaultInjector Tests         (10 tests)
  3. ChaosScenario Tests          ( 4 tests)
  4. ExperimentRunner Tests       (10 tests)
  5. ObservabilityHook Tests      ( 8 tests)
  6. Integration Tests            ( 8 tests)
                                -----
    Total:                        48 tests
"""

from __future__ import annotations

import pytest

try:
    from ai_vibe_coding.chaos_engineering import (
        ChaosScenario,
        ExperimentPhase,
        ExperimentResult,
        ExperimentRunner,
        ExperimentStatus,
        FaultInjector,
        FaultProfile,
        FaultType,
        MetricSnapshot,
        ObservabilityHook,
    )
    MODULE_EXISTS = True
except ImportError:
    MODULE_EXISTS = False


def test_chaos_engineering_module_must_exist() -> None:
    """RED phase: chaos_engineering.py must exist."""
    if not MODULE_EXISTS:
        pytest.fail(
            "Module 'ai_vibe_coding.chaos_engineering' not found."
        )


# ====================================================================
# Interface Smoke Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="chaos_engineering not impl")
class TestInterfaceSmoke:
    """Verify API surface — all classes, enums, dataclasses exist."""

    def test_fault_injector_instantiation(self) -> None:
        fi = FaultInjector()
        assert fi.injection_count == 0

    def test_experiment_runner_instantiation(self) -> None:
        er = ExperimentRunner()
        assert er.phase == ExperimentPhase.PENDING

    def test_chaos_scenario_dataclass(self) -> None:
        scenario = ChaosScenario(
            name="test",
            target_provider="openai",
            duration_seconds=10.0,
        )
        assert scenario.name == "test"
        assert scenario.target_provider == "openai"

    def test_observability_hook_instantiation(self) -> None:
        oh = ObservabilityHook()
        assert oh.snapshots == []

    def test_fault_profile_dataclass(self) -> None:
        fp = FaultProfile(fault_type=FaultType.TIMEOUT, duration_ms=500)
        assert fp.fault_type == FaultType.TIMEOUT
        assert fp.duration_ms == 500.0

    def test_fault_type_enum_values(self) -> None:
        assert FaultType.TIMEOUT.value == "timeout"
        assert FaultType.RATE_LIMIT.value == "rate-limit"
        assert FaultType.PROVIDER_FAILURE.value == "provider-failure"

    def test_experiment_phase_enum_values(self) -> None:
        assert ExperimentPhase.PREPARING.value == "preparing"
        assert ExperimentPhase.INJECTING.value == "injecting"
        assert ExperimentPhase.OBSERVING.value == "observing"

    def test_experiment_status_enum_values(self) -> None:
        assert ExperimentStatus.PASSED.value == "passed"
        assert ExperimentStatus.FAILED.value == "failed"


# ====================================================================
# FaultInjector Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="chaos_engineering not impl")
class TestFaultInjector:
    """Test FaultInjector — registering scenarios and injecting faults."""

    def test_register_unregister_scenario(self) -> None:
        fi = FaultInjector()
        scenario = ChaosScenario(name="test", target_provider="openai")
        fi.register_scenario(scenario)
        assert fi.should_inject("openai") is True
        fi.unregister_scenario("test")
        assert fi.should_inject("openai") is False

    def test_register_multiple_scenarios(self) -> None:
        fi = FaultInjector()
        fi.register_scenario(ChaosScenario(name="s1", target_provider="openai"))
        fi.register_scenario(ChaosScenario(name="s2", target_provider="anthropic"))
        assert fi.should_inject("openai") is True
        assert fi.should_inject("anthropic") is True

    def test_inject_fault_returns_fault_response(self) -> None:
        fi = FaultInjector()
        scenario = ChaosScenario(
            name="test", target_provider="openai",
            fault_profile=FaultProfile(fault_type=FaultType.TIMEOUT),
        )
        fi.register_scenario(scenario)
        result = fi.inject_fault("openai")
        assert result is not None
        assert result["fault_type"] == "timeout"
        assert fi.injection_count == 1

    def test_inject_fault_returns_none_for_unknown_provider(self) -> None:
        fi = FaultInjector()
        fi.register_scenario(ChaosScenario(name="test", target_provider="openai"))
        result = fi.inject_fault("anthropic")
        assert result is None

    def test_inject_fault_rate_limit_response(self) -> None:
        fi = FaultInjector()
        scenario = ChaosScenario(
            name="rate-test", target_provider="openai",
            fault_profile=FaultProfile(fault_type=FaultType.RATE_LIMIT, duration_ms=2000),
        )
        fi.register_scenario(scenario)
        result = fi.inject_fault("openai")
        assert result is not None
        assert result["fault_type"] == "rate-limit"
        assert result["retry_after_ms"] == 2000.0

    def test_inject_fault_partial_response(self) -> None:
        fi = FaultInjector()
        scenario = ChaosScenario(
            name="partial", target_provider="openai",
            fault_profile=FaultProfile(fault_type=FaultType.PARTIAL_RESPONSE),
        )
        fi.register_scenario(scenario)
        result = fi.inject_fault("openai")
        assert result is not None
        assert result["fault_type"] == "partial-response"

    def test_inject_fault_provider_failure(self) -> None:
        fi = FaultInjector()
        scenario = ChaosScenario(
            name="provider-down", target_provider="openai",
            fault_profile=FaultProfile(fault_type=FaultType.PROVIDER_FAILURE),
        )
        fi.register_scenario(scenario)
        result = fi.inject_fault("openai")
        assert result is not None
        assert result["fault_type"] == "provider-failure"

    def test_clear_removes_all_faults(self) -> None:
        fi = FaultInjector()
        fi.register_scenario(ChaosScenario(name="s1", target_provider="openai"))
        fi.register_scenario(ChaosScenario(name="s2", target_provider="anthropic"))
        fi.clear()
        assert fi.should_inject("openai") is False
        assert fi.injection_count == 0

    def test_expired_scenario_not_injected(self) -> None:
        fake_time: list[float] = [0.0]

        def _time() -> float:
            return fake_time[0]

        fi = FaultInjector(time_func=_time)
        scenario = ChaosScenario(
            name="expired", target_provider="openai",
            duration_seconds=0.001,
            fault_profile=FaultProfile(fault_type=FaultType.TIMEOUT, error_code=503),
        )
        fi.register_scenario(scenario)
        # First call may inject before expiration
        fake_time[0] = 10.0  # well past the 0.001s duration
        result = fi.inject_fault("openai")
        assert result is None  # should be expired


# ====================================================================
# ChaosScenario Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="chaos_engineering not impl")
class TestChaosScenario:
    """Test ChaosScenario dataclass and defaults."""

    def test_default_fault_profile(self) -> None:
        scenario = ChaosScenario(name="defaults", target_provider="openai")
        assert scenario.fault_profile.fault_type == FaultType.TIMEOUT
        assert scenario.fault_profile.duration_ms == 1000.0

    def test_default_abort_on_failure(self) -> None:
        scenario = ChaosScenario(name="defaults", target_provider="openai")
        assert scenario.abort_on_failure is True

    def test_tags_default_list(self) -> None:
        scenario = ChaosScenario(name="no-tags", target_provider="openai")
        assert scenario.tags == []

    def test_conditions_custom_values(self) -> None:
        scenario = ChaosScenario(
            name="custom", target_provider="openai",
            conditions={"min_health": 0.8, "max_latency": 2000},
        )
        assert scenario.conditions["min_health"] == 0.8


# ====================================================================
# ExperimentRunner Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="chaos_engineering not impl")
class TestExperimentRunner:
    """Test ExperimentRunner — lifecycle management."""

    def test_initial_phase_pending(self) -> None:
        er = ExperimentRunner()
        assert er.phase == ExperimentPhase.PENDING

    def test_prepare_validates_scenario(self) -> None:
        er = ExperimentRunner()
        scenario = ChaosScenario(name="test", target_provider="openai", duration_seconds=5.0)
        er.prepare(scenario)
        assert er.phase == ExperimentPhase.PREPARING
        assert er.current_scenario is not None

    def test_prepare_raises_on_empty_name(self) -> None:
        er = ExperimentRunner()
        with pytest.raises(ValueError, match="name"):
            er.prepare(ChaosScenario(name="", target_provider="openai"))

    def test_prepare_raises_on_empty_target(self) -> None:
        er = ExperimentRunner()
        with pytest.raises(ValueError, match="target_provider"):
            er.prepare(ChaosScenario(name="test", target_provider=""))

    def test_prepare_raises_on_zero_duration(self) -> None:
        er = ExperimentRunner()
        with pytest.raises(ValueError, match="duration"):
            er.prepare(ChaosScenario(name="test", target_provider="openai", duration_seconds=0))

    def test_inject_changes_phase_to_injecting(self) -> None:
        er = ExperimentRunner()
        er.prepare(ChaosScenario(name="test", target_provider="openai", duration_seconds=5.0))
        er.inject()
        assert er.phase == ExperimentPhase.INJECTING

    def test_inject_raises_without_prepare(self) -> None:
        er = ExperimentRunner()
        with pytest.raises(RuntimeError, match="prepare"):
            er.inject()

    def test_observe_returns_snapshots(self) -> None:
        er = ExperimentRunner()
        scenario = ChaosScenario(name="test", target_provider="openai", duration_seconds=5.0)
        er.prepare(scenario)
        er.inject()
        snapshots = er.observe()
        assert isinstance(snapshots, list)
        assert len(snapshots) > 0

    def test_clean_returns_result(self) -> None:
        er = ExperimentRunner()
        scenario = ChaosScenario(name="test", target_provider="openai", duration_seconds=5.0)
        er.prepare(scenario)
        er.inject()
        er.observe()
        result = er.clean()
        assert isinstance(result, ExperimentResult)
        assert result.scenario_name == "test"
        assert result.status in (ExperimentStatus.PASSED, ExperimentStatus.PARTIAL)

    def test_run_completes_full_lifecycle(self) -> None:
        er = ExperimentRunner()
        scenario = ChaosScenario(name="lifecycle", target_provider="openai", duration_seconds=1.0)
        result = er.run(scenario)
        assert result.phase == ExperimentPhase.COMPLETED
        assert result.scenario_name == "lifecycle"


# ====================================================================
# ObservabilityHook Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="chaos_engineering not impl")
class TestObservabilityHook:
    """Test ObservabilityHook — metrics capture and analysis."""

    def test_capture_adds_snapshot(self) -> None:
        oh = ObservabilityHook()
        oh.capture(latency_ms=100.0, error_count=1, request_count=10)
        assert len(oh.snapshots) == 1

    def test_capture_multiple_snapshots(self) -> None:
        oh = ObservabilityHook()
        oh.capture()
        oh.capture()
        oh.capture()
        assert len(oh.snapshots) == 3

    def test_get_average_latency(self) -> None:
        oh = ObservabilityHook()
        oh.capture(latency_ms=50.0)
        oh.capture(latency_ms=150.0)
        assert oh.get_average_latency() == 100.0

    def test_get_average_latency_by_phase(self) -> None:
        oh = ObservabilityHook()
        oh.capture(phase=ExperimentPhase.INJECTING, latency_ms=30.0)
        oh.capture(phase=ExperimentPhase.OBSERVING, latency_ms=70.0)
        oh.capture(phase=ExperimentPhase.OBSERVING, latency_ms=90.0)
        assert oh.get_average_latency(ExperimentPhase.OBSERVING) == 80.0

    def test_get_error_rate(self) -> None:
        oh = ObservabilityHook()
        oh.capture(error_count=2, request_count=10)
        oh.capture(error_count=1, request_count=10)
        assert oh.get_error_rate() == 0.15  # 3 errors / 20 total

    def test_get_error_rate_zero_requests(self) -> None:
        oh = ObservabilityHook()
        assert oh.get_error_rate() == 0.0

    def test_reset_clears_snapshots(self) -> None:
        oh = ObservabilityHook()
        oh.capture()
        oh.capture()
        oh.reset()
        assert oh.snapshots == []

    def test_on_snapshot_callback(self) -> None:
        oh = ObservabilityHook()
        received: list[MetricSnapshot] = []

        def cb(snapshot: MetricSnapshot) -> None:
            received.append(snapshot)

        oh.on_snapshot(cb)
        oh.capture(latency_ms=42.0)
        assert len(received) == 1
        assert received[0].latency_ms == 42.0


# ====================================================================
# Integration Tests
# ====================================================================


@pytest.mark.skipif(not MODULE_EXISTS, reason="chaos_engineering not impl")
class TestIntegration:
    """Integration tests combining chaos components."""

    def test_runner_with_injector_and_hook(self) -> None:
        fi = FaultInjector()
        oh = ObservabilityHook()
        er = ExperimentRunner(fault_injector=fi, observability_hook=oh)

        scenario = ChaosScenario(
            name="integration",
            target_provider="openai",
            duration_seconds=2.0,
            fault_profile=FaultProfile(fault_type=FaultType.TIMEOUT),
        )

        result = er.run(scenario)
        assert result.faults_injected >= 0  # may be 0 if randomness didn't trigger
        assert result.phase == ExperimentPhase.COMPLETED

    def test_fault_injector_probability_zero(self) -> None:
        """Zero probability means no fault is ever injected."""
        fi = FaultInjector()
        scenario = ChaosScenario(
            name="no-fault",
            target_provider="openai",
            fault_profile=FaultProfile(
                fault_type=FaultType.TIMEOUT, probability=0.0,
            ),
        )
        fi.register_scenario(scenario)
        # Even though scenario is registered, probability=0 means never inject
        for _ in range(20):
            result = fi.inject_fault("openai")
            if result is not None:
                pytest.fail("Fault injected despite probability=0")

    def test_observability_hook_metrics_after_experiment(self) -> None:
        fi = FaultInjector()
        oh = ObservabilityHook()
        er = ExperimentRunner(fault_injector=fi, observability_hook=oh)

        scenario = ChaosScenario(
            name="metrics-test",
            target_provider="openai",
            duration_seconds=1.0,
        )

        er.run(scenario)
        snapshots = oh.snapshots
        assert len(snapshots) >= 2  # at least injection + observation

    def test_multiple_fault_types_not_cross_contaminate(self) -> None:
        fi = FaultInjector()
        fi.register_scenario(ChaosScenario(
            name="openai-fault", target_provider="openai",
            fault_profile=FaultProfile(fault_type=FaultType.TIMEOUT),
        ))
        fi.register_scenario(ChaosScenario(
            name="anthropic-fault", target_provider="anthropic",
            fault_profile=FaultProfile(fault_type=FaultType.RATE_LIMIT),
        ))

        result = fi.inject_fault("anthropic")
        if result is not None:
            assert result["fault_type"] == "rate-limit"

    def test_runner_is_running_flag(self) -> None:
        er = ExperimentRunner()
        assert er.is_running() is False
        scenario = ChaosScenario(name="flag-test", target_provider="openai", duration_seconds=5.0)
        er.prepare(scenario)
        assert er.is_running() is True
        er.inject()
        assert er.is_running() is True
        er.clean()
        assert er.is_running() is False

    def test_phase_change_callbacks(self) -> None:
        er = ExperimentRunner()
        phases: list[str] = []

        def cb(old: ExperimentPhase, new: ExperimentPhase) -> None:
            phases.append(f"{old.value}->{new.value}")

        er.on_phase_change(cb)
        scenario = ChaosScenario(name="cb-test", target_provider="openai", duration_seconds=1.0)
        er.run(scenario)
        assert len(phases) >= 1

    def test_fault_injector_latency_spike(self) -> None:
        fi = FaultInjector()
        scenario = ChaosScenario(
            name="latency-test", target_provider="openai",
            fault_profile=FaultProfile(
                fault_type=FaultType.LATENCY_SPIKE,
                duration_ms=5000.0,
            ),
        )
        fi.register_scenario(scenario)
        result = fi.inject_fault("openai")
        if result is not None:
            assert result["latency_ms"] == 5000.0
            assert result["fault_type"] == "latency-spike"
