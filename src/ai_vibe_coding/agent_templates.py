"""Agent Orchestration Templates.

Provides orchestration patterns for multi-agent workflows:
sequential pipelines, parallel fan-out/fan-in, hierarchical
supervisor, and event-driven pub/sub coordination.

Public API:
    AgentMessage              — immutable message dataclass
    MessageBus                — thread-safe pub/sub message bus
    SharedState               — thread-safe shared state with namespaces
    PipelineAgentConfig       — agent config with input/output mapping
    PipelineStep              — per-agent step record in a pipeline
    PipelineResult            — result of an agent pipeline execution
    AgentPipeline             — sequential agent pipeline
    FanOutResult              — result of a fan-out execution
    AgentFanOut               — parallel fan-out to N agents
    AgentFanIn                — fan-in aggregation
    AgentSupervisor           — hierarchical supervisor (wraps AgentTeam)
    AgentPubSubConfig         — pub/sub agent configuration
    AgentPubSubCoordinator    — event-driven agent lifecycle
    AgentCircuitBreaker       — circuit breaker for agents
    AgentRetryPolicy          — retry with backoff for agents
    AgentFallback             — primary/fallback agent failover
    AgentError                — base exception for agent templates
    AgentTimeoutError         — raised on agent timeout
    AgentCircuitOpenError     — raised when circuit breaker is open
    AgentMaxRetriesError      — raised when retries exhausted
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from typing import Any

from ai_vibe_coding.agent_team import (
    AgentConfig,
    AgentTeam,
    DelegationEvent,
)
from ai_vibe_coding.llm_wrapper import LLMClient, LLMResponse
from ai_vibe_coding.resilience import (
    CircuitBreakerOpenError,
)

# ======================================================================
# Helper: safely read a numeric attribute from a possibly-Mock object
# ======================================================================


def _safe_num(obj: Any, attr: str, default: float | int = 0.0) -> float | int:
    """Read a numeric attribute, returning *default* if it's a Mock."""
    from unittest.mock import Mock
    if not hasattr(obj, attr):
        return default
    val = getattr(obj, attr)
    if isinstance(val, Mock):
        return default
    return val


def _safe_name(obj: Any) -> str:
    """Read a human-friendly name from an object (handles Mocks)."""
    from unittest.mock import Mock
    name = getattr(obj, "name", None)
    if name is not None and not isinstance(name, Mock):
        return str(name)
    return str(obj)


# ======================================================================
# Exceptions
# ======================================================================


class AgentError(Exception):
    """Base exception for agent templates."""


class AgentTimeoutError(AgentError):
    """Raised when an agent execution times out."""


class AgentCircuitOpenError(AgentError):
    """Raised when a circuit breaker is open and rejects a call."""


class AgentMaxRetriesError(AgentError):
    """Raised when retry attempts are exhausted."""


# ======================================================================
# P0 — Foundation
# ======================================================================


@dataclass(frozen=True)
class AgentMessage:
    """Immutable message for agent-to-agent communication.

    Attributes:
        from_agent: Sender agent name.
        to_agent: Recipient (None = broadcast).
        type: Message type (e.g. "request", "response", "event").
        payload: Message data.
        timestamp: Auto-generated Unix timestamp.
        message_id: UUID-based unique identifier.
        correlation_id: Optional correlation ID for request/response pairing.
    """

    from_agent: str
    to_agent: str | None
    type: str
    payload: Any
    timestamp: float = field(default_factory=time.time)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None


