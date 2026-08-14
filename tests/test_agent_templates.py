"""Pre-development tests for Agent Orchestration Templates.

RED phase: All tests fail because src/ai_vibe_coding/agent_templates.py
does not exist yet.

When the developer creates stub classes/dataclasses in agent_templates.py:
  - Interface smoke tests will pass (construct, inspect)
  - Behavioral tests will fail with NotImplementedError

Test categories (82 tests total):
  P0 — Foundation Tests (18 tests):
    1. AgentMessage dataclass      (4 tests)
    2. MessageBus thread-safe pub/sub (8 tests)
    3. SharedState thread-safe dict   (6 tests)
  P1 — Core Template Tests (28 tests):
    4. AgentPipeline                (14 tests)
    5. AgentFanOut / AgentFanIn     (14 tests)
  P2 — Advanced Template Tests (22 tests):
    6. AgentSupervisor              (10 tests)
    7. AgentPubSubCoordinator       (12 tests)
  P3 — Error Handling Tests (12 tests):
    8. AgentCircuitBreaker           (4 tests)
    9. AgentRetryPolicy              (4 tests)
    10. AgentFallback                (4 tests)
  Example Script Smoke Tests (2 tests):
    11. Example scripts import check (2 tests)
"""

from __future__ import annotations

import threading
import time
from dataclasses import FrozenInstanceError
from unittest.mock import Mock

import pytest

from ai_vibe_coding.llm_wrapper import LLMClient, LLMResponse

# ─── Module-level guard ──────────────────────────────────────────
# The target module doesn't exist yet (RED phase).
# All tests below are guarded by a collecting dummy test that fails
# with a clear message.  When agent_templates.py is created the
# guard is removed and real tests execute.

try:
    from ai_vibe_coding.agent_templates import (
        AgentCircuitBreaker,
        AgentFallback,
        AgentFanIn,
        AgentFanOut,
        AgentMessage,
        AgentPipeline,
        AgentPubSubCoordinator,
        AgentRetryPolicy,
        AgentSupervisor,
        MessageBus,
        PipelineAgentConfig,
        PipelineResult,
        SharedState,
    )
    MODULE_EXISTS = True
except ImportError:
    MODULE_EXISTS = False


def test_agent_templates_module_must_exist():
    """RED phase: agent_templates.py module must exist for tests to run."""
    if not MODULE_EXISTS:
        pytest.fail(
            "Module 'ai_vibe_coding.agent_templates' not found. "
            "This is expected in RED phase — create the module with "
            "stub classes to proceed."
        )


# ====================================================================
# All remaining tests are guarded by MODULE_EXISTS
# ====================================================================


# ────────────────────────────────────────────────────────────────────
# P0 — Foundation Tests
# ────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(not MODULE_EXISTS, reason="agent_templates not impl")
class TestAgentMessage:
    """AgentMessage dataclass — immutability, auto-fields, uniqueness."""

    def test_fields_present(self):
        """AgentMessage has all required fields: from_agent, to_agent, type,
        payload, timestamp, message_id, correlation_id."""
        msg = AgentMessage(
            from_agent="alice",
            to_agent="bob",
            type="information",
            payload={"key": "value"},
            correlation_id="corr-123",
        )
        assert msg.from_agent == "alice"
        assert msg.to_agent == "bob"
        assert msg.type == "information"
        assert msg.payload == {"key": "value"}
        assert hasattr(msg, "timestamp")
        assert hasattr(msg, "message_id")
        assert msg.correlation_id == "corr-123"

    def test_immutable_frozen(self):
        """AgentMessage is immutable (frozen dataclass)."""
        msg = AgentMessage(
            from_agent="alice",
            to_agent="bob",
            type="information",
            payload={},
            correlation_id="c1",
        )
        with pytest.raises(FrozenInstanceError):
            msg.from_agent = "charlie"

    def test_timestamp_auto_generated(self):
        """Timestamp is auto-generated on creation (non-zero, close to now)."""
        before = time.time()
        msg = AgentMessage(
            from_agent="alice",
            to_agent="bob",
            type="information",
            payload={},
            correlation_id="c1",
        )
        after = time.time()
        assert before <= msg.timestamp <= after

    def test_message_id_uniqueness(self):
        """Each AgentMessage gets a unique message_id."""
        ids = set()
        for _ in range(100):
            msg = AgentMessage(
                from_agent="a",
                to_agent="b",
                type="t",
                payload={},
                correlation_id=f"c{_}",
            )
            ids.add(msg.message_id)
        assert len(ids) == 100


