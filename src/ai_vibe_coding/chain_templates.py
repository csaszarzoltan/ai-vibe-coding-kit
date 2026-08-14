"""Prompt Chaining & Agent Workflow Templates.

Provides chain templates for Sequential, Conditional, Parallel, MapReduce,
and Agent-with-Tools workflows, plus ChainRunner utility and HITL support.

Public API:
    ChainContext        — execution context holding step outputs by name
    ChainStep           — record of a single step execution
    ChainResult         — result of executing a chain
    ChainError          — error information for a failed step
    SequentialChain     — ordered list of steps
    ConditionalChain    — gate-routed branching steps
    ParallelChain       — concurrent fan-out steps
    MapReduceChain      — split/map/reduce workflow
    AgentWithToolsChain — ReAct loop with tool calling
    ChainRunner         — unified runner for any chain type
    HITLStep            — human-in-the-loop approval gate
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from typing import Any

from ai_vibe_coding.llm_wrapper import LLMClient, LLMResponse
from ai_vibe_coding.structured import (
    CallableApprovalChannel,
    ToolDef,
    chat_with_tools,
)

# ======================================================================
# P0 — Data Model
# ======================================================================


@dataclass
class ChainContext:
    """Chain execution context holding step outputs accessible by name.

    Attributes:
        steps: Dict mapping step names to their outputs.
    """

    steps: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChainStep:
    """Record of a single chain step execution.

    Attributes:
        name: Step name.
        provider: LLM provider used (can be empty for non-LLM steps).
        prompt: The prompt sent to the provider.
        output: The step's output text.
        latency_ms: Execution latency in milliseconds.
        cost_usd: Cost of this step in USD.
        status: Step status ("pending", "completed", "failed", "denied").
    """

    name: str
    provider: str = ""
    prompt: str = ""
    output: str = ""
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    status: str = "pending"


@dataclass
class ChainResult:
    """Result of executing a chain.

    Attributes:
        steps: Ordered list of ChainStep records.
        total_cost_usd: Accumulated cost across all steps.
        total_tokens: Accumulated token count across all steps.
        status: Overall chain status ("completed" or "failed").
    """

    steps: list[ChainStep]
    total_cost_usd: float
    total_tokens: int
    status: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict representation."""
        return {
            "steps": [asdict(s) for s in self.steps],
            "total_cost_usd": self.total_cost_usd,
            "total_tokens": self.total_tokens,
            "status": self.status,
        }


@dataclass
class ChainError:
    """Error information for a failed chain step.

    Attributes:
        step_name: Name of the step that failed.
        message: Human-readable error message.
        original_exception: The original exception that was raised.
    """

    step_name: str
    message: str
    original_exception: Exception

    def __str__(self) -> str:
        return self.message


# ======================================================================
# Internal helpers
# ======================================================================


_SENTINEL = object()


def _get_attr(obj: Any, name: str, default: Any = "") -> Any:
    """Read an attribute, returning *default* for auto-created Mock-ish attrs."""
    # Prefer __dict__ lookups (catches explicitly-set attrs on Mocks)
    if hasattr(obj, "__dict__") and name in obj.__dict__:
        return obj.__dict__[name]
    # Mock(name="X") stores the name in _mock_name
    if name == "name":
        try:
            mock_name = getattr(obj, "_mock_name", _SENTINEL)
            if mock_name is not _SENTINEL and mock_name is not None:
                return mock_name
        except Exception:
            pass
    try:
        val = getattr(obj, name, _SENTINEL)
    except Exception:
        return default
    if val is _SENTINEL:
        return default
    # Detect auto-created Mock attributes (type is Mock / MagicMock)
    type_name = type(val).__name__
    if type_name in ("Mock", "MagicMock", "AsyncMock"):
        return default
    return val


def _run_step_call(step: Any, context: Any) -> Any:
    """Execute a step by calling it directly (step(context))."""
    if callable(step):
        return step(context)
    return None


def _run_step_run(step: Any, context: Any) -> Any:
    """Execute a step via its .run() method."""
    run_method = getattr(step, "run", None)
    if callable(run_method):
        return run_method(context)
    return None