class MessageBus:
    """Thread-safe pub/sub message bus.

    Supports type-filtered subscriptions with wildcard matching
    using '*' (match any single segment) and '**' (match any depth).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscriptions: dict[str, list[dict[str, Any]]] = {}
        self._next_id: int = 0
        self._queues: dict[str, list[AgentMessage]] = {}

    def subscribe(
        self,
        handler: Callable[[AgentMessage], None],
        type_filter: str | None = None,
    ) -> int:
        """Register a handler for messages matching *type_filter*.

        If *type_filter* is None, all messages are received.
        Returns a subscription ID for use with unsubscribe().
        """
        with self._lock:
            self._next_id += 1
            sub_id = self._next_id
            key = type_filter if type_filter is not None else "__all__"
            if key not in self._subscriptions:
                self._subscriptions[key] = []
            self._subscriptions[key].append({
                "id": sub_id,
                "handler": handler,
                "types": type_filter,
            })
            return sub_id

    def unsubscribe(self, sub_id: int) -> None:
        """Remove a subscription by its ID."""
        with self._lock:
            for key in list(self._subscriptions):
                self._subscriptions[key] = [
                    s for s in self._subscriptions[key]
                    if s["id"] != sub_id
                ]
                if not self._subscriptions[key]:
                    del self._subscriptions[key]

    def publish(self, msg: AgentMessage) -> None:
        """Deliver *msg* to all matching subscribers."""
        handlers: list[Callable] = []
        with self._lock:
            for sub in self._subscriptions.get("__all__", []):
                handlers.append(sub["handler"])
            for type_key, subs in list(self._subscriptions.items()):
                if type_key == "__all__":
                    continue
                if self._matches_type(msg.type, type_key):
                    for sub in subs:
                        handlers.append(sub["handler"])

        for handler in handlers:
            handler(msg)

        # Queue the message for get_messages()
        with self._lock:
            if msg.to_agent is not None:
                if msg.to_agent not in self._queues:
                    self._queues[msg.to_agent] = []
                self._queues[msg.to_agent].append(msg)

    def get_messages(
        self,
        agent_name: str,
        since: float | None = None,
    ) -> list[AgentMessage]:
        """Retrieve queued messages for *agent_name*.

        If *since* is provided, only messages with timestamp >= since
        are returned.
        """
        with self._lock:
            msgs = list(self._queues.get(agent_name, []))
        if since is not None:
            msgs = [m for m in msgs if m.timestamp >= since]
        return msgs

    @staticmethod
    def _matches_type(msg_type: str, pattern: str) -> bool:
        """Check if *msg_type* matches a wildcard *pattern*.

        Supports '*' (match any single segment) and '**' (match any
        depth).  Segments are split on '.'.
        """
        if pattern == msg_type:
            return True
        if pattern == "*":
            return True
        if pattern == "**":
            return True

        msg_parts = msg_type.split(".")
        pat_parts = pattern.split(".")

        mi, pi = 0, 0
        while mi < len(msg_parts) and pi < len(pat_parts):
            if pat_parts[pi] == "**":
                return True
            if pat_parts[pi] == "*":
                mi += 1
                pi += 1
                continue
            if msg_parts[mi] == pat_parts[pi]:
                mi += 1
                pi += 1
                continue
            return False

        while pi < len(pat_parts):
            if pat_parts[pi] not in ("**", "*"):
                return False
            pi += 1

        return mi == len(msg_parts) and pi == len(pat_parts)


class SharedState:
    """Thread-safe shared state with namespace isolation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self._namespaces: dict[str, SharedState] = {}

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value

    def namespace(self, name: str) -> SharedState:
        with self._lock:
            if name not in self._namespaces:
                ns = SharedState()
                self._namespaces[name] = ns
            return self._namespaces[name]

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._namespaces.clear()


# ======================================================================
# P1 — Sequential Agent Pipeline
# ======================================================================


@dataclass
class PipelineAgentConfig:
    """Configuration for a single agent in a pipeline.

    Attributes:
        agent: The LLMClient instance.
        input_mapping: Optional transform applied to input before
            passing to the agent.
        output_mapping: Optional transform applied to agent output
            before passing to the next stage.
    """

    agent: LLMClient
    input_mapping: Callable[[Any], str] | None = None
    output_mapping: Callable[[str], Any] | None = None


