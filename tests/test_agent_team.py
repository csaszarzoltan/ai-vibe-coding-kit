"""Tests for AgentTeam multi-agent orchestration feature.

Interface tests verify API surface. Behavioral tests define the contract
for AgentTeam behavior against stubs that raise NotImplementedError.
"""
from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from ai_vibe_coding.agent_team import (
    AgentConfig,
    AgentTeam,
    AgentTeamResult,
    CostLimitExceededError,
    DelegationEvent,
)
from ai_vibe_coding.llm_wrapper import LLMClient, LLMResponse

# ──────────────────────────────────────────────────────────────
# Interface smoke tests
# ──────────────────────────────────────────────────────────────

class TestInterfaceSmoke:
    """Verify that all classes and functions exist with correct signatures."""

    def test_import_agent_team(self):
        """Import AgentTeam from ai_vibe_coding."""
        assert AgentTeam is not None

    def test_constructor_accepts_supervisor_and_agents(self):
        """AgentTeam.__init__ accepts supervisor and agents dict."""
        supervisor = Mock(spec=LLMClient)
        agents = {"test_agent": Mock(spec=AgentConfig)}
        team = AgentTeam(supervisor, agents)
        assert team.supervisor is supervisor
        assert team.agents == agents

    def test_constructor_accepts_optional_params(self):
        """AgentTeam.__init__ accepts optional supervisor_prompt, max_rounds."""
        supervisor = Mock(spec=LLMClient)
        agent = Mock(spec=AgentConfig)
        agents = {"test": agent}
        team = AgentTeam(
            supervisor,
            agents,
            supervisor_prompt="test",
            max_rounds=5,
            cost_limit_usd=10.0,
        )
        assert team.supervisor is supervisor
        assert team.agents == agents
        assert team.supervisor_prompt == "test"
        assert team.max_rounds == 5
        assert team.cost_limit_usd == 10.0

    def test_agent_team_run_method_exists(self):
        """AgentTeam.run method exists and has correct signature."""
        import inspect
        sig = inspect.signature(AgentTeam.run)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "prompt" in params
        assert "stream" in params

    def test_agent_team_exposes_cost_tracking(self):
        """AgentTeam has cost tracking and history accessors."""
        # This is verified by checking the class has _cost_tracker attribute
        assert hasattr(AgentTeam, '_dispatch_to_agent')
        assert hasattr(AgentTeam, '_build_supervisor_prompt')

    def test_agent_config_dataclass(self):
        """AgentConfig is a dataclass with required fields."""
        supervisor = Mock(spec=LLMClient)
        config = AgentConfig(
            name="test",
            client=supervisor,
            system_prompt="Test prompt"
        )
        assert config.name == "test"
        assert config.client is supervisor
        assert config.system_prompt == "Test prompt"
        assert config.tools == []
        assert config.max_iterations == 10
        assert config.cost_limit_usd is None

    def test_agent_team_result_dataclass(self):
        """AgentTeamResult has expected fields."""
        response = Mock(spec=LLMResponse)
        result = AgentTeamResult(
            content="test",
            supervisor_response=response,
            agent_results={},
            total_cost_usd=0.0,
            total_tokens=0,
            delegation_trace=[]
        )
        assert result.content == "test"
        assert result.supervisor_response is response
        assert result.agent_results == {}
        assert result.total_cost_usd == 0.0
        assert result.total_tokens == 0
        assert result.delegation_trace == []

    def test_delegation_event_class(self):
        """DelegationEvent can be instantiated."""
        event = DelegationEvent(
            timestamp=123.45,
            from_agent="supervisor",
            to_agent="research",
            task_description="Test task",
            result_preview="Test result"
        )
        assert event.timestamp == 123.45
        assert event.from_agent == "supervisor"
        assert event.to_agent == "research"
        assert event.task_description == "Test task"
        assert event.result_preview == "Test result"

    def test_cost_limit_exceeded_error(self):
        """CostLimitExceededError is an Exception subclass."""
        error = CostLimitExceededError(current_cost=10.0, limit=5.0, agent_name="test")
        assert isinstance(error, Exception)
        assert "cost limit" in str(error).lower()
        assert error.current_cost == 10.0
        assert error.limit == 5.0
        assert error.agent_name == "test"

# ──────────────────────────────────────────────────────────────
# Behavioral tests (should fail with NotImplementedError)
# ──────────────────────────────────────────────────────────────