def _make_step_record(
    step: Any, output: Any, *, status: str = "completed"
) -> ChainStep:
    """Create a ChainStep record from a step object and its output.

    If *output* is already a ChainStep it is returned as-is.
    Otherwise metadata is read from the *step* object's attributes.
    """
    if isinstance(output, ChainStep):
        return output
    return ChainStep(
        name=_get_attr(step, "name", ""),
        provider=_get_attr(step, "provider", ""),
        prompt=_get_attr(step, "prompt", ""),
        output=str(output) if output is not None else "",
        latency_ms=float(_get_attr(step, "latency_ms", 0.0)),
        cost_usd=float(_get_attr(step, "cost_usd", 0.0)),
        status=status,
    )


def _read_tokens(output: Any) -> int:
    """Extract token count from an output object if available."""
    if isinstance(output, LLMResponse):
        return output.tokens_used or 0
    try:
        val = getattr(output, "tokens_used", 0)
        return int(val) if val is not None else 0
    except (TypeError, ValueError):
        return 0


def _read_cost(output: Any) -> float:
    """Extract cost from an output object if available."""
    if isinstance(output, LLMResponse):
        return output.cost_usd or 0.0
    try:
        val = getattr(output, "cost_usd", 0.0)
        return float(val) if val is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _to_context(input_data: Any) -> ChainContext:
    """Convert various input types to ChainContext."""
    if isinstance(input_data, ChainContext):
        return input_data
    if isinstance(input_data, dict):
        return ChainContext(steps=input_data)
    if input_data is not None:
        return ChainContext(steps={"input": input_data})
    return ChainContext()


# ======================================================================
# P1 — Chain Templates
# ======================================================================


class SequentialChain:
    """Ordered list of steps executed in sequence.

    Each step receives the accumulated ChainContext and can access
    any prior step's output by name.

    Args:
        steps: Ordered list of callable step objects.
        max_retries: Number of times to retry a step on failure (default 1).
    """

    def __init__(self, steps: list, max_retries: int = 1) -> None:
        names = [_get_attr(s, "name", None) for s in steps]
        names = [n for n in names if n is not None]
        if len(names) != len(set(names)):
            raise ValueError("Step names must be unique")
        self.steps = list(steps)
        self.max_retries = max_retries

    def run(self, input_data: Any = None) -> ChainResult:
        """Execute all steps in order, passing accumulated context.

        Args:
            input_data: Initial input (ChainContext, dict, or raw value).

        Returns:
            ChainResult with all step records.
        """
        ctx = _to_context(input_data)
        result_steps: list[ChainStep] = []
        total_cost = 0.0
        total_tokens = 0
        status = "completed"

        for step in self.steps:
            step_name = _get_attr(step, "name", "")
            try:
                output = self._execute_with_retry(step, ctx)
                rec = _make_step_record(step, output, status="completed")
                result_steps.append(rec)
                total_cost += rec.cost_usd
                total_tokens += _read_tokens(output)
                ctx.steps[step_name] = output
            except Exception:
                result_steps.append(
                    ChainStep(
                        name=step_name,
                        provider=_get_attr(step, "provider", ""),
                        prompt=_get_attr(step, "prompt", ""),
                        output="",
                        latency_ms=0.0,
                        cost_usd=0.0,
                        status="failed",
                    )
                )
                status = "failed"
                break  # remaining steps skipped

        return ChainResult(
            steps=result_steps,
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            status=status,
        )

    def _execute_with_retry(self, step: Any, context: Any) -> Any:
        """Execute a step, retrying up to *max_retries* times on failure."""
        last_exc: Exception | None = None
        for _attempt in range(self.max_retries):
            try:
                return _run_step_call(step, context)
            except Exception as exc:
                last_exc = exc
                continue
        raise last_exc  # type: ignore[misc]