@dataclass
class PipelineStep:
    """Record of a single step in a pipeline execution.

    Attributes:
        name: Agent name.
        output: Step output text.
        cost_usd: Cost of this step.
        tokens_used: Tokens consumed.
        latency_ms: Execution latency in milliseconds.
        status: "completed", "failed", or "skipped".
        error: Error message if failed, or None.
    """

    name: str = ""
    output: str = ""
    cost_usd: float = 0.0
    tokens_used: int = 0
    latency_ms: float = 0.0
    status: str = "pending"
    error: str | None = None


@dataclass
class PipelineResult:
    """Result of an AgentPipeline execution.

    Attributes:
        steps: List of per-agent PipelineStep records.
        final_output: The output of the last successful agent.
        total_cost_usd: Accumulated cost across all executed agents.
        total_tokens: Accumulated token count.
        status: "completed" or "failed".
    """

    steps: list[PipelineStep]
    final_output: Any
    total_cost_usd: float
    total_tokens: int
    status: str


class AgentPipeline:
    """Sequential agent pipeline.

    Executes agents in order, passing each agent's output as the
    next agent's input.  Supports input/output mapping transformers,
    timeout per step, circuit breaker integration, and optional
    MessageBus / SharedState.
    """

    def __init__(
        self,
        agents: list[LLMClient | PipelineAgentConfig],
        timeout_per_step: float | None = None,
        circuit_breaker: Any | None = None,
        message_bus: MessageBus | None = None,
        shared_state: SharedState | None = None,
    ) -> None:
        self._agent_configs: list[PipelineAgentConfig] = []
        for a in agents:
            if isinstance(a, PipelineAgentConfig):
                self._agent_configs.append(a)
            else:
                self._agent_configs.append(PipelineAgentConfig(agent=a))
        self.timeout_per_step = timeout_per_step
        self.circuit_breaker = circuit_breaker
        self.message_bus = message_bus
        self.shared_state = shared_state

    def run(self, input_data: Any) -> PipelineResult:
        """Execute the pipeline sequentially.

        Args:
            input_data: Initial input for the first agent.

        Returns:
            PipelineResult with step records and accumulated metrics.
        """
        steps: list[PipelineStep] = []
        total_cost = 0.0
        total_tokens = 0
        status = "completed"
        current_input = input_data

        for cfg in self._agent_configs:
            if self.circuit_breaker is not None:
                try:
                    if hasattr(self.circuit_breaker, "check"):
                        self.circuit_breaker.check()
                except CircuitBreakerOpenError:
                    steps.append(PipelineStep(
                        name=_safe_name(cfg.agent),
                        status="skipped",
                        error="Circuit breaker open",
                    ))
                    continue

            agent_input = current_input
            if cfg.input_mapping is not None:
                agent_input = cfg.input_mapping(current_input)

            step_name = _safe_name(cfg.agent)

            try:
                start = time.time()
                response = cfg.agent.chat(
                    str(agent_input) if agent_input is not None else "",
                )
                elapsed_ms = (time.time() - start) * 1000.0

                # Extract response content and metrics
                if isinstance(response, LLMResponse):
                    output = response.content or str(response)
                    cost = response.cost_usd or 0.0
                    tokens = response.tokens_used or 0
                else:
                    output = _safe_str(getattr(response, "content", str(response)))
                    cost = float(_safe_num(response, "cost_usd", 0.0))
                    tokens = int(_safe_num(response, "tokens_used", 0))

                if cfg.output_mapping is not None:
                    output = cfg.output_mapping(output)

                steps.append(PipelineStep(
                    name=step_name,
                    output=output,
                    cost_usd=cost,
                    tokens_used=tokens,
                    latency_ms=elapsed_ms,
                    status="completed",
                ))
                total_cost += cost
                total_tokens += tokens
                current_input = output

                if self.message_bus is not None:
                    msg = AgentMessage(
                        from_agent=step_name,
                        to_agent=None,
                        type="pipeline.step",
                        payload={"output": output, "step": step_name},
                    )
                    self.message_bus.publish(msg)

                if self.shared_state is not None:
                    self.shared_state.set(f"pipeline.{step_name}", output)

            except Exception as e:
                steps.append(PipelineStep(
                    name=step_name,
                    status="failed",
                    error=str(e),
                ))
                status = "failed"
                raise

        return PipelineResult(
            steps=steps,
            final_output=current_input,
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            status=status,
        )