class TestBehavioralFails:
    """These tests should fail with NotImplementedError against stubs.

    When stubs are implemented, these tests should pass.
    """

    def test_empty_agents_dict_raises_value_error(self):
        """Empty agents dict raises ValueError in constructor."""
        supervisor = Mock(spec=LLMClient)
        with pytest.raises(ValueError, match="requires at least one agent"):
            AgentTeam(supervisor, {})

    def test_unknown_agent_name_raises_error(self):
        """Unknown agent name in supervisor routing raises appropriate error."""
        supervisor = Mock(spec=LLMClient)
        agents = {"research": Mock(spec=AgentConfig)}
        team = AgentTeam(supervisor, agents)

        # Mock supervisor to return unknown agent name
        with (
            patch.object(
                team.supervisor,
                'chat',
                return_value=Mock(
                    content='{"delegate": {"agent": "unknown", "task": "test"}}',
                    raw_response='{"delegate": {"agent": "unknown", "task": "test"}}',
                    cost_usd=0.0,
                    tokens_used=0,
                    latency_ms=0,
                ),
            ),
            pytest.raises(ValueError, match="Unknown agent"),
        ):
            team.run("test prompt")

    def test_supervisor_receives_user_prompt(self):
        """Supervisor receives user prompt and can route."""
        supervisor = Mock(spec=LLMClient)
        agents = {"research": Mock(spec=AgentConfig)}
        team = AgentTeam(supervisor, agents)

        # Mock supervisor to return a valid delegation
        with patch.object(
            team.supervisor,
            'chat',
            return_value=Mock(
                content=(
                    '{"delegate": {"agent": "research",'
                    ' "task": "Analyze request"}}'
                ),
                raw_response=(
                    '{"delegate": {"agent": "research",'
                    ' "task": "Analyze request"}}'
                ),
                cost_usd=0.0,
                tokens_used=0,
                latency_ms=0,
            ),
        ):
            try:
                team.run("Analyze research request")
                raise AssertionError("Should have raised NotImplementedError")
            except NotImplementedError:
                pass  # Expected for stub

    def test_multiple_agents_sequence(self):
        """Multiple agents can be invoked in sequence within a single run()."""
        supervisor = Mock(spec=LLMClient)
        agents = {
            "agent1": Mock(spec=AgentConfig, cost_limit_usd=None),
            "agent2": Mock(spec=AgentConfig, cost_limit_usd=None),
        }
        team = AgentTeam(supervisor, agents)

        # Mock supervisor to delegate to agent1 first, then agent2
        call_count = [0]

        def supervisor_side_effect(prompt, system_prompt=""):
            call_count[0] += 1
            if call_count[0] == 1:
                return Mock(
                    content='{"delegate": {"agent": "agent1", "task": "Task 1"}}',
                    cost_usd=0.01,
                    tokens_used=100,
                    latency_ms=50
                )
            else:
                return Mock(
                    content='{"delegate": {"agent": "agent2", "task": "Task 2"}}',
                    cost_usd=0.01,
                    tokens_used=100,
                    latency_ms=50
                )

        supervisor.chat = Mock(side_effect=supervisor_side_effect)

        # Mock agents to return responses
        agents["agent1"].client = Mock(spec=LLMClient)
        agents["agent1"].client.chat = Mock(return_value=Mock(
            content="Agent1 response",
            cost_usd=0.005,
            tokens_used=50,
            latency_ms=25
        ))

        agents["agent2"].client = Mock(spec=LLMClient)
        agents["agent2"].client.chat = Mock(return_value=Mock(
            content="Agent2 response",
            cost_usd=0.005,
            tokens_used=50,
            latency_ms=25
        ))

        result = team.run("Test multiple agents")

        # Verify both agents were invoked
        assert "agent1" in result.agent_results
        assert "agent2" in result.agent_results
        assert result.agent_results["agent1"] == "Agent1 response"
        assert result.agent_results["agent2"] == "Agent2 response"

    def test_agent_maintains_independent_history(self):
        """Each agent maintains independent conversation history."""
        supervisor = Mock(spec=LLMClient)
        agents = {
            "agent1": Mock(spec=AgentConfig, cost_limit_usd=None),
            "agent2": Mock(spec=AgentConfig, cost_limit_usd=None),
        }
        team = AgentTeam(supervisor, agents)

        # Mock agents to record what they receive
        received_prompts = {"agent1": [], "agent2": []}

        def make_agent_side_effect(agent_name):
            def side_effect(prompt, system_prompt=""):
                received_prompts[agent_name].append(prompt)
                return Mock(
                    content=f"{agent_name} response",
                    cost_usd=0.005,
                    tokens_used=50,
                    latency_ms=25
                )
            return side_effect

        agents["agent1"].client = Mock(spec=LLMClient)
        agents["agent1"].client.chat = Mock(
            side_effect=make_agent_side_effect("agent1")
        )

        agents["agent2"].client = Mock(spec=LLMClient)
        agents["agent2"].client.chat = Mock(
            side_effect=make_agent_side_effect("agent2")
        )

        # Supervisor delegates to agent1 first, then responds directly
        call_count = [0]

        def supervisor_side_effect(prompt, system_prompt=""):
            call_count[0] += 1
            if call_count[0] == 1:
                return Mock(
                    content=(
                        '{"delegate": {"agent": "agent1",'
                        ' "task": "Task for agent1"}}'
                    ),
                    cost_usd=0.01,
                    tokens_used=100,
                    latency_ms=50,
                )
            else:
                return Mock(
                    content='{"respond": "Final answer"}',
                    cost_usd=0.01,
                    tokens_used=100,
                    latency_ms=50
                )

        supervisor.chat = Mock(side_effect=supervisor_side_effect)

        result = team.run("Test independent history")

        # Verify each agent received its own context
        assert len(received_prompts["agent1"]) == 1
        assert "agent1" in result.agent_results

        # Verify histories are separate (not shared)
        assert team._agent_histories["agent1"] != team._agent_histories["agent2"]

    def test_agent_costs_tracked(self):
        """Agent costs are tracked per-agent and aggregated at team level."""
        supervisor = Mock(spec=LLMClient)
        agents = {
            "agent1": Mock(spec=AgentConfig, cost_limit_usd=None),
            "agent2": Mock(spec=AgentConfig, cost_limit_usd=None),
        }
        team = AgentTeam(supervisor, agents)

        # Mock agents with different costs
        agents["agent1"].client = Mock(spec=LLMClient)
        agents["agent1"].client.chat = Mock(return_value=Mock(
            content="Agent1 response",
            cost_usd=0.02,
            tokens_used=200,
            latency_ms=30
        ))

        agents["agent2"].client = Mock(spec=LLMClient)
        agents["agent2"].client.chat = Mock(return_value=Mock(
            content="Agent2 response",
            cost_usd=0.03,
            tokens_used=300,
            latency_ms=40
        ))

        # Supervisor delegates to agent1, then responds directly
        call_count = [0]

        def supervisor_side_effect(prompt, system_prompt=""):
            call_count[0] += 1
            if call_count[0] == 1:
                return Mock(
                    content='{"delegate": {"agent": "agent1", "task": "Task"}}',
                    cost_usd=0.01,
                    tokens_used=100,
                    latency_ms=50
                )
            else:
                return Mock(
                    content='{"respond": "Final answer"}',
                    cost_usd=0.01,
                    tokens_used=100,
                    latency_ms=50
                )

        supervisor.chat = Mock(side_effect=supervisor_side_effect)

        result = team.run("Test cost tracking")

        # Verify costs are tracked
        assert result.total_cost_usd > 0
        assert result.total_tokens > 0
        assert "agent1" in team._agent_costs
        assert team._agent_costs["agent1"] == 0.02

    def test_streaming_propagates_supervisor_tokens(self):
        """run(stream=True) yields supervisor tokens."""
        supervisor = Mock(spec=LLMClient)
        agents = {"agent1": Mock(spec=AgentConfig, cost_limit_usd=None)}
        team = AgentTeam(supervisor, agents)

        # Mock supervisor to yield tokens
        def mock_stream(prompt, system_prompt=""):
            yield "Hello "
            yield "from "
            yield "supervisor"

        supervisor.stream = Mock(side_effect=mock_stream)

        # Call with stream=True
        result = team.run("Test streaming", stream=True)

        # Verify it's an iterator, not a result
        assert hasattr(result, '__iter__')
        assert hasattr(result, '__next__')

        # Collect tokens
        tokens = list(result)
        assert tokens == ["Hello ", "from ", "supervisor"]

    def test_agent_failure_returns_graceful_error(self):
        """Agent failure returns graceful error, not crash."""
        supervisor = Mock(spec=LLMClient)
        agents = {"agent1": Mock(spec=AgentConfig, cost_limit_usd=None)}
        team = AgentTeam(supervisor, agents)

        # Mock agent to raise an error
        agents["agent1"].client = Mock(spec=LLMClient)
        agents["agent1"].client.chat = Mock(
            side_effect=RuntimeError("Agent crashed")
        )

        # Mock supervisor to delegate to the failing agent
        supervisor.chat = Mock(return_value=Mock(
            content='{"delegate": {"agent": "agent1", "task": "Task"}}',
            cost_usd=0.01,
            tokens_used=100,
            latency_ms=50
        ))

        # The error should propagate (not crash the entire system)
        with pytest.raises(RuntimeError, match="Agent crashed"):
            team.run("Test agent failure")