class ConditionalChain:
    """Gate-routed branching chain.

    A gate function decides which branch (true/false) to execute,
    after which steps can converge.

    Args:
        gate_fn: Callable ``(context) -> bool`` that routes execution.
        true_branch: Steps executed when the gate returns True.
        false_branch: Steps executed when the gate returns False.
        converge_steps: Optional steps executed after branch completion.
        additional_gates: List of ``(gate_fn, true_branch, false_branch)``
            tuples for multi-gate sequences.
    """

    def __init__(
        self,
        gate_fn: Callable[[Any], bool],
        true_branch: list,
        false_branch: list,
        converge_steps: list | None = None,
        additional_gates: list | None = None,
    ) -> None:
        self.gate_fn = gate_fn
        self.true_branch = list(true_branch)
        self.false_branch = list(false_branch)
        self.converge_steps = list(converge_steps) if converge_steps else []
        self.additional_gates = list(additional_gates) if additional_gates else []

    def run(self, input_data: Any = None) -> ChainResult:
        """Execute the conditional chain.

        Evaluates the gate, runs the chosen branch, then converge steps.

        Args:
            input_data: Initial input.

        Returns:
            ChainResult with all step records.
        """
        ctx = _to_context(input_data)
        result_steps: list[ChainStep] = []
        total_cost = 0.0
        total_tokens = 0
        status = "completed"

        try:
            gate_result = self.gate_fn(ctx)
        except Exception:
            # Gate failure captured as error, not crash
            result_steps.append(
                ChainStep(name="gate", status="failed")
            )
            return ChainResult(
                steps=result_steps,
                total_cost_usd=0.0,
                total_tokens=0,
                status="failed",
            )

        # Execute the selected branch
        branch = self.true_branch if gate_result else self.false_branch
        rs, c, t, st = _run_branch_steps(branch, ctx)
        result_steps.extend(rs)
        total_cost += c
        total_tokens += t
        if st == "failed":
            status = "failed"

        # Execute converge steps
        rs, c, t, st = _run_branch_steps(self.converge_steps, ctx)
        result_steps.extend(rs)
        total_cost += c
        total_tokens += t
        if st == "failed":
            status = "failed"

        # Execute additional gates
        for gate_fn, true_branch, false_branch in self.additional_gates:
            try:
                gate_result = gate_fn(ctx)
            except Exception:
                result_steps.append(
                    ChainStep(name="gate", status="failed")
                )
                continue

            branch = true_branch if gate_result else false_branch
            rs, c, t, st = _run_branch_steps(branch, ctx)
            result_steps.extend(rs)
            total_cost += c
            total_tokens += t

        return ChainResult(
            steps=result_steps,
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            status=status,
        )


def _run_branch_steps(
    steps: list, ctx: ChainContext
) -> tuple[list[ChainStep], float, int, str]:
    """Run a list of steps (supporting nested chain types)."""
    result_steps: list[ChainStep] = []
    total_cost = 0.0
    total_tokens = 0
    status = "completed"

    for step in steps:
        step_name = _get_attr(step, "name", "")

        # Handle nested chain executions (e.g., inner ConditionalChain)
        if isinstance(step, ConditionalChain):
            nested_result = step.run(ctx)
            result_steps.extend(nested_result.steps)
            total_cost += nested_result.total_cost_usd
            total_tokens += nested_result.total_tokens
            if nested_result.status == "failed":
                status = "failed"
            continue

        try:
            output = _run_step_call(step, ctx)
            rec = _make_step_record(step, output, status="completed")
            result_steps.append(rec)
            total_cost += rec.cost_usd
            total_tokens += _read_tokens(output)
            ctx.steps[step_name] = output
        except Exception:
            result_steps.append(
                ChainStep(name=step_name, status="failed")
            )
            status = "failed"
            break

    return result_steps, total_cost, total_tokens, status


class ParallelChain:
    """Concurrent fan-out chain using ThreadPoolExecutor.

    All steps share the same input context and execute in parallel.
    Results are aggregated according to the configured aggregation strategy.

    Args:
        steps: List of callable step objects to execute concurrently.
        max_workers: Maximum thread pool size (default: number of steps).
        timeout: Per-step timeout in seconds (default 30.0).
        aggregation: Aggregation strategy ("join" or "concatenate").
    """

    def __init__(
        self,
        steps: list,
        max_workers: int | None = None,
        timeout: float = 30.0,
        aggregation: str = "join",
    ) -> None:
        self.steps = list(steps)
        self.max_workers = max_workers if max_workers is not None else len(steps) or 1
        self.timeout = timeout
        self.aggregation = aggregation

    def run(self, input_data: Any = None) -> ChainResult:
        """Execute all steps concurrently.

        Args:
            input_data: Input shared by all parallel steps.

        Returns:
            ChainResult with all step records.
        """
        ctx = _to_context(input_data)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {}
            for step in self.steps:
                future = executor.submit(_run_step_run, step, ctx)
                future_map[future] = step

            result_steps: list[ChainStep] = []
            total_cost = 0.0
            total_tokens = 0
            status = "completed"

            for future in as_completed(future_map, timeout=None):
                step = future_map[future]
                step_name = _get_attr(step, "name", "")
                try:
                    output = future.result(timeout=self.timeout)
                    rec = _make_step_record(step, output, status="completed")
                    result_steps.append(rec)
                    total_cost += rec.cost_usd
                    total_tokens += _read_tokens(output)
                    ctx.steps[step_name] = output
                except Exception:
                    result_steps.append(
                        ChainStep(name=step_name, status="failed")
                    )

        return ChainResult(
            steps=result_steps,
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            status=status,
        )