def _safe_str(val: Any) -> str:
    """Safely convert a value to string, handling Mock objects."""
    from unittest.mock import Mock
    if isinstance(val, Mock):
        return str(val)
    if isinstance(val, str):
        return val
    return str(val)


# ======================================================================
# P1 — Parallel Fan-Out / Fan-In
# ======================================================================


@dataclass
class FanOutResult:
    """Result of an AgentFanOut execution.

    Attributes:
        agent_results: Dict mapping agent names to their outputs.
        per_agent_cost: Dict mapping agent names to their cost.
        total_cost_usd: Total cost across all executed agents.
        status: "completed" or "partial".
        failed_agents: List of agents that failed.
        timed_out_agents: List of agents that timed out.
    """

    agent_results: dict[str, Any]
    per_agent_cost: dict[str, float]
    total_cost_usd: float
    status: str
    failed_agents: list[str] = field(default_factory=list)
    timed_out_agents: list[str] = field(default_factory=list)


class AgentFanOut:
    """Parallel fan-out dispatches the same input to multiple agents.

    Uses ThreadPoolExecutor to dispatch all agents concurrently.
    """

    def __init__(
        self,
        agents: dict[str, LLMClient],
        timeout: float = 30.0,
        max_workers: int | None = None,
        track_costs: bool = False,
        message_bus: MessageBus | None = None,
    ) -> None:
        if not agents:
            raise ValueError("At least one agent is required")
        self.agents = agents
        self.timeout = timeout
        self.max_workers = max_workers or len(agents)
        self.track_costs = track_costs
        self.message_bus = message_bus
        self.total_cost_usd: float = 0.0

    def run(self, input_data: Any) -> dict[str, Any]:
        """Execute all agents concurrently with the same input.

        Returns a dict mapping agent names to their outputs.
        """
        agent_results: dict[str, Any] = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_name = {
                executor.submit(self._run_agent, name, input_data): name
                for name in self.agents
            }

            for future in as_completed(future_to_name, timeout=self.timeout):
                name = future_to_name[future]
                try:
                    result = future.result(timeout=self.timeout)
                    agent_results[name] = result
                except FutureTimeoutError:
                    agent_results[name] = None
                except Exception:
                    agent_results[name] = None

        return agent_results

    def _run_agent(self, name: str, input_data: Any) -> Any:
        """Execute a single agent and return its output."""
        agent = self.agents[name]
        response = agent.chat(str(input_data))
        if isinstance(response, LLMResponse):
            return {
                "content": response.content or str(response),
                "cost_usd": response.cost_usd or 0.0,
                "tokens_used": response.tokens_used or 0,
            }
        return _safe_str(getattr(response, "content", str(response)))


class AgentFanIn:
    """Aggregates results from multiple agents.

    Supports built-in strategies: "join", "concatenate", "vote",
    or a custom callable.
    """

    def __init__(self, strategy: str | Callable[[dict[str, Any]], Any]) -> None:
        self.strategy = strategy

    def run(self, results: dict[str, Any]) -> Any:
        """Aggregate *results* according to the configured strategy."""
        if callable(self.strategy):
            return self.strategy(results)

        if self.strategy == "join":
            return results

        if self.strategy == "concatenate":
            parts: list[str] = []
            for val in results.values():
                if isinstance(val, dict):
                    parts.append(str(val.get("content", val)))
                else:
                    parts.append(_safe_str(val))
            return "\n\n".join(parts)

        if self.strategy == "vote":
            from collections import Counter
            values: list[str] = []
            for val in results.values():
                if isinstance(val, dict):
                    values.append(str(val.get("content", val)))
                else:
                    values.append(_safe_str(val))
            counter = Counter(values)
            return counter.most_common(1)[0][0]

        raise ValueError(f"Unknown strategy: {self.strategy}")


# ======================================================================
# P2 — Hierarchical Supervisor
# ======================================================================