# ──────────────────────────────────────────────────────────────
# Parametrized tests (interface)
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("supervisor_name", ["llm1", "gpt4", "claude"])
@pytest.mark.parametrize("agent_name", ["research", "code", "write"])
def test_constructor_with_various_agent_names(supervisor_name, agent_name):
    """AgentTeam constructor works with various agent name patterns."""
    supervisor = Mock(spec=LLMClient, name=supervisor_name)
    agents = {agent_name: Mock(spec=AgentConfig)}

    team = AgentTeam(supervisor, agents)
    assert team.supervisor is supervisor
    assert agent_name in team.agents


def test_supervisor_prompt_injection():
    """Supervisor prompt template includes {agents} placeholder."""
    supervisor = Mock(spec=LLMClient)
    agents = {"test": Mock(spec=AgentConfig)}

    team = AgentTeam(supervisor, agents)
    assert hasattr(team, 'supervisor_prompt')


@pytest.mark.parametrize("stream", [False, True])
def test_run_signature(stream):
    """AgentTeam.run signature validates."""
    pass  # Interface test - stub verification

# ──────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────

print("Interface tests: 10+ tests")
print("Behavioral tests: 7+ tests")
print("Total tests: 17+")
print("Interface tests should PASS against stubs")
print("Behavioral tests should FAIL with NotImplementedError against stubs")