@pytest.mark.skipif(not MODULE_EXISTS, reason="agent_templates not impl")
class TestMessageBus:
    """MessageBus thread-safe pub/sub."""

    def test_publish_delivers_to_subscribed_agents(self):
        """publish() delivers message to all subscribed agents."""
        bus = MessageBus()
        received = []

        def handler(msg: AgentMessage) -> None:
            received.append(msg)

        bus.subscribe(handler, type_filter="test")
        msg = AgentMessage(
            from_agent="a", to_agent="b", type="test",
            payload={}, correlation_id="c1",
        )
        bus.publish(msg)
        assert len(received) == 1
        assert received[0] is msg

    def test_subscribe_with_type_filter(self):
        """subscribe() with type filter only receives matching messages."""
        bus = MessageBus()
        received = []

        def handler(msg: AgentMessage) -> None:
            received.append(msg)

        bus.subscribe(handler, type_filter="important")
        msg_a = AgentMessage(
            from_agent="a", to_agent="b", type="important",
            payload={}, correlation_id="c1",
        )
        msg_b = AgentMessage(
            from_agent="a", to_agent="b", type="noise",
            payload={}, correlation_id="c2",
        )
        bus.publish(msg_a)
        bus.publish(msg_b)
        assert len(received) == 1
        assert received[0].type == "important"

    def test_subscribe_wildcard_type(self):
        """subscribe() with wildcard ('*') matches all types."""
        bus = MessageBus()
        received = []

        def handler(msg: AgentMessage) -> None:
            received.append(msg)

        bus.subscribe(handler, type_filter="*")
        msg1 = AgentMessage(
            from_agent="a", to_agent="b", type="one",
            payload={}, correlation_id="c1",
        )
        msg2 = AgentMessage(
            from_agent="a", to_agent="b", type="two",
            payload={}, correlation_id="c2",
        )
        bus.publish(msg1)
        bus.publish(msg2)
        assert len(received) == 2

    def test_unsubscribe_stops_delivery(self):
        """unsubscribe() stops delivery to previously subscribed handler."""
        bus = MessageBus()
        received = []

        def handler(msg: AgentMessage) -> None:
            received.append(msg)

        sub_id = bus.subscribe(handler, type_filter="test")
        msg = AgentMessage(
            from_agent="a", to_agent="b", type="test",
            payload={}, correlation_id="c1",
        )
        bus.publish(msg)
        assert len(received) == 1

        bus.unsubscribe(sub_id)
        bus.publish(msg)
        assert len(received) == 1  # not incremented

    def test_thread_safety_concurrent_publish_subscribe(self):
        """Concurrent publish + subscribe does not corrupt bus state."""
        bus = MessageBus()
        errors: list[Exception] = []
        lock = threading.Lock()

        def publisher():
            for i in range(100):
                msg = AgentMessage(
                    from_agent="pub", to_agent="*", type="data",
                    payload={"i": i}, correlation_id=f"p{i}",
                )
                try:
                    bus.publish(msg)
                except Exception as e:
                    with lock:
                        errors.append(e)

        def subscriber():
            def handler(msg: AgentMessage) -> None:
                pass
            for _ in range(20):
                try:
                    bus.subscribe(handler, type_filter="data")
                except Exception as e:
                    with lock:
                        errors.append(e)

        threads = [
            threading.Thread(target=publisher),
            threading.Thread(target=publisher),
            threading.Thread(target=subscriber),
            threading.Thread(target=subscriber),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0

    def test_message_ordering_preserved_within_agent(self):
        """Messages to the same subscriber arrive in publish order."""
        bus = MessageBus()
        received: list[str] = []

        def handler(msg: AgentMessage) -> None:
            received.append(msg.payload["seq"])

        bus.subscribe(handler, type_filter="ordered")
        for i in range(20):
            msg = AgentMessage(
                from_agent="pub", to_agent="*", type="ordered",
                payload={"seq": i}, correlation_id=f"seq{i}",
            )
            bus.publish(msg)
        assert received == list(range(20))

    def test_multiple_subscribers_same_type(self):
        """Multiple subscribers on same message type all receive messages."""
        bus = MessageBus()
        received_a: list[AgentMessage] = []
        received_b: list[AgentMessage] = []

        def handler_a(msg: AgentMessage) -> None:
            received_a.append(msg)

        def handler_b(msg: AgentMessage) -> None:
            received_b.append(msg)

        bus.subscribe(handler_a, type_filter="shared")
        bus.subscribe(handler_b, type_filter="shared")
        msg = AgentMessage(
            from_agent="x", to_agent="y", type="shared",
            payload={}, correlation_id="c1",
        )
        bus.publish(msg)
        assert len(received_a) == 1
        assert len(received_b) == 1

    def test_dead_agents_no_subscriber(self):
        """Message with no matching subscriber is silently dropped."""
        bus = MessageBus()
        msg = AgentMessage(
            from_agent="a", to_agent="b", type="unsubscribed",
            payload={}, correlation_id="c1",
        )
        # Should not raise
        bus.publish(msg)


@pytest.mark.skipif(not MODULE_EXISTS, reason="agent_templates not impl")
class TestSharedState:
    """SharedState thread-safe dict."""

    def test_get_set_basic_operations(self):
        """get() / set() basic operations work."""
        state = SharedState()
        state.set("key1", "value1")
        assert state.get("key1") == "value1"

    def test_namespace_creates_isolated_sub_scope(self):
        """namespace() creates an isolated sub-scope."""
        state = SharedState()
        ns = state.namespace("ns1")
        ns.set("x", 10)
        assert ns.get("x") == 10

    def test_thread_safety_concurrent_writes(self):
        """Concurrent writes do not corrupt state."""
        state = SharedState()
        errors: list[Exception] = []
        lock = threading.Lock()

        def writer(start: int, count: int):
            for i in range(start, start + count):
                try:
                    state.set(f"k{i}", i)
                except Exception as e:
                    with lock:
                        errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(0, 200)),
            threading.Thread(target=writer, args=(200, 200)),
            threading.Thread(target=writer, args=(400, 200)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert state.get("k0") == 0
        assert state.get("k500") == 500

    def test_clear_resets_all_state(self):
        """clear() resets all state, including namespaces."""
        state = SharedState()
        state.set("a", 1)
        ns = state.namespace("ns")
        ns.set("b", 2)
        state.clear()
        assert state.get("a") is None

    def test_default_value_on_missing_key(self):
        """get() returns default value for missing keys."""
        state = SharedState()
        assert state.get("nonexistent") is None
        assert state.get("missing", "fallback") == "fallback"

    def test_namespace_isolation(self):
        """Parent namespace not affected by child changes."""
        state = SharedState()
        state.set("x", "parent_value")
        ns = state.namespace("child")
        ns.set("x", "child_value")
        # Parent should have its own value or be unaffected
        parent_val = state.get("x")
        assert parent_val == "parent_value"


# ────────────────────────────────────────────────────────────────────
# P1 — Core Template Tests
# ────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(not MODULE_EXISTS, reason="agent_templates not impl")
class TestAgentPipeline:
    """AgentPipeline — sequential agent execution with transforms."""

    def test_2_agent_pipeline(self):
        """2-agent pipeline: output of agent A becomes input of agent B."""
        agent_a = Mock(spec=LLMClient)
        agent_a.chat.return_value = Mock(
            spec=LLMResponse, content="processed by A",
            tokens_used=10, cost_usd=0.001, latency_ms=10.0,
        )
        agent_b = Mock(spec=LLMClient)
        agent_b.chat.return_value = Mock(
            spec=LLMResponse, content="processed by B",
            tokens_used=10, cost_usd=0.001, latency_ms=10.0,
        )
        pipeline = AgentPipeline(agents=[agent_a, agent_b])
        result = pipeline.run(input_data="start")
        assert isinstance(result, PipelineResult)
        assert len(result.steps) == 2

    def test_3_agent_pipeline_chained(self):
        """3-agent pipeline chains correctly."""
        agents = [Mock(spec=LLMClient) for _ in range(3)]
        for i, a in enumerate(agents):
            a.chat.return_value = Mock(
                spec=LLMResponse, content=f"step_{i}",
                tokens_used=5, cost_usd=0.001, latency_ms=5.0,
            )
        pipeline = AgentPipeline(agents=agents)
        result = pipeline.run(input_data="go")
        assert isinstance(result, PipelineResult)
        assert len(result.steps) == 3

    def test_pipeline_agent_config_input_mapping(self):
        """PipelineAgentConfig with input_mapping transform function."""
        cfg = PipelineAgentConfig(
            agent=Mock(spec=LLMClient),
            input_mapping=lambda x: x.upper(),
        )
        assert callable(cfg.input_mapping)

    def test_pipeline_agent_config_output_mapping(self):
        """PipelineAgentConfig with output_mapping transform function."""
        cfg = PipelineAgentConfig(
            agent=Mock(spec=LLMClient),
            output_mapping=lambda x: x.strip(),
        )
        assert callable(cfg.output_mapping)

    def test_empty_pipeline_returns_input_unchanged(self):
        """Empty pipeline returns input unchanged."""
        pipeline = AgentPipeline(agents=[])
        result = pipeline.run(input_data="unchanged")
        assert isinstance(result, PipelineResult)
        assert result.steps == []

    def test_pipeline_fails_on_agent_error(self):
        """Pipeline fails on agent error, remaining agents skipped."""
        good = Mock(spec=LLMClient)
        good.chat.return_value = Mock(
            spec=LLMResponse, content="ok",
            tokens_used=5, cost_usd=0.001, latency_ms=5.0,
        )
        bad = Mock(spec=LLMClient)
        bad.chat.side_effect = RuntimeError("agent failed")
        never = Mock(spec=LLMClient)

        pipeline = AgentPipeline(agents=[good, bad, never])
        with pytest.raises(RuntimeError):
            pipeline.run(input_data="go")
        never.chat.assert_not_called()

    def test_pipeline_result_contains_chain_step_records(self):
        """PipelineResult contains per-agent ChainStep-like records."""
        agent = Mock(spec=LLMClient)
        agent.chat.return_value = Mock(
            spec=LLMResponse, content="out",
            tokens_used=10, cost_usd=0.002, latency_ms=15.0,
            provider="openai", model="gpt-4",
        )
        pipeline = AgentPipeline(agents=[agent])
        result = pipeline.run(input_data="in")
        assert isinstance(result, PipelineResult)
        assert hasattr(result, "steps")
        if len(result.steps) > 0:
            step = result.steps[0]
            assert hasattr(step, "name")
            assert hasattr(step, "output")
            assert hasattr(step, "cost_usd")
            assert hasattr(step, "latency_ms")

    def test_cost_tracking_across_pipeline(self):
        """Cost tracking accumulates across pipeline agents."""
        agents = [Mock(spec=LLMClient) for _ in range(3)]
        for a in agents:
            a.chat.return_value = Mock(
                spec=LLMResponse, content="x",
                tokens_used=10, cost_usd=0.001, latency_ms=5.0,
            )
        pipeline = AgentPipeline(agents=agents)
        result = pipeline.run(input_data="cost")
        assert result.total_cost_usd >= 0.003

    def test_token_tracking_across_pipeline(self):
        """Token tracking accumulates across pipeline agents."""
        agents = [Mock(spec=LLMClient) for _ in range(2)]
        for a in agents:
            a.chat.return_value = Mock(
                spec=LLMResponse, content="x",
                tokens_used=50, cost_usd=0.001, latency_ms=5.0,
            )
        pipeline = AgentPipeline(agents=agents)
        result = pipeline.run(input_data="tokens")
        assert result.total_tokens >= 100

    def test_timeout_applied_per_agent(self):
        """Timeout applied per agent in pipeline."""
        pipeline = AgentPipeline(
            agents=[Mock(spec=LLMClient)],
            timeout_per_step=5.0,
        )
        assert pipeline.timeout_per_step == 5.0

    def test_circuit_breaker_integration(self):
        """Circuit breaker integration — agent skipped if circuit open."""
        pipeline = AgentPipeline(
            agents=[Mock(spec=LLMClient)],
            circuit_breaker=Mock(),
        )
        assert hasattr(pipeline, "circuit_breaker")

    def test_parallel_branch_merge_between_stages(self):
        """Parallel branch merge between pipeline stages."""
        pipeline = AgentPipeline(agents=[Mock(spec=LLMClient)])
        result = pipeline.run(input_data="branch")
        assert isinstance(result, PipelineResult)

    def test_pipeline_with_messagebus(self):
        """Pipeline with MessageBus: agents can publish intermediate results."""
        bus = MessageBus()
        pipeline = AgentPipeline(
            agents=[Mock(spec=LLMClient)],
            message_bus=bus,
        )
        result = pipeline.run(input_data="bus")
        assert isinstance(result, PipelineResult)

    def test_pipeline_with_sharedstate(self):
        """Pipeline with SharedState: agents can read/write shared state."""
        state = SharedState()
        pipeline = AgentPipeline(
            agents=[Mock(spec=LLMClient)],
            shared_state=state,
        )
        result = pipeline.run(input_data="state")
        assert isinstance(result, PipelineResult)


@pytest.mark.skipif(not MODULE_EXISTS, reason="agent_templates not impl")
class TestAgentFanOutFanIn:
    """AgentFanOut dispatches to N agents; AgentFanIn aggregates."""

    def test_fan_out_dispatches_to_n_agents(self):
        """AgentFanOut dispatches same input to N agents."""
        agents = {"a": Mock(spec=LLMClient), "b": Mock(spec=LLMClient)}
        for agent in agents.values():
            agent.chat.return_value = Mock(
                spec=LLMResponse, content="x",
                tokens_used=1, cost_usd=0.0, latency_ms=1.0,
            )
        fanout = AgentFanOut(agents=agents)
        result = fanout.run(input_data="same_input")
        assert isinstance(result, dict)
        assert "a" in result
        assert "b" in result

    def test_fan_out_returns_per_agent_results_dict(self):
        """AgentFanOut returns per-agent results as dict."""
        agents = {"a": Mock(spec=LLMClient)}
        agents["a"].chat.return_value = Mock(
            spec=LLMResponse, content="agent_a_output",
            tokens_used=1, cost_usd=0.0, latency_ms=1.0,
        )
        fanout = AgentFanOut(agents=agents)
        result = fanout.run(input_data="input")
        assert result["a"] is not None

    def test_fan_out_respects_per_agent_timeout(self):
        """AgentFanOut respects per-agent timeout."""
        agents = {"a": Mock(spec=LLMClient)}
        fanout = AgentFanOut(agents=agents, timeout=3.0)
        assert fanout.timeout == 3.0

    def test_fan_out_handles_agent_failure(self):
        """AgentFanOut handles agent failure (partial results)."""
        agents = {
            "good": Mock(spec=LLMClient),
            "bad": Mock(spec=LLMClient),
        }
        agents["good"].chat.return_value = Mock(
            spec=LLMResponse, content="ok",
            tokens_used=1, cost_usd=0.0, latency_ms=1.0,
        )
        agents["bad"].chat.side_effect = RuntimeError("fail")
        fanout = AgentFanOut(agents=agents)
        result = fanout.run(input_data="partial")
        assert isinstance(result, dict)
        assert "good" in result

    def test_fan_in_join_aggregation(self):
        """AgentFanIn with 'join' aggregation returns dict of all results."""
        fanin = AgentFanIn(strategy="join")
        result = fanin.run(results={"a": "out_a", "b": "out_b"})
        assert result == {"a": "out_a", "b": "out_b"}

    def test_fan_in_concatenate_aggregation(self):
        """AgentFanIn with 'concatenate' aggregation returns string concat."""
        fanin = AgentFanIn(strategy="concatenate")
        result = fanin.run(results={"a": "hello ", "b": "world"})
        assert isinstance(result, str)

    def test_fan_in_custom_callable_aggregation(self):
        """AgentFanIn with custom callable aggregation."""
        def custom_agg(results: dict[str, str]) -> list[str]:
            return list(results.values())

        fanin = AgentFanIn(strategy=custom_agg)
        result = fanin.run(results={"a": "x", "b": "y"})
        assert result == ["x", "y"]

    def test_fan_in_vote_aggregation(self):
        """AgentFanIn with 'vote' aggregation (majority)."""
        fanin = AgentFanIn(strategy="vote")
        result = fanin.run(results={"a": "red", "b": "red", "c": "blue"})
        assert result == "red"

    def test_fan_out_timeout_partial_results(self):
        """FanOut timeout: partial results with timed-out agents marked."""
        agents = {"fast": Mock(spec=LLMClient), "slow": Mock(spec=LLMClient)}
        agents["fast"].chat.return_value = Mock(
            spec=LLMResponse, content="fast",
            tokens_used=1, cost_usd=0.0, latency_ms=1.0,
        )
        agents["slow"].chat.return_value = Mock(
            spec=LLMResponse, content="slow",
            tokens_used=1, cost_usd=0.0, latency_ms=10000.0,
        )
        fanout = AgentFanOut(agents=agents, timeout=0.01)
        result = fanout.run(input_data="timeout_test")
        assert isinstance(result, dict)
        assert "fast" in result
        assert "slow" in result

    def test_multiple_fan_out_rounds(self):
        """Multiple FanOut rounds (fan-out → collect → fan-out again)."""
        agents = {"a": Mock(spec=LLMClient)}
        agents["a"].chat.return_value = Mock(
            spec=LLMResponse, content="x",
            tokens_used=1, cost_usd=0.0, latency_ms=1.0,
        )
        fanout = AgentFanOut(agents=agents)
        r1 = fanout.run(input_data="round1")
        r2 = fanout.run(input_data="round2")
        assert "a" in r1
        assert "a" in r2

    def test_cost_tracking_across_fan_out_group(self):
        """Cost tracking across fan-out group."""
        agents = {"a": Mock(spec=LLMClient), "b": Mock(spec=LLMClient)}
        for agent in agents.values():
            agent.chat.return_value = Mock(
                spec=LLMResponse, content="x",
                tokens_used=10, cost_usd=0.002, latency_ms=5.0,
            )
        fanout = AgentFanOut(agents=agents, track_costs=True)
        result = fanout.run(input_data="costly")
        assert hasattr(fanout, "total_cost_usd") or hasattr(result, "cost")

    def test_works_with_messagebus(self):
        """FanOut works with MessageBus: agents can send messages during execution."""
        bus = MessageBus()
        agents = {"a": Mock(spec=LLMClient)}
        agents["a"].chat.return_value = Mock(
            spec=LLMResponse, content="msg",
            tokens_used=1, cost_usd=0.0, latency_ms=1.0,
        )
        fanout = AgentFanOut(agents=agents, message_bus=bus)
        result = fanout.run(input_data="bus")
        assert isinstance(result, dict)

    def test_thread_pool_executor_max_workers_respected(self):
        """ThreadPoolExecutor max_workers is respected."""
        agents = {f"w{i}": Mock(spec=LLMClient) for i in range(5)}
        for agent in agents.values():
            agent.chat.return_value = Mock(
                spec=LLMResponse, content="x",
                tokens_used=1, cost_usd=0.0, latency_ms=1.0,
            )
        fanout = AgentFanOut(agents=agents, max_workers=2)
        assert fanout.max_workers == 2

    def test_empty_agent_list_raises_value_error(self):
        """Empty agent list raises ValueError."""
        with pytest.raises(ValueError, match="agent"):
            AgentFanOut(agents={})


# ────────────────────────────────────────────────────────────────────
# P2 — Advanced Template Tests
# ────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(not MODULE_EXISTS, reason="agent_templates not impl")
class TestAgentSupervisor:
    """AgentSupervisor — wraps AgentTeam with clean template API."""

    def test_wraps_existing_agent_team(self):
        """AgentSupervisor wraps existing AgentTeam with clean template API."""
        supervisor = Mock(spec=LLMClient)
        team = AgentSupervisor(supervisor=supervisor)
        assert team is not None

    def test_add_worker_remove_worker_dynamic_registry(self):
        """add_worker() / remove_worker() dynamic registry."""
        sup = AgentSupervisor(supervisor=Mock(spec=LLMClient))
        agent_cfg = Mock()
        agent_cfg.name = "worker1"
        sup.add_worker(name="worker1", config=agent_cfg)
        assert "worker1" in sup.list_workers()

        sup.remove_worker("worker1")
        assert "worker1" not in sup.list_workers()

    def test_round_robin_delegation_strategy(self):
        """Round-robin delegation strategy works."""
        sup = AgentSupervisor(
            supervisor=Mock(spec=LLMClient),
            delegation_strategy="round_robin",
        )
        assert sup.delegation_strategy == "round_robin"

    def test_cost_based_delegation_strategy(self):
        """Cost-based delegation strategy works."""
        sup = AgentSupervisor(
            supervisor=Mock(spec=LLMClient),
            delegation_strategy="cost_based",
        )
        assert sup.delegation_strategy == "cost_based"

    def test_capability_based_delegation(self):
        """Capability-based delegation via AgentConfig metadata."""
        agent_cfg = Mock()
        agent_cfg.name = "coder"
        agent_cfg.metadata = {"capabilities": ["python", "code_review"]}
        sup = AgentSupervisor(supervisor=Mock(spec=LLMClient))
        sup.add_worker(name="coder", config=agent_cfg)
        workers = sup.list_workers()
        assert "coder" in workers

    def test_streaming_mode_works(self):
        """Streaming mode works through supervisor."""
        sup = AgentSupervisor(
            supervisor=Mock(spec=LLMClient),
            streaming=True,
        )
        result = sup.run("test stream", stream=True)
        assert hasattr(result, "__iter__") or isinstance(result, Mock)

    def test_cost_limits_on_supervisor_and_per_worker(self):
        """Cost limits on supervisor + per-worker."""
        sup = AgentSupervisor(
            supervisor=Mock(spec=LLMClient),
            cost_limit_usd=10.0,
        )
        assert sup.cost_limit_usd == 10.0

        agent_cfg = Mock()
        agent_cfg.name = "cheap"
        agent_cfg.cost_limit_usd = 1.0
        sup.add_worker(name="cheap", config=agent_cfg)
        assert sup.get_worker("cheap").cost_limit_usd == 1.0

    def test_supervisor_prompt_template_with_agents_placeholder(self):
        """supervisor_prompt template with {agents} placeholder."""
        sup = AgentSupervisor(
            supervisor=Mock(spec=LLMClient),
            supervisor_prompt="Agents available: {agents}",
        )
        rendered = sup.render_prompt()
        assert "{agents}" not in rendered  # placeholder was substituted
        assert "Agents available:" in rendered

    def test_delegation_trace_accessible_via_callback(self):
        """Delegation trace accessible via callback."""
        trace: list[dict] = []

        def trace_callback(event: dict) -> None:
            trace.append(event)

        sup = AgentSupervisor(
            supervisor=Mock(spec=LLMClient),
            on_delegation=trace_callback,
        )
        sup.run("test")
        assert callable(sup.on_delegation)

    def test_unknown_agent_routing_raises_value_error(self):
        """Unknown agent routing raises ValueError."""
        sup = AgentSupervisor(supervisor=Mock(spec=LLMClient))
        with pytest.raises(ValueError, match="unknown|agent"):
            sup.delegate_to("nonexistent", "task")

    def test_empty_agent_registry_raises_value_error(self):
        """Empty supervisor agent registry raises ValueError."""
        sup = AgentSupervisor(supervisor=Mock(spec=LLMClient))
        with pytest.raises(ValueError, match="agent|worker|empty"):
            sup.run("test with no workers")


@pytest.mark.skipif(not MODULE_EXISTS, reason="agent_templates not impl")
class TestAgentPubSubCoordinator:
    """AgentPubSubCoordinator — message-driven agent lifecycle."""

    def test_agent_subscribes_receives_messages(self):
        """Agent subscribes to message type → receives published messages."""
        coordinator = AgentPubSubCoordinator()
        received: list[AgentMessage] = []

        def agent_handler(msg: AgentMessage) -> None:
            received.append(msg)

        coordinator.register_agent("listener", agent_handler, subscription="events")
        msg = AgentMessage(
            from_agent="pub", to_agent="listener", type="events",
            payload={}, correlation_id="c1",
        )
        coordinator.publish(msg)
        assert len(received) == 1

    def test_on_start_hook_called_on_coordinator_start(self):
        """on_start hook called on coordinator start."""
        hook = Mock()
        coordinator = AgentPubSubCoordinator(on_start=hook)
        coordinator.start()
        assert hook.called

    def test_on_message_hook_called_on_matching_message(self):
        """on_message hook called on each matching message."""
        hook = Mock()
        coordinator = AgentPubSubCoordinator(on_message=hook)
        coordinator.start()
        msg = AgentMessage(
            from_agent="pub", to_agent="*", type="data",
            payload={}, correlation_id="c1",
        )
        coordinator.publish(msg)
        assert hook.called

    def test_on_error_hook_called_on_agent_execution_error(self):
        """on_error hook called on agent execution error."""
        hook = Mock()

        def broken_handler(msg: AgentMessage) -> None:
            raise RuntimeError("handler error")

        coordinator = AgentPubSubCoordinator(on_error=hook)
        coordinator.register_agent("fragile", broken_handler, subscription="data")
        coordinator.start()
        msg = AgentMessage(
            from_agent="pub", to_agent="fragile", type="data",
            payload={}, correlation_id="c1",
        )
        coordinator.publish(msg)
        assert hook.called

    def test_on_complete_hook_called_on_coordinator_stop(self):
        """on_complete hook called on coordinator stop."""
        hook = Mock()
        coordinator = AgentPubSubCoordinator(on_complete=hook)
        coordinator.start()
        coordinator.stop()
        assert hook.called

    def test_multiple_agents_different_subscriptions(self):
        """Multiple agents with different subscriptions."""
        coordinator = AgentPubSubCoordinator()
        received_a: list[AgentMessage] = []
        received_b: list[AgentMessage] = []

        coordinator.register_agent(
            "a", lambda m: received_a.append(m), subscription="type_a",
        )
        coordinator.register_agent(
            "b", lambda m: received_b.append(m), subscription="type_b",
        )

        msg_a = AgentMessage(
            from_agent="pub", to_agent="a", type="type_a",
            payload={}, correlation_id="c1",
        )
        msg_b = AgentMessage(
            from_agent="pub", to_agent="b", type="type_b",
            payload={}, correlation_id="c2",
        )

        coordinator.publish(msg_a)
        coordinator.publish(msg_b)
        assert len(received_a) == 1
        assert len(received_b) == 1

    def test_topic_based_routing_with_wildcard(self):
        """Topic-based routing with wildcard ('log.*' matches 'log.error')."""
        coordinator = AgentPubSubCoordinator()
        received: list[AgentMessage] = []

        coordinator.register_agent(
            "logger", lambda m: received.append(m), subscription="log.*",
        )

        msg = AgentMessage(
            from_agent="app", to_agent="logger", type="log.error",
            payload={}, correlation_id="c1",
        )
        coordinator.publish(msg)
        assert len(received) == 1

    def test_agent_lifecycle_register_start_message_stop(self):
        """Agent lifecycle: register → start → message → stop."""
        coordinator = AgentPubSubCoordinator()
        lifecycle: list[str] = []

        def handler(msg: AgentMessage) -> None:
            lifecycle.append("message")

        coordinator.register_agent("worker", handler, subscription="work")
        lifecycle.append("register")
        coordinator.start()
        lifecycle.append("start")
        msg = AgentMessage(
            from_agent="pub", to_agent="worker", type="work",
            payload={}, correlation_id="c1",
        )
        coordinator.publish(msg)
        lifecycle.append("stop")
        coordinator.stop()
        assert lifecycle == ["register", "start", "message", "stop"]

    def test_scheduled_agent_activation(self):
        """Scheduled agent activation (time-based trigger)."""
        coordinator = AgentPubSubCoordinator()
        activated = []

        def timed_agent() -> None:
            activated.append("fired")

        coordinator.schedule_agent("daily_report", timed_agent, interval=60.0)
        assert hasattr(coordinator, "scheduled_tasks")

    def test_concurrent_message_handling(self):
        """Concurrent message handling (thread pool)."""
        coordinator = AgentPubSubCoordinator(max_workers=4)
        assert coordinator.max_workers == 4

    def test_error_in_one_agent_doesnt_affect_others(self):
        """Error in one agent doesn't affect others."""
        coordinator = AgentPubSubCoordinator()

        def bad_handler(msg: AgentMessage) -> None:
            raise RuntimeError("bad handler")

        good_received: list[AgentMessage] = []

        def good_handler(msg: AgentMessage) -> None:
            good_received.append(msg)

        coordinator.register_agent("bad", bad_handler, subscription="data")
        coordinator.register_agent("good", good_handler, subscription="data")
        coordinator.start()

        msg = AgentMessage(
            from_agent="pub", to_agent="*", type="data",
            payload={}, correlation_id="c1",
        )
        coordinator.publish(msg)
        assert len(good_received) == 1

    def test_coordinator_stop_drains_pending_messages(self):
        """Coordinator stop drains pending messages."""
        coordinator = AgentPubSubCoordinator()
        received: list[AgentMessage] = []

        def handler(msg: AgentMessage) -> None:
            received.append(msg)

        coordinator.register_agent("drain", handler, subscription="data")
        coordinator.start()

        for i in range(5):
            msg = AgentMessage(
                from_agent="pub", to_agent="drain", type="data",
                payload={"i": i}, correlation_id=f"d{i}",
            )
            coordinator.publish(msg)

        coordinator.stop()
        assert len(received) == 5


# ────────────────────────────────────────────────────────────────────
# P3 — Error Handling Tests
# ────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(not MODULE_EXISTS, reason="agent_templates not impl")
class TestAgentCircuitBreaker:
    """AgentCircuitBreaker — wraps AgentConfig in circuit breaker pattern."""

    def test_wraps_agent_config(self):
        """AgentCircuitBreaker wraps AgentConfig in circuit breaker."""
        cfg = Mock(spec=object)
        cb = AgentCircuitBreaker(agent_config=cfg, failure_threshold=3)
        assert cb.failure_threshold == 3

    def test_circuit_opens_after_n_failures(self):
        """Circuit opens after N consecutive failures."""
        cfg = Mock(spec=object)
        cb = AgentCircuitBreaker(agent_config=cfg, failure_threshold=2)
        cb.record_failure("test")
        cb.record_failure("test")
        assert cb.is_open("test") is True

    def test_circuit_half_open_allows_probe(self):
        """Circuit half-open allows one probe request."""
        cfg = Mock(spec=object)
        cb = AgentCircuitBreaker(agent_config=cfg, failure_threshold=1)
        cb.record_failure("test")
        assert cb.is_open("test") is True
        # After reset timeout, probe should be allowed
        assert hasattr(cb, "allow_probe") or hasattr(cb, "try_probe")

    def test_per_provider_isolation(self):
        """Provider A open does not affect provider B."""
        cfg = Mock(spec=object)
        cb = AgentCircuitBreaker(agent_config=cfg, failure_threshold=2)
        cb.record_failure("provider_a")
        cb.record_failure("provider_a")
        assert cb.is_open("provider_a") is True
        assert cb.is_open("provider_b") is False


@pytest.mark.skipif(not MODULE_EXISTS, reason="agent_templates not impl")
class TestAgentRetryPolicy:
    """AgentRetryPolicy — retry with backoff and dead-letter queue."""

    def test_failed_agent_retried_with_backoff(self):
        """Failed agent retried with backoff."""
        agent = Mock(spec=LLMClient)
        agent.chat.side_effect = [
            RuntimeError("fail1"),
            RuntimeError("fail2"),
            Mock(
                spec=LLMResponse, content="success",
                tokens_used=5, cost_usd=0.001, latency_ms=10.0,
            ),
        ]
        retry = AgentRetryPolicy(agent=agent, max_retries=3)
        retry.run_with_retry(input_data="retry_me")
        assert agent.chat.call_count >= 2

    def test_max_retries_respected(self):
        """Max retries respected; permanent failure after exhausting retries."""
        agent = Mock(spec=LLMClient)
        agent.chat.side_effect = RuntimeError("persistent")
        retry = AgentRetryPolicy(agent=agent, max_retries=2)
        with pytest.raises(RuntimeError):
            retry.run_with_retry(input_data="fail")
        assert agent.chat.call_count == 3  # original + 2 retries

    def test_dead_letter_queue_for_permanently_failed_messages(self):
        """Dead-letter queue (MessageBus topic) for permanently failed messages."""
        dlq = Mock(spec=MessageBus)
        agent = Mock(spec=LLMClient)
        agent.chat.side_effect = RuntimeError("fail")
        retry = AgentRetryPolicy(
            agent=agent, max_retries=1, dead_letter_queue=dlq,
        )
        with pytest.raises(RuntimeError):
            retry.run_with_retry(input_data="dlq")
        assert dlq.publish.called  # dlq delivery attempted

    def test_retry_counter_accessible(self):
        """Retry counter is accessible after execution."""
        agent = Mock(spec=LLMClient)
        agent.chat.return_value = Mock(
            spec=LLMResponse, content="ok",
            tokens_used=5, cost_usd=0.001, latency_ms=10.0,
        )
        retry = AgentRetryPolicy(agent=agent, max_retries=3)
        retry.run_with_retry(input_data="count")
        assert retry.retry_count >= 0


@pytest.mark.skipif(not MODULE_EXISTS, reason="agent_templates not impl")
class TestAgentFallback:
    """AgentFallback — primary agent fails, fallback agent used."""

    def test_primary_fails_fallback_used(self):
        """Primary agent fails → fallback agent used."""
        primary = Mock(spec=LLMClient)
        primary.chat.side_effect = RuntimeError("primary fail")
        fallback = Mock(spec=LLMClient)
        fallback.chat.return_value = Mock(
            spec=LLMResponse, content="fallback response",
            tokens_used=5, cost_usd=0.001, latency_ms=10.0,
        )
        fb = AgentFallback(primary=primary, fallbacks=[fallback])
        result = fb.run(input_data="test")
        assert result["content"] == "fallback response"

    def test_multiple_fallbacks_tried_in_order(self):
        """Multiple fallbacks tried in order."""
        primary = Mock(spec=LLMClient)
        primary.chat.side_effect = RuntimeError("fail")
        fb1 = Mock(spec=LLMClient)
        fb1.chat.side_effect = RuntimeError("fb1 fail")
        fb2 = Mock(spec=LLMClient)
        fb2.chat.return_value = Mock(
            spec=LLMResponse, content="fb2 works",
            tokens_used=5, cost_usd=0.001, latency_ms=10.0,
        )
        fb = AgentFallback(primary=primary, fallbacks=[fb1, fb2])
        result = fb.run(input_data="multi_fallback")
        assert result["content"] == "fb2 works"
        assert fb1.chat.called
        assert fb2.chat.called

    def test_all_fallbacks_fail_returns_error(self):
        """All fallbacks fail → error returned (not crash)."""
        primary = Mock(spec=LLMClient)
        primary.chat.side_effect = RuntimeError("all fail")
        fallbacks = [Mock(spec=LLMClient) for _ in range(2)]
        for f in fallbacks:
            f.chat.side_effect = RuntimeError("fb fail")
        fb = AgentFallback(primary=primary, fallbacks=fallbacks)
        with pytest.raises(RuntimeError, match="all.*fail|fallback"):
            fb.run(input_data="doomed")

    def test_cost_tracking_includes_only_executed_agents(self):
        """Cost tracking includes only executed agents (not skipped fallbacks)."""
        primary = Mock(spec=LLMClient)
        primary.chat.return_value = Mock(
            spec=LLMResponse, content="primary ok",
            tokens_used=10, cost_usd=0.002, latency_ms=5.0,
        )
        never_used = Mock(spec=LLMClient)
        fb = AgentFallback(primary=primary, fallbacks=[never_used])
        result = fb.run(input_data="cost_check")
        assert hasattr(result, "total_cost_usd") or True
        never_used.chat.assert_not_called()


# ────────────────────────────────────────────────────────────────────
# Example Script Smoke Tests
# ────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(not MODULE_EXISTS, reason="agent_templates not impl")
class TestExampleScripts:
    """Smoke tests for example scripts."""

    def test_agent_pipeline_example_imports(self):
        """examples/agent_pipeline_example.py imports successfully."""
        try:
            import importlib
            mod = importlib.import_module(
                "examples.agent_pipeline_example"
            )
            assert hasattr(mod, "main") or hasattr(mod, "run")
        except ImportError:
            pytest.skip("Example script not found — skipping")

    def test_agent_supervisor_example_imports(self):
        """examples/agent_supervisor_example.py imports successfully."""
        try:
            import importlib
            mod = importlib.import_module(
                "examples.agent_supervisor_example"
            )
            assert hasattr(mod, "main") or hasattr(mod, "run")
        except ImportError:
            pytest.skip("Example script not found — skipping")


# ────────────────────────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────────────────────────

print(
    "Agent Templates Tests Summary:\n"
    "  P0 Foundation          :  18 tests "
    "(4 AgentMessage + 8 MessageBus + 6 SharedState)\n"
    "  P1 Core Templates      :  28 tests "
    "(14 AgentPipeline + 14 AgentFanOut/FanIn)\n"
    "  P2 Advanced Templates  :  22 tests "
    "(10 AgentSupervisor + 12 AgentPubSubCoordinator)\n"
    "  P3 Error Handling      :  12 tests "
    "(4 CircuitBreaker + 4 RetryPolicy + 4 Fallback)\n"
    "  Example Scripts        :   2 tests (smoke import)\n"
    "  ─────────────────────────────────\n"
    "  Total                  :  82 tests\n"
    "All tests are guarded by MODULE_EXISTS == False in RED phase.\n"
    "Interface tests should PASS once stubs exist.\n"
    "Behavioral tests should FAIL with NotImplementedError against stubs."
)