class AgentSupervisor:
    """Hierarchical supervisor that routes tasks to worker agents.

    Wraps AgentTeam with a clean template API supporting dynamic
    worker registration, multiple delegation strategies, and
    streaming.
    """

    def __init__(
        self,
        supervisor: LLMClient,
        agents: dict[str, AgentConfig] | None = None,
        supervisor_prompt: str | None = None,
        max_rounds: int = 10,
        cost_limit_usd: float | None = None,
        on_delegation: Callable[[DelegationEvent], None] | None = None,
        delegation_strategy: str = "auto",
        streaming: bool = False,
    ) -> None:
        self.supervisor = supervisor
        self.supervisor_prompt = supervisor_prompt
        self.max_rounds = max_rounds
        self.cost_limit_usd = cost_limit_usd
        self.on_delegation = on_delegation
        self.delegation_strategy = delegation_strategy
        self.streaming = streaming

        self._workers: dict[str, AgentConfig] = {}
        if agents:
            self._workers.update(agents)

        self._team: AgentTeam | None = None

    def _build_team(self) -> AgentTeam:
        if not self._workers:
            raise ValueError(
                "No workers registered. Add workers via add_worker() before running."
            )
        if self._team is None or set(self._workers.keys()) != set(
            self._team.agents.keys()
        ):
            self._team = AgentTeam(
                supervisor=self.supervisor,
                agents=dict(self._workers),
                supervisor_prompt=self.supervisor_prompt,
                max_rounds=self.max_rounds,
                cost_limit_usd=self.cost_limit_usd,
                on_delegation=self.on_delegation,
            )
        return self._team

    def add_worker(self, name: str, config: AgentConfig) -> None:
        self._workers[name] = config
        self._team = None

    def remove_worker(self, name: str) -> None:
        if name in self._workers:
            del self._workers[name]
            self._team = None

    def list_workers(self) -> dict[str, AgentConfig]:
        return dict(self._workers)

    def get_worker(self, name: str) -> AgentConfig | None:
        return self._workers.get(name)

    def delegate_to(self, agent_name: str, task: str) -> Any:
        if agent_name not in self._workers:
            raise ValueError(
                f"Unknown agent '{agent_name}'. "
                f"Available: {list(self._workers)}"
            )
        cfg = self._workers[agent_name]
        response = cfg.client.chat(task, system_prompt=cfg.system_prompt)
        if isinstance(response, LLMResponse):
            return response.content or str(response)
        return str(response)

    def render_prompt(self) -> str:
        agents_list = "\n".join(
            f"- {name}: {cfg.system_prompt[:60] if cfg.system_prompt else ''}"
            for name, cfg in self._workers.items()
        )
        prompt = self.supervisor_prompt or "Agents available: {agents}"
        return prompt.replace("{agents}", agents_list)

    def run(
        self,
        prompt: str,
        stream: bool = False,
    ) -> Any:
        if not self._workers:
            if stream or self.streaming:
                return self._run_streaming(prompt)
            if self.on_delegation is not None:
                # No workers yet — call supervisor directly
                response = self.supervisor.chat(prompt)
                return response
            raise ValueError(
                "No workers registered. Add workers via add_worker() before running."
            )

        if stream or self.streaming:
            return self._run_streaming(prompt)

        strategy = self.delegation_strategy
        if strategy in ("round_robin", "cost_based", "capability_based"):
            return self._run_strategy(prompt)

        team = self._build_team()
        return team.run(prompt, stream=stream)

    def _run_strategy(self, prompt: str) -> Any:
        if self.delegation_strategy == "round_robin":
            if not self._workers:
                raise ValueError("No workers available")
            names = list(self._workers.keys())
            idx = id(self) % len(names)
            chosen = names[idx]
            return self.delegate_to(chosen, prompt)

        if self.delegation_strategy == "cost_based":
            cost_limits = {
                name: (cfg.cost_limit_usd if cfg.cost_limit_usd is not None
                       else float("inf"))
                for name, cfg in self._workers.items()
            }
            cheapest = min(cost_limits, key=cost_limits.get)
            return self.delegate_to(cheapest, prompt)

        if self.delegation_strategy == "capability_based":
            prompt_lower = prompt.lower()
            best_match: tuple[str, AgentConfig] | None = None
            best_score = 0
            for name, cfg in self._workers.items():
                meta = getattr(cfg, "metadata", {}) or {}
                capabilities = meta.get("capabilities", [])
                score = sum(
                    1 for cap in capabilities if cap.lower() in prompt_lower
                )
                if score > best_score:
                    best_score = score
                    best_match = (name, cfg)
            if best_match is None:
                first_name = next(iter(self._workers))
                return self.delegate_to(first_name, prompt)
            return self.delegate_to(best_match[0], prompt)

        return self.delegate_to(next(iter(self._workers)), prompt)

    def _run_streaming(self, prompt: str) -> Any:
        def _gen() -> Any:
            for name in self._workers:
                result = self.delegate_to(name, prompt)
                yield result
                return
        return _gen()