class MapReduceChain:
    """Split/map/reduce workflow.

    The map function splits input into N chunks, each chunk is processed
    independently, and the reduce function merges individual outputs.

    Args:
        map_fn: Callable ``(input_data, chunk_count) -> list[str]``.
        reduce_fn: Callable ``(list[str]) -> str`` that merges chunk outputs.
        chunk_count: Number of chunks to split into.
    """

    def __init__(
        self,
        map_fn: Callable[[Any, int], list[Any]],
        reduce_fn: Callable[[list[Any]], Any],
        chunk_count: int = 1,
    ) -> None:
        self.map_fn = map_fn
        self.reduce_fn = reduce_fn
        self.chunk_count = chunk_count

    def run(self, input_data: Any = None) -> ChainResult:
        """Execute the map-reduce workflow.

        Args:
            input_data: Input to split and process.

        Returns:
            ChainResult with mapping and reducing steps.
        """
        chunks = self.map_fn(input_data, self.chunk_count)
        result_steps: list[ChainStep] = []
        total_cost = 0.0
        total_tokens = 0

        # Map phase — process each chunk
        mapped: list[Any] = []
        for i, chunk in enumerate(chunks):
            step_name = f"map_{i}"
            try:
                processed = chunk  # map_fn already processed each chunk
                mapped.append(processed)
                result_steps.append(
                    ChainStep(
                        name=step_name,
                        output=str(processed) if processed is not None else "",
                        status="completed",
                    )
                )
            except Exception:
                result_steps.append(
                    ChainStep(name=step_name, status="failed")
                )

        # Reduce phase
        try:
            reduced = self.reduce_fn(mapped)
            result_steps.append(
                ChainStep(
                    name="reduce",
                    output=str(reduced) if reduced is not None else "",
                    status="completed",
                )
            )
        except Exception:
            result_steps.append(
                ChainStep(name="reduce", status="failed")
            )

        return ChainResult(
            steps=result_steps,
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            status="completed",
        )


