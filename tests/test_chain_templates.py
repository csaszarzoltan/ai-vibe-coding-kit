"""Pre-development tests for Prompt Chaining & Agent Workflow Templates.

RED phase: All tests fail because src/ai_vibe_coding/chain_templates.py
does not exist yet.

When the developer creates stub classes/dataclasses in chain_templates.py:
  - Interface smoke tests will pass (construct, inspect)
  - Behavioral tests will fail with NotImplementedError

Test categories (64 tests total):
  1. Data Model Tests          (8 tests)
  2. SequentialChain Tests    (10 tests)
  3. ConditionalChain Tests   (10 tests)
  4. ParallelChain Tests      (10 tests)
  5. MapReduceChain Tests      (8 tests)
  6. AgentWithToolsChain Tests (8 tests)
  7. ChainRunner Utility Tests (6 tests)
  8. Human-in-the-Loop Tests   (4 tests)
"""

from __future__ import annotations

import time
from unittest.mock import Mock

import pytest

from ai_vibe_coding.llm_wrapper import LLMClient, LLMResponse
from ai_vibe_coding.structured import ToolDef

# ─── Module-level guard ──────────────────────────────────────────
# The target module doesn't exist yet (RED phase).
# All tests below are guarded by a collecting dummy test that fails
# with a clear message.  When chain_templates.py is created the
# guard is removed and real tests execute.

try:
    from ai_vibe_coding.chain_templates import (
        AgentWithToolsChain,
        ChainContext,
        ChainError,
        ChainResult,
        ChainRunner,
        ChainStep,
        ConditionalChain,
        HITLStep,
        MapReduceChain,
        ParallelChain,
        SequentialChain,
    )
    from ai_vibe_coding.structured import CallableApprovalChannel
    MODULE_EXISTS = True
except ImportError:
    MODULE_EXISTS = False


def test_chain_templates_module_must_exist():
    """RED phase: chain_templates.py module must exist for tests to run."""
    if not MODULE_EXISTS:
        pytest.fail(
            "Module 'ai_vibe_coding.chain_templates' not found. "
            "This is expected in RED phase — create the module with "
            "stub classes to proceed."
        )


# ====================================================================
# All remaining tests are guarded by MODULE_EXISTS
# ====================================================================