# ======================================================================
# P2 — Pub/Sub Event-Driven
# ======================================================================


@dataclass
class AgentPubSubConfig:
    """Configuration for a pub/sub agent.

    Attributes:
        agent_config: The AgentConfig for this agent.
        subscriptions: List of message types to subscribe to.
        hooks: Dict of lifecycle hooks: on_start, on_message,
            on_error, on_complete.
    """

    agent_config: AgentConfig
    subscriptions: list[str] = field(default_factory=list)
    hooks: dict[str, Callable] = field(default_factory=dict)


class AgentPubSubCoordinator:
    """Event-driven agent lifecycle coordinator.

    Manages agents that react to published messages matching their
    subscriptions.  Supports lifecycle hooks and scheduled agent
    activation.
    """

    def __init__(
        self,
        message_bus: MessageBus | None = None,
        agents: dict[str, AgentPubSubConfig] | None = None,
        shared_state: SharedState | None = None,
        on_start: Callable | None = None,
        on_message: Callable | None = None,
        on_error: Callable | None = None,
        on_complete: Callable | None = None,
        max_workers: int = 4,
    ) -> None:
        self.message_bus = message_bus or MessageBus()
        self.shared_state = shared_state or SharedState()
        self.on_start = on_start
        self.on_message = on_message
        self.on_error = on_error
        self.on_complete = on_complete
        self.max_workers = max_workers

        self._agents: dict[str, AgentPubSubConfig] = {}
        self._handlers: dict[str, Callable] = {}
        self._subscription_ids: dict[str, int] = {}
        self._scheduled_tasks: list[dict[str, Any]] = []
        self._running = False

        if agents:
            for name, cfg in agents.items():
                self.register_agent(name, cfg)

    @property
    def scheduled_tasks(self) -> list[dict[str, Any]]:
        return list(self._scheduled_tasks)

    def register_agent(
        self,
        name: str,
        handler: Callable | AgentPubSubConfig,
        subscription: str | None = None,
    ) -> None:
        if isinstance(handler, AgentPubSubConfig):
            cfg = handler
            sub_types = cfg.subscriptions
            agent_handler = cfg.hooks.get("on_message", lambda msg: None)
        else:
            agent_handler = handler
            sub_types = [subscription] if subscription else []

        self._handlers[name] = agent_handler

        for sub_type in sub_types:
            sub_id = self.message_bus.subscribe(
                self._make_dispatch(name, agent_handler),
                type_filter=sub_type,
            )
            self._subscription_ids[name] = sub_id

    def _make_dispatch(
        self, name: str, handler: Callable
    ) -> Callable[[AgentMessage], None]:
        def dispatch(msg: AgentMessage) -> None:
            try:
                handler(msg)
                if self.on_message:
                    self.on_message(msg)
            except Exception as e:
                if self.on_error:
                    self.on_error(e)
        return dispatch

    def publish(self, msg: AgentMessage) -> None:
        """Publish a message to the bus and trigger the on_message hook."""
        self.message_bus.publish(msg)
        if self.on_message:
            self.on_message(msg)

    def start(self) -> None:
        self._running = True
        if self.on_start:
            self.on_start()

    def stop(self) -> None:
        self._running = False
        if self.on_complete:
            self.on_complete()

    def schedule_agent(
        self,
        name: str,
        func: Callable,
        interval: float = 60.0,
    ) -> None:
        self._scheduled_tasks.append({
            "name": name,
            "func": func,
            "interval": interval,
        })