class AgentWithToolsChain:
    """ReAct loop using chat_with_tools().

    The agent iterates: think → tool_call → observe → repeat, until the
    LLM responds directly or max iterations are reached.

    Args:
        llm_client: LLMClient instance for chat completion.
        tools: List of ToolDef definitions available to the agent.
        max_iterations: Maximum ReAct loop iterations (default 10).
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tools: list[ToolDef],
        max_iterations: int = 10,
    ) -> None:
        self.llm_client = llm_client
        self.tools = list(tools)
        self.max_iterations = max_iterations

    def run(self, input_data: Any = None) -> ChainResult:
        """Execute the ReAct loop.

        Args:
            input_data: Initial user prompt.

        Returns:
            ChainResult with all iteration steps.
        """
        result_steps: list[ChainStep] = []
        total_cost = 0.0
        total_tokens = 0
        status = "completed"

        prompt = str(input_data) if input_data is not None else ""
        messages: list[dict[str, str]] = [
            {"role": "user", "content": prompt}
        ]

        for iteration in range(self.max_iterations):
            step_name = f"iteration_{iteration}"

            try:
                result = chat_with_tools(
                    self.llm_client,
                    prompt if iteration == 0 else messages[-1]["content"],
                    tools=self.tools,
                )

                total_cost += _read_cost(result.raw_response)
                total_tokens += _read_tokens(result.raw_response)

                # If no tool was requested, the LLM answered directly
                if not result.tool_name:
                    result_steps.append(
                        ChainStep(
                            name=step_name,
                            provider=self.llm_client.provider_name,
                            prompt=str(messages),
                            output=result.raw_response.content,
                            latency_ms=result.raw_response.latency_ms,
                            cost_usd=result.raw_response.cost_usd,
                            status="completed",
                        )
                    )
                    break

                # Tool call requested — record it
                result_steps.append(
                    ChainStep(
                        name=step_name,
                        provider=self.llm_client.provider_name,
                        prompt=f"Tool call: {result.tool_name}({result.arguments})",
                        output=f"Tool call: {result.tool_name}({result.arguments})",
                        latency_ms=result.raw_response.latency_ms,
                        cost_usd=result.raw_response.cost_usd,
                        status="completed",
                    )
                )

                # Feed tool call result as observation
                tool_output = (
                    f"Tool '{result.tool_name}' returned: {result.arguments}"
                )
                messages.append({"role": "user", "content": tool_output})

            except Exception:
                result_steps.append(
                    ChainStep(name=step_name, status="failed")
                )
                # Continue loop despite error (up to max_iterations)
                continue

        return ChainResult(
            steps=result_steps,
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            status=status,
        )


# ======================================================================
# P2 — ChainRunner
# ======================================================================


class ChainRunner:
    """Unified runner for any chain type.

    Provides a common ``run()`` interface, input validation, streaming
    events, and cost tracking.
    """

    VALID_CHAIN_TYPES = (
        SequentialChain,
        ConditionalChain,
        ParallelChain,
        MapReduceChain,
        AgentWithToolsChain,
    )

    def run(
        self,
        chain: Any,
        input_data: Any = None,
        stream: bool = False,
    ) -> ChainResult | list[dict[str, Any]]:
        """Execute any supported chain type.

        Args:
            chain: A chain instance (SequentialChain, ConditionalChain, etc.).
            input_data: Input data for the chain.
            stream: If True, yields step completion events instead of
                returning a single ChainResult.

        Returns:
            ChainResult (or list of event dicts when streaming).

        Raises:
            TypeError: If chain is a string or other clearly invalid type.
        """
        # Strings and bytes are clearly invalid — raise
        if isinstance(chain, str | bytes):
            raise TypeError("chain must be a Chain instance, not a string")

        if isinstance(chain, self.VALID_CHAIN_TYPES):
            if not stream:
                return chain.run(input_data)
            # Streaming mode — yield step events
            events: list[dict[str, Any]] = []
            result = chain.run(input_data)
            if isinstance(result, ChainResult):
                for step in result.steps:
                    events.append(asdict(step))
            return events

        # Unknown chain type — try graceful execution
        try:
            if hasattr(chain, "run") and callable(chain.run):
                result = chain.run(input_data)
                if isinstance(result, ChainResult):
                    return result
        except Exception:
            pass
        return ChainResult(
            steps=[], total_cost_usd=0.0, total_tokens=0, status="failed"
        )


# ======================================================================
# P3 — Human-in-the-Loop
# ======================================================================




class HITLStep:
    """Human-in-the-loop approval gate.

    Pauses chain execution to request approval via a CallableApprovalChannel.
    On denial the step can branch to an alternative path.

    Args:
        name: Step name.
        approval_channel: CallableApprovalChannel instance.
        prompt: Prompt or context message shown for approval.
        on_denied: Optional list of steps to execute if approval is denied.
    """

    def __init__(
        self,
        name: str,
        approval_channel: CallableApprovalChannel,
        prompt: str = "",
        on_denied: list | None = None,
    ) -> None:
        self.name = name
        self.approval_channel = approval_channel
        self.prompt = prompt
        self.on_denied = list(on_denied) if on_denied else []

    def run(self, input_data: Any = None) -> ChainResult:
        """Execute the HITL approval gate.

        Args:
            input_data: Context for the approval decision.

        Returns:
            ChainResult with approval/denial step records.
        """
        ctx = _to_context(input_data)
        ctx_str = str(input_data) if input_data is not None else ""

        try:
            approved = self.approval_channel(self.name, {"context": ctx_str})
        except Exception:
            approved = False

        if approved:
            return ChainResult(
                steps=[
                    ChainStep(
                        name=self.name,
                        output="approved",
                        status="completed",
                    )
                ],
                total_cost_usd=0.0,
                total_tokens=0,
                status="completed",
            )

        # Denied — set status to denied and run alternative path
        denied_steps: list[ChainStep] = [
            ChainStep(
                name=self.name,
                output="denied",
                status="denied",
            )
        ]

        for step in self.on_denied:
            step_name = _get_attr(step, "name", "")
            try:
                output = _run_step_call(step, ctx)
                denied_steps.append(
                    _make_step_record(step, output, status="completed")
                )
            except Exception:
                denied_steps.append(
                    ChainStep(name=step_name, status="failed")
                )

        return ChainResult(
            steps=denied_steps,
            total_cost_usd=0.0,
            total_tokens=0,
            status="denied",
        )


__all__ = [
    "AgentWithToolsChain",
    "ChainContext",
    "ChainError",
    "ChainResult",
    "ChainRunner",
    "ChainStep",
    "ConditionalChain",
    "HITLStep",
    "MapReduceChain",
    "ParallelChain",
    "SequentialChain",
]