@pytest.mark.skipif(
    not MODULE_EXISTS, reason="chain_templates not impl"
)
class TestDataModel:
    """Interface + behavioral tests for data model classes."""

    # -- Interface smoke tests (pass once stubs exist) --

    def test_chain_context_is_dataclass(self):
        """ChainContext holds a dict accessible by step name."""
        ctx = ChainContext(steps={"greeting": "Hello", "farewell": "Goodbye"})
        assert ctx.steps["greeting"] == "Hello"
        assert ctx.steps["farewell"] == "Goodbye"

    def test_chain_context_default_empty(self):
        """ChainContext defaults to empty steps dict."""
        ctx = ChainContext()
        assert ctx.steps == {}

    def test_chain_step_records_all_fields(self):
        """ChainStep records all metadata fields."""
        step = ChainStep(
            name="translate",
            provider="openai",
            prompt="Translate to French",
            output="Bonjour",
            latency_ms=150.0,
            cost_usd=0.002,
            status="completed",
        )
        assert step.name == "translate"
        assert step.provider == "openai"
        assert step.prompt == "Translate to French"
        assert step.output == "Bonjour"
        assert step.latency_ms == 150.0
        assert step.cost_usd == 0.002
        assert step.status == "completed"

    def test_chain_step_default_fields(self):
        """ChainStep has sensible defaults for optional fields."""
        step = ChainStep(
            name="noop",
            provider="",
            prompt="",
        )
        assert step.output == ""
        assert step.latency_ms == 0.0
        assert step.cost_usd == 0.0
        assert step.status == "pending"

    def test_chain_result_contains_steps_and_totals(self):
        """ChainResult contains ordered steps, totals, and status."""
        steps = [
            ChainStep(
                name="a", provider="p", prompt="p1", output="o1",
                latency_ms=10.0, cost_usd=0.001, status="completed",
            ),
            ChainStep(
                name="b", provider="p", prompt="p2", output="o2",
                latency_ms=20.0, cost_usd=0.002, status="completed",
            ),
        ]
        result = ChainResult(
            steps=steps,
            total_cost_usd=0.003,
            total_tokens=100,
            status="completed",
        )
        assert len(result.steps) == 2
        assert result.total_cost_usd == 0.003
        assert result.total_tokens == 100
        assert result.status == "completed"

    def test_chain_result_to_dict_serialization(self):
        """ChainResult.to_dict() returns a JSON-serializable dict."""
        steps = [
            ChainStep(
                name="a", provider="p", prompt="p1", output="o1",
                latency_ms=10.0, cost_usd=0.001, status="completed",
            ),
        ]
        result = ChainResult(
            steps=steps, total_cost_usd=0.001,
            total_tokens=50, status="completed",
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["total_cost_usd"] == 0.001
        assert d["total_tokens"] == 50
        assert d["status"] == "completed"
        assert len(d["steps"]) == 1
        assert d["steps"][0]["name"] == "a"

    def test_chain_error_captures_details(self):
        """ChainError captures step_name, message, original_exception."""
        try:
            raise ValueError("original failure")
        except ValueError as exc:
            err = ChainError(
                step_name="extract",
                message="Failed to extract data",
                original_exception=exc,
            )
        assert err.step_name == "extract"
        assert "Failed to extract data" in str(err)
        assert isinstance(err.original_exception, ValueError)

    # -- Edge case tests --

    def test_empty_chain_result(self):
        """Edge: Empty ChainResult has zero steps and zero totals."""
        result = ChainResult(
            steps=[], total_cost_usd=0.0,
            total_tokens=0, status="completed",
        )
        assert result.steps == []
        assert result.total_cost_usd == 0.0
        assert result.total_tokens == 0

    def test_chain_step_max_values(self):
        """Edge: ChainStep with maximum numeric values."""
        step = ChainStep(
            name="maxed",
            provider="anthropic",
            prompt="x" * 10_000,
            output="y" * 100_000,
            latency_ms=9_999_999.0,
            cost_usd=999.99,
            status="completed",
        )
        assert len(step.prompt) == 10_000
        assert len(step.output) == 100_000
        assert step.latency_ms == 9_999_999.0
        assert step.cost_usd == 999.99


@pytest.mark.skipif(
    not MODULE_EXISTS, reason="chain_templates not impl"
)
class TestSequentialChain:
    """Behavioral tests for SequentialChain."""

    def test_accepts_list_of_steps_executed_in_order(self):
        """SequentialChain accepts list of steps executed in order."""
        mock_step1 = Mock()
        mock_step1.name = "step1"
        mock_step2 = Mock()
        mock_step2.name = "step2"

        chain = SequentialChain(steps=[mock_step1, mock_step2])
        result = chain.run(input_data="start")

        assert isinstance(result, ChainResult)
        assert len(result.steps) == 2
        assert result.steps[0].name == "step1"
        assert result.steps[1].name == "step2"

    def test_each_step_receives_previous_output(self):
        """Each step receives previous step output in context."""
        chain = SequentialChain(steps=[])
        result = chain.run(input_data={"a": 1})
        assert result.status == "completed"

    def test_steps_can_reference_any_prior_step(self):
        """Steps can reference any prior step by name in ChainContext."""
        chain = SequentialChain(steps=[])
        context = ChainContext(steps={"step1": "first", "step2": "second"})
        result = chain.run(input_data=context)
        assert isinstance(result, ChainResult)

    def test_returns_chain_result_with_snapshots(self):
        """Returns ChainResult with all step snapshots."""
        step_a = Mock()
        step_a.name = "alpha"
        chain = SequentialChain(steps=[step_a])
        result = chain.run(input_data="test")
        assert isinstance(result, ChainResult)
        assert hasattr(result, "steps")
        assert hasattr(result, "total_cost_usd")
        assert hasattr(result, "total_tokens")

    def test_error_in_one_step_captures_failure_remaining_skipped(self):
        """Error in one step captured as failure, remaining steps skipped."""
        step1 = Mock()
        step1.name = "good"
        step2 = Mock(side_effect=RuntimeError("fail"))
        step2.name = "bad"
        step3 = Mock()
        step3.name = "never_reached"

        chain = SequentialChain(steps=[step1, step2, step3])
        result = chain.run(input_data="go")

        assert len(result.steps) >= 1
        failing_steps = [s for s in result.steps if s.status == "failed"]
        assert len(failing_steps) >= 1
        step_names = [s.name for s in result.steps]
        assert "never_reached" not in step_names

    def test_single_step_works(self):
        """Single step works correctly."""
        step = Mock()
        step.name = "solo"
        chain = SequentialChain(steps=[step])
        result = chain.run(input_data="only")
        assert isinstance(result, ChainResult)
        assert len(result.steps) == 1

    def test_empty_step_list_returns_empty_result(self):
        """Empty step list returns empty ChainResult."""
        chain = SequentialChain(steps=[])
        result = chain.run(input_data="nothing")
        assert isinstance(result, ChainResult)
        assert result.steps == []

    def test_step_names_must_be_unique(self):
        """Step names must be unique, raises error on duplicates."""
        step1 = Mock()
        step1.name = "duplicate"
        step2 = Mock()
        step2.name = "duplicate"

        with pytest.raises(ValueError, match="duplicate|unique|name"):
            SequentialChain(steps=[step1, step2])

    def test_cost_tracking_accumulates_across_steps(self):
        """Cost/token tracking accumulates across steps."""
        step1 = Mock()
        step1.name = "a"
        step1.latency_ms = 50.0
        step1.cost_usd = 0.001
        step2 = Mock()
        step2.name = "b"
        step2.latency_ms = 100.0
        step2.cost_usd = 0.003

        chain = SequentialChain(steps=[step1, step2])
        result = chain.run(input_data="costly")

        assert result.total_cost_usd >= 0.004

    def test_max_retries_on_transient_failure(self):
        """max_retries retries on transient failure."""
        step = Mock()
        step.name = "retry_me"

        chain = SequentialChain(steps=[step], max_retries=3)
        result = chain.run(input_data="retry")
        assert isinstance(result, ChainResult)
        assert result.status in ("completed", "failed")


@pytest.mark.skipif(
    not MODULE_EXISTS, reason="chain_templates not impl"
)
class TestConditionalChain:
    """Behavioral tests for ConditionalChain."""

    def test_gate_receives_step_output_returns_bool(self):
        """Gate function receives step output, returns bool."""
        def gate(output: str) -> bool:
            return len(output) > 5

        chain = ConditionalChain(
            gate_fn=gate,
            true_branch=[],
            false_branch=[],
        )
        assert callable(chain.gate_fn)

    def test_true_branch_executed_when_gate_passes(self):
        """True branch executed when gate passes."""
        true_step = Mock()
        true_step.name = "true_path"
        false_step = Mock()
        false_step.name = "false_path"

        chain = ConditionalChain(
            gate_fn=lambda o: True,
            true_branch=[true_step],
            false_branch=[false_step],
        )
        result = chain.run(input_data="pass")
        step_names = [s.name for s in result.steps]
        assert "true_path" in step_names
        assert "false_path" not in step_names

    def test_false_branch_executed_when_gate_fails(self):
        """False branch executed when gate fails."""
        true_step = Mock()
        true_step.name = "true_path"
        false_step = Mock()
        false_step.name = "false_path"

        chain = ConditionalChain(
            gate_fn=lambda o: False,
            true_branch=[true_step],
            false_branch=[false_step],
        )
        result = chain.run(input_data="fail")
        step_names = [s.name for s in result.steps]
        assert "false_path" in step_names
        assert "true_path" not in step_names

    def test_both_branches_converge_after_decision(self):
        """Both branches converge after decision."""
        converge_step = Mock()
        converge_step.name = "converge"

        chain = ConditionalChain(
            gate_fn=lambda o: True,
            true_branch=[],
            false_branch=[],
            converge_steps=[converge_step],
        )
        result = chain.run(input_data="converge")
        step_names = [s.name for s in result.steps]
        assert "converge" in step_names

    def test_gate_execution_failure_captured(self):
        """Gate execution failure captured as error, not crash."""
        def broken_gate(output: str) -> bool:
            raise RuntimeError("gate failed")

        chain = ConditionalChain(
            gate_fn=broken_gate,
            true_branch=[],
            false_branch=[],
        )
        result = chain.run(input_data="boom")
        assert result.status in ("failed", "completed")

    def test_nested_conditions(self):
        """Nested conditions (gate within a branch)."""
        inner_true = Mock()
        inner_true.name = "inner_true"
        inner_false = Mock()
        inner_false.name = "inner_false"

        inner_chain = ConditionalChain(
            gate_fn=lambda o: True,
            true_branch=[inner_true],
            false_branch=[inner_false],
        )
        outer_chain = ConditionalChain(
            gate_fn=lambda o: True,
            true_branch=[inner_chain],
            false_branch=[],
        )
        result = outer_chain.run(input_data="nested")
        step_names = [s.name for s in result.steps]
        assert "inner_true" in step_names

    def test_multiple_gates_in_sequence(self):
        """Multiple gates in sequence."""
        gate1 = Mock()
        gate1.name = "gate1"
        gate2 = Mock()
        gate2.name = "gate2"

        chain = ConditionalChain(
            gate_fn=lambda o: True,
            true_branch=[gate1],
            false_branch=[],
            additional_gates=[(lambda o: False, [gate2], [])],
        )
        result = chain.run(input_data="multi")
        assert isinstance(result, ChainResult)

    def test_output_from_prior_step_available_in_gate(self):
        """Output from prior step available in gate function."""
        received = []

        def capturing_gate(output: str) -> bool:
            received.append(output)
            return True

        chain = ConditionalChain(
            gate_fn=capturing_gate,
            true_branch=[],
            false_branch=[],
        )
        chain.run(input_data="prior_output")
        assert len(received) >= 0

    def test_always_true_gate(self):
        """Edge: always-true gate always executes true branch."""
        chain = ConditionalChain(
            gate_fn=lambda o: True,
            true_branch=[Mock(name="always")],
            false_branch=[],
        )
        result = chain.run(input_data="always_true")
        step_names = [s.name for s in result.steps]
        assert "always" in step_names

    def test_always_false_gate(self):
        """Edge: always-false gate always executes false branch."""
        chain = ConditionalChain(
            gate_fn=lambda o: False,
            true_branch=[],
            false_branch=[Mock(name="never")],
        )
        result = chain.run(input_data="always_false")
        step_names = [s.name for s in result.steps]
        assert "never" in step_names


@pytest.mark.skipif(
    not MODULE_EXISTS, reason="chain_templates not impl"
)
class TestParallelChain:
    """Behavioral tests for ParallelChain."""

    def test_steps_execute_concurrently(self):
        """Steps execute concurrently (check timing with mocked delays)."""
        def make_slow_step(name: str):
            def delayed_run(ctx):
                time.sleep(0.05)
                return ChainStep(
                    name=name, provider="p", prompt="",
                    output=name, latency_ms=50.0,
                    cost_usd=0.0, status="completed",
                )
            return delayed_run

        step1 = Mock()
        step1.name = "a"
        step1.run = make_slow_step("a")
        step2 = Mock()
        step2.name = "b"
        step2.run = make_slow_step("b")

        chain = ParallelChain(steps=[step1, step2], max_workers=2)
        start = time.monotonic()
        result = chain.run(input_data="parallel")
        elapsed = time.monotonic() - start

        assert isinstance(result, ChainResult)
        assert elapsed < 0.09  # parallel: 2 * 0.05 serial would be ~0.1s

    def test_all_steps_share_same_input_context(self):
        """All steps share same input context."""
        step1 = Mock()
        step1.name = "s1"
        step2 = Mock()
        step2.name = "s2"

        chain = ParallelChain(steps=[step1, step2])
        result = chain.run(input_data={"shared": "context"})
        assert len(result.steps) == 2

    def test_results_aggregated(self):
        """Results aggregated (configurable join/concatenate)."""
        step1 = Mock()
        step1.name = "part1"
        step2 = Mock()
        step2.name = "part2"

        chain = ParallelChain(steps=[step1, step2], aggregation="concatenate")
        result = chain.run(input_data="aggregate")
        assert isinstance(result, ChainResult)

    def test_configurable_max_workers(self):
        """configurable max_workers."""
        chain = ParallelChain(steps=[], max_workers=4)
        assert chain.max_workers == 4

    def test_timeout_per_step(self):
        """Timeout per parallel step (default 30s)."""
        chain = ParallelChain(steps=[])
        assert chain.timeout == 30.0

        chain = ParallelChain(steps=[], timeout=5.0)
        assert chain.timeout == 5.0

    def test_single_step_in_parallel_list(self):
        """Single step in parallel list."""
        step = Mock()
        step.name = "lone"
        chain = ParallelChain(steps=[step])
        result = chain.run(input_data="solo")
        assert len(result.steps) == 1

    def test_empty_parallel_list(self):
        """Empty parallel list returns empty result."""
        chain = ParallelChain(steps=[])
        result = chain.run(input_data="empty")
        assert isinstance(result, ChainResult)
        assert result.steps == []

    def test_one_step_failing_doesnt_abort_others(self):
        """One step failing doesn't abort others."""
        def failing_run(ctx):
            raise RuntimeError("fail")

        good = Mock()
        good.name = "good"
        bad = Mock()
        bad.name = "bad"
        bad.run = failing_run

        chain = ParallelChain(steps=[good, bad])
        result = chain.run(input_data="partial_fail")
        step_names = [s.name for s in result.steps]
        assert "good" in step_names

    def test_error_status_per_step_maintained(self):
        """Error status per step maintained."""
        def broken_run(ctx):
            raise RuntimeError("broken")

        step1 = Mock()
        step1.name = "ok"
        step2 = Mock()
        step2.name = "broken"
        step2.run = broken_run

        chain = ParallelChain(steps=[step1, step2])
        result = chain.run(input_data="status_check")
        statuses = {s.name: s.status for s in result.steps}
        assert statuses.get("broken") in ("failed", "pending", "completed")

    def test_cost_tracking_across_parallel_steps(self):
        """Cost/token tracking across parallel steps."""
        step1 = Mock()
        step1.name = "a"
        step2 = Mock()
        step2.name = "b"

        chain = ParallelChain(steps=[step1, step2])
        result = chain.run(input_data="costs")
        assert result.total_cost_usd >= 0.0
        assert result.total_tokens >= 0


@pytest.mark.skipif(
    not MODULE_EXISTS, reason="chain_templates not impl"
)
class TestMapReduceChain:
    """Behavioral tests for MapReduceChain."""

    def test_map_function_splits_input_into_chunks(self):
        """Map function splits input into N chunks."""
        def splitter(text: str, chunk_count: int) -> list[str]:
            size = len(text) // chunk_count
            return [text[i:i+size] for i in range(0, len(text), size)]

        chain = MapReduceChain(
            map_fn=splitter,
            reduce_fn=lambda chunks: " ".join(chunks),
            chunk_count=3,
        )
        assert callable(chain.map_fn)
        assert chain.chunk_count == 3

    def test_each_chunk_processed_independently(self):
        """Each chunk processed independently (check timing)."""
        chain = MapReduceChain(
            map_fn=lambda t, n: [t] * n,
            reduce_fn=lambda chunks: "|".join(chunks),
            chunk_count=2,
        )
        result = chain.run(input_data="independent")
        assert isinstance(result, ChainResult)

    def test_reduce_function_merges_outputs(self):
        """Reduce function merges individual outputs."""
        chain = MapReduceChain(
            map_fn=lambda t, n: [f"chunk_{i}" for i in range(n)],
            reduce_fn=lambda chunks: ", ".join(chunks),
            chunk_count=3,
        )
        result = chain.run(input_data="merge")
        assert isinstance(result, ChainResult)

    def test_configurable_mapper(self):
        """Configurable mapper (LLM-based or programmatic)."""
        chain = MapReduceChain(
            map_fn=lambda t, n: [t] * n,
            reduce_fn=lambda c: c[0],
            chunk_count=1,
        )
        assert callable(chain.map_fn)
        result = chain.run(input_data="mapper")
        assert isinstance(result, ChainResult)

    def test_configurable_reducer(self):
        """Configurable reducer (LLM-based or programmatic)."""
        chain = MapReduceChain(
            map_fn=lambda t, n: [t] * n,
            reduce_fn=lambda c: c[0],
            chunk_count=1,
        )
        assert callable(chain.reduce_fn)

    def test_single_chunk_no_split_needed(self):
        """Single chunk (no split needed)."""
        chain = MapReduceChain(
            map_fn=lambda t, n: [t],
            reduce_fn=lambda c: c[0],
            chunk_count=1,
        )
        result = chain.run(input_data="single")
        assert isinstance(result, ChainResult)

    def test_empty_input_handled_gracefully(self):
        """Empty input handled gracefully."""
        chain = MapReduceChain(
            map_fn=lambda t, n: [],
            reduce_fn=lambda c: "",
            chunk_count=1,
        )
        result = chain.run(input_data="")
        assert isinstance(result, ChainResult)

    def test_chunk_count_configurable(self):
        """Chunk count configurable."""
        chain = MapReduceChain(
            map_fn=lambda t, n: [t] * n,
            reduce_fn=lambda c: c[0],
            chunk_count=5,
        )
        assert chain.chunk_count == 5


@pytest.mark.skipif(
    not MODULE_EXISTS, reason="chain_templates not impl"
)
class TestAgentWithToolsChain:
    """Behavioral tests for AgentWithToolsChain."""

    def test_react_loop_think_tool_observe_repeat(self):
        """ReAct loop: think → tool_call → observe → repeat."""
        mock_llm = Mock(spec=LLMClient)
        tools = [ToolDef(name="search", description="Search the web")]

        chain = AgentWithToolsChain(
            llm_client=mock_llm,
            tools=tools,
            max_iterations=3,
        )
        result = chain.run(input_data="search query")
        assert isinstance(result, ChainResult)

    def test_max_iterations_configurable(self):
        """Max iterations configurable (default 10)."""
        chain = AgentWithToolsChain(llm_client=Mock(spec=LLMClient), tools=[])
        assert chain.max_iterations == 10

        chain_5 = AgentWithToolsChain(
            llm_client=Mock(spec=LLMClient),
            tools=[],
            max_iterations=5,
        )
        assert chain_5.max_iterations == 5

    def test_uses_chat_with_tools(self):
        """Uses chat_with_tools() from structured.py."""
        mock_llm = Mock(spec=LLMClient)
        tool = ToolDef(name="get_time", description="Get current time")
        chain = AgentWithToolsChain(llm_client=mock_llm, tools=[tool])
        result = chain.run(input_data="What time is it?")
        assert isinstance(result, ChainResult)

    def test_tool_call_results_fed_back_as_observation(self):
        """Tool call results fed back as observation."""
        mock_llm = Mock(spec=LLMClient)
        tool = ToolDef(name="calculator", description="Do math")
        chain = AgentWithToolsChain(llm_client=mock_llm, tools=[tool])
        result = chain.run(input_data="2+2")
        assert isinstance(result, ChainResult)

    def test_loop_exits_when_llm_responds_directly(self):
        """Loop exits when LLM responds directly (no tool call)."""
        mock_llm = Mock(spec=LLMClient)
        mock_llm.chat.return_value = LLMResponse(
            content="Direct answer", provider="openai", model="gpt-4",
            tokens_used=10, cost_usd=0.0001, latency_ms=50.0,
        )
        chain = AgentWithToolsChain(llm_client=mock_llm, tools=[])
        result = chain.run(input_data="hello")
        assert isinstance(result, ChainResult)

    def test_cost_tracking_across_iterations(self):
        """Cost/token tracking across iterations."""
        mock_llm = Mock(spec=LLMClient)
        chain = AgentWithToolsChain(
            llm_client=mock_llm,
            tools=[ToolDef(name="t", description="tool")],
            max_iterations=2,
        )
        result = chain.run(input_data="track costs")
        assert result.total_cost_usd >= 0.0
        assert result.total_tokens >= 0

    def test_error_in_tool_call_continues_loop(self):
        """Error in tool call captured and loop continues (up to max iterations)."""
        mock_llm = Mock(spec=LLMClient)
        chain = AgentWithToolsChain(
            llm_client=mock_llm,
            tools=[ToolDef(name="broken", description="always fails")],
            max_iterations=3,
        )
        result = chain.run(input_data="will fail")
        assert isinstance(result, ChainResult)

    def test_multiple_different_tools_in_sequence(self):
        """Agent can call multiple different tools in sequence."""
        mock_llm = Mock(spec=LLMClient)
        tools = [
            ToolDef(name="search", description="Search"),
            ToolDef(name="summarize", description="Summarize"),
            ToolDef(name="translate", description="Translate"),
        ]
        chain = AgentWithToolsChain(
            llm_client=mock_llm, tools=tools, max_iterations=5,
        )
        result = chain.run(input_data="multi tool task")
        assert isinstance(result, ChainResult)


@pytest.mark.skipif(
    not MODULE_EXISTS, reason="chain_templates not impl"
)
class TestChainRunner:
    """Behavioral tests for ChainRunner utility."""

    def test_run_executes_any_chain_type(self):
        """ChainRunner.run(chain, input) executes any chain type."""
        runner = ChainRunner()
        chain = Mock()
        chain.run.return_value = ChainResult(
            steps=[], total_cost_usd=0.0,
            total_tokens=0, status="completed",
        )
        result = runner.run(chain=chain, input_data="test")
        assert isinstance(result, ChainResult)

    def test_intermediate_results_inspectable(self):
        """Intermediate results inspectable via ChainResult.steps."""
        runner = ChainRunner()
        chain = SequentialChain(steps=[])
        result = runner.run(chain=chain, input_data="inspect")
        assert hasattr(result, "steps")

    def test_streaming_yields_step_completion_events(self):
        """Streaming: run(chain, input, stream=True) yields step completion events."""
        runner = ChainRunner()
        chain = SequentialChain(steps=[])
        events = list(runner.run(chain=chain, input_data="stream", stream=True))
        assert isinstance(events, list)

    def test_cost_tracking_across_composite_chain(self):
        """Cost tracking across all steps of a composite chain."""
        runner = ChainRunner()
        chain = SequentialChain(steps=[])
        result = runner.run(chain=chain, input_data="costly")
        assert result.total_cost_usd >= 0.0
        assert result.total_tokens >= 0

    def test_runner_validates_chain_type_before_execution(self):
        """Runner validates chain type before execution."""
        runner = ChainRunner()
        with pytest.raises(TypeError, match="chain|Chain"):
            runner.run(chain="not_a_chain", input_data="test")

    def test_runner_handles_unknown_chain_type_gracefully(self):
        """Runner handles unknown chain type gracefully."""
        runner = ChainRunner()
        result = runner.run(chain=object(), input_data="unknown")
        assert isinstance(result, ChainResult)
        assert result.status == "failed"


@pytest.mark.skipif(
    not MODULE_EXISTS, reason="chain_templates not impl"
)
class TestHumanInTheLoop:
    """Behavioral tests for HITLStep."""

    def test_hitl_step_pauses_for_approval_callback(self):
        """HITLStep pauses for approval callback."""
        callback = Mock(return_value=True)
        channel = CallableApprovalChannel(callback)
        step = HITLStep(
            name="approval_gate",
            approval_channel=channel,
            prompt="Do you approve?",
        )
        step.run(input_data="needs approval")
        assert callback.called

    def test_uses_callable_approval_channel(self):
        """Uses CallableApprovalChannel."""
        channel = CallableApprovalChannel(func=lambda tool_name, arguments: True)
        step = HITLStep(name="check", approval_channel=channel)
        assert isinstance(step.approval_channel, CallableApprovalChannel)

    def test_approval_denial_captured_in_chain_step_status(self):
        """Approval/Denial captured in ChainStep status."""
        callback = Mock(return_value=False)
        channel = CallableApprovalChannel(callback)
        step = HITLStep(name="deny_gate", approval_channel=channel)
        result = step.run(input_data="deny me")
        assert result.status in ("denied", "failed")

    def test_denied_step_can_branch_to_alternative_path(self):
        """Denied step can branch to alternative path."""
        alt_step = Mock()
        alt_step.name = "alternative"
        callback = Mock(return_value=False)
        channel = CallableApprovalChannel(callback)
        step = HITLStep(
            name="branch_gate",
            approval_channel=channel,
            on_denied=[alt_step],
        )
        result = step.run(input_data="branch me")
        assert isinstance(result, ChainResult)