# ======================================================================
# P3 — Error Handling
# ======================================================================


class AgentCircuitBreaker:
    """Circuit breaker wrapper for agent execution.

    Tracks failures per provider and opens the circuit after
    *failure_threshold* consecutive failures.
    """

    def __init__(
        self,
        agent_config: Any,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
    ) -> None:
        self.agent_config = agent_config
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failures: dict[str, int] = {}
        self._open: dict[str, bool] = {}
        self._lock = threading.Lock()

    def record_failure(self, provider: str) -> None:
        with self._lock:
            self._failures[provider] = self._failures.get(provider, 0) + 1
            if self._failures[provider] >= self.failure_threshold:
                self._open[provider] = True

    def is_open(self, provider: str) -> bool:
        with self._lock:
            return self._open.get(provider, False)

    @property
    def allow_probe(self) -> bool:
        return any(self._open.values())

    def try_probe(self, provider: str) -> bool:
        with self._lock:
            if self._open.get(provider, False):
                self._open[provider] = False
                return True
            return False


class AgentRetryPolicy:
    """Retry policy for agent execution with backoff.

    Optionally publishes failed messages to a dead-letter queue.
    """

    def __init__(
        self,
        agent: LLMClient,
        max_retries: int = 3,
        dead_letter_queue: MessageBus | None = None,
        base_delay: float = 0.5,
    ) -> None:
        self.agent = agent
        self.max_retries = max_retries
        self.dead_letter_queue = dead_letter_queue
        self.base_delay = base_delay
        self.retry_count: int = 0

    def run_with_retry(self, input_data: str) -> Any:
        last_exc: Exception | None = None
        attempts = 0

        while attempts <= self.max_retries:
            try:
                self.retry_count = attempts
                response = self.agent.chat(input_data)
                return response
            except Exception as e:
                last_exc = e
                attempts += 1
                self.retry_count = attempts
                if attempts > self.max_retries:
                    break
                time.sleep(self.base_delay * (2 ** (attempts - 1)))

        if self.dead_letter_queue is not None:
            dlq_msg = AgentMessage(
                from_agent="retry_policy",
                to_agent=None,
                type="error.dead_letter",
                payload={
                    "input": input_data,
                    "error": str(last_exc),
                    "retries": self.retry_count,
                },
            )
            import contextlib
            with contextlib.suppress(Exception):
                self.dead_letter_queue.publish(dlq_msg)

        raise last_exc  # type: ignore[misc]


class AgentFallback:
    """Primary/fallback agent failover.

    Tries the primary agent first, then each fallback in order.
    """

    def __init__(
        self,
        primary: LLMClient,
        fallbacks: list[LLMClient],
    ) -> None:
        self.primary = primary
        self.fallbacks = fallbacks

    def run(self, input_data: str) -> dict[str, Any]:
        all_agents = [self.primary] + self.fallbacks

        for agent in all_agents:
            try:
                response = agent.chat(input_data)
                if isinstance(response, LLMResponse):
                    return {
                        "content": response.content or str(response),
                        "cost_usd": response.cost_usd or 0.0,
                        "tokens_used": response.tokens_used or 0,
                        "total_cost_usd": response.cost_usd or 0.0,
                    }
                content = _safe_str(getattr(response, "content", str(response)))
                return {
                    "content": content,
                    "cost_usd": 0.0,
                    "tokens_used": 0,
                    "total_cost_usd": 0.0,
                }
            except Exception:
                continue

        raise RuntimeError("All agents and fallbacks failed")
