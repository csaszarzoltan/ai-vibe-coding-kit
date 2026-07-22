"""AgentTeam: multi-agent orchestration with supervisor routing.

The supervisor receives a user prompt, decides which agent(s) to invoke
via a synthetic tool-call mechanism, and aggregates results.

Public API:
    AgentConfig          — configuration for a single agent
    AgentTeamResult      — result of an AgentTeam.run() invocation
    DelegationEvent      — one delegation event in the trace
    CostLimitExceededError — raised when cost limit is exceeded
    AgentTeam            — the orchestrator class
"""

from __future__ import annotations

import contextlib
import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from .llm_wrapper import LLMClient, LLMResponse

# ── Data classes ─────────────────────────────────────────────


@dataclass
class AgentConfig:
    """Configuration for a single agent in the team.

    Attributes:
        name: Human-readable agent name (must match routing keys).
        client: LLMClient instance for this agent.
        system_prompt: System prompt prepended to every agent call.
        tools: Optional list of tool definitions available to the agent.
        max_iterations: Max tool-call iterations per invocation.
        cost_limit_usd: Optional per-agent cost cap.
    """

    name: str
    client: LLMClient
    system_prompt: str
    tools: list[object] = field(default_factory=list)
    max_iterations: int = 10
    cost_limit_usd: float | None = None


@dataclass
class AgentTeamResult:
    """Result of an AgentTeam.run() invocation.

    Attributes:
        content: Final aggregated output text.
        supervisor_response: The last LLMResponse from the supervisor.
        agent_results: Per-agent outputs keyed by agent name.
        total_cost_usd: Sum of all costs (supervisor + agents).
        total_tokens: Sum of all tokens consumed.
        delegation_trace: Ordered list of DelegationEvent objects.
    """

    content: str
    supervisor_response: LLMResponse
    agent_results: dict[str, object]
    total_cost_usd: float
    total_tokens: int
    delegation_trace: list[object]


class DelegationEvent:
    """One delegation event in the trace.

    Attributes:
        timestamp: Unix timestamp when the delegation occurred.
        from_agent: Name of the delegating entity (usually "supervisor").
        to_agent: Name of the agent that was delegated to.
        task_description: What was asked of the agent.
        result_preview: First 200 chars of the agent's response.
    """

    def __init__(
        self,
        timestamp: float,
        from_agent: str,
        to_agent: str,
        task_description: str,
        result_preview: str,
    ) -> None:
        self.timestamp = timestamp
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.task_description = task_description
        self.result_preview = result_preview


class CostLimitExceededError(Exception):
    """Raised when team or agent cost limit is exceeded.

    Attributes:
        current_cost: The cost at the time of the violation.
        limit: The configured limit.
        agent_name: Which agent exceeded (None = team-level).
    """

    def __init__(
        self,
        current_cost: float,
        limit: float,
        agent_name: str | None = None,
    ) -> None:
        self.current_cost = current_cost
        self.limit = limit
        self.agent_name = agent_name
        scope = f"agent '{agent_name}'" if agent_name else "team"
        super().__init__(
            f"{scope} cost limit ${limit:.4f} exceeded "
            f"(current: ${current_cost:.4f})"
        )


# ── Default supervisor prompt ────────────────────────────────

_DEFAULT_SUPERVISOR_PROMPT = (
    "You are a supervisor that routes user requests to specialized agents.\n"
    "Available agents:\n{agents}\n\n"
    "To delegate a task, respond with a JSON object:\n"
    '  {{"delegate": {{"agent": "<name>", "task": "<description>"}}}}\n'
    "To respond directly without delegation, respond with:\n"
    '  {{"respond": "<your answer>"}}\n'
    "You may delegate multiple times in sequence if needed."
)

# ── AgentTeam ────────────────────────────────────────────────


class AgentTeam:
    """Multi-agent orchestration with supervisor routing.

    The supervisor receives a user prompt, decides which agent(s) to invoke
    via a synthetic tool-call mechanism, and aggregates results.

    Example::

        team = AgentTeam(
            supervisor=LLMClient("openai"),
            agents={
                "research": AgentConfig(
                    name="research",
                    client=LLMClient("anthropic"),
                    system_prompt="You are a research assistant.",
                ),
            },
        )
        result = team.run("Summarize the latest AI papers")
    """

    def __init__(
        self,
        supervisor: LLMClient,
        agents: dict[str, AgentConfig],
        supervisor_prompt: str | None = None,
        max_rounds: int = 10,
        cost_limit_usd: float | None = None,
        on_delegation: Callable[[DelegationEvent], None] | None = None,
    ) -> None:
        """Initialize AgentTeam with supervisor and agent configurations.

        Args:
            supervisor: LLMClient used for routing decisions.
            agents: Dict mapping agent names to their AgentConfig.
            supervisor_prompt: Custom supervisor prompt template.
                Must contain ``{agents}`` placeholder.
            max_rounds: Maximum supervisor reasoning rounds.
            cost_limit_usd: Team-level cost cap.
            on_delegation: Optional callback for each delegation event.

        Raises:
            ValueError: If agents dict is empty.
        """
        if not agents:
            raise ValueError("AgentTeam requires at least one agent")

        self.supervisor = supervisor
        self.agents = agents
        self.supervisor_prompt = supervisor_prompt or _DEFAULT_SUPERVISOR_PROMPT
        self.max_rounds = max_rounds
        self.cost_limit_usd = cost_limit_usd
        self.on_delegation = on_delegation

        # Internal tracking state
        self._cost_total: float = 0.0
        self._tokens_total: int = 0
        self._agent_costs: dict[str, float] = {}
        self._agent_histories: dict[str, list[dict[str, str]]] = {
            name: [] for name in agents
        }

    # ── Public API ───────────────────────────────────────────

    def run(
        self,
        prompt: str,
        *,
        stream: bool = False,
    ) -> AgentTeamResult | Iterator[str]:
        """Execute the multi-agent workflow.

        Args:
            prompt: User's request.
            stream: If True, yield supervisor tokens instead of returning
                AgentTeamResult.

        Returns:
            AgentTeamResult when stream=False, Iterator[str] when stream=True.

        Raises:
            CostLimitExceededError: If team cost limit is exceeded.
            ValueError: If the supervisor routes to an unknown agent.
        """
        if stream:
            return self._run_streaming(prompt)

        agent_results: dict[str, object] = {}
        delegation_trace: list[DelegationEvent] = []
        supervisor_response: LLMResponse | None = None

        supervisor_sys = self._build_supervisor_prompt()
        messages: list[dict[str, str]] = [
            {"role": "system", "content": supervisor_sys},
            {"role": "user", "content": prompt},
        ]

        for _round in range(self.max_rounds):
            current_prompt = prompt if _round == 0 else messages[-1]["content"]
            response = self.supervisor.chat(
                current_prompt,
                system_prompt=supervisor_sys,
            )
            supervisor_response = response
            self._record_cost(response, "supervisor")

            action = self._parse_supervisor_response(response.content)

            if action is None:
                # Unparseable response — treat as direct answer
                break

            if "respond" in action:
                # Supervisor chose to respond directly
                break

            if "delegate" in action:
                delegation = action["delegate"]
                agent_name = delegation.get("agent", "")
                task = delegation.get("task", "")

                if agent_name not in self.agents:
                    raise ValueError(
                        f"Unknown agent '{agent_name}'. "
                        f"Available: {list(self.agents)}"
                    )

                # Dispatch to the agent
                agent_output = self._dispatch_to_agent(
                    agent_name, task, prompt
                )

                agent_results[agent_name] = agent_output

                # Record delegation event
                preview = (
                    agent_output[:200]
                    if isinstance(agent_output, str)
                    else str(agent_output)[:200]
                )
                event = DelegationEvent(
                    timestamp=time.time(),
                    from_agent="supervisor",
                    to_agent=agent_name,
                    task_description=task,
                    result_preview=preview,
                )
                delegation_trace.append(event)
                if self.on_delegation:
                    self.on_delegation(event)

                # Feed result back to supervisor for next round
                messages.append(
                    {"role": "assistant", "content": response.content}
                )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Agent '{agent_name}' responded:\n"
                            f"{agent_output}\n\n"
                            f"Continue or provide final answer."
                        ),
                    }
                )

        assert supervisor_response is not None, "supervisor never responded"
        final_content = (
            supervisor_response.content
            if not agent_results
            else self._aggregate_results(
                supervisor_response.content, agent_results
            )
        )

        return AgentTeamResult(
            content=final_content,
            supervisor_response=supervisor_response,
            agent_results=agent_results,
            total_cost_usd=self._cost_total,
            total_tokens=self._tokens_total,
            delegation_trace=delegation_trace,
        )

    # ── Internal methods ─────────────────────────────────────

    def _dispatch_to_agent(
        self,
        agent_name: str,
        task: str,
        original_prompt: str,
    ) -> str:
        """Run a single agent with a task and return its text response.

        Each agent gets its own conversation context (history isolation).
        Raises NotImplementedError if the agent's client is not configured.

        Args:
            agent_name: Key into self.agents.
            task: The specific task delegated by the supervisor.
            original_prompt: The user's original request for context.

        Returns:
            The agent's text response.

        Raises:
            NotImplementedError: If agent client is not a usable LLMClient.
            CostLimitExceededError: If agent cost limit is exceeded.
        """
        config = self.agents[agent_name]

        # Validate agent has a usable client
        client = getattr(config, "client", None)
        if client is None:
            raise NotImplementedError(
                f"Agent '{agent_name}' has no client configured"
            )

        # Check per-agent cost limit
        cost_limit = getattr(config, "cost_limit_usd", None)
        if cost_limit is not None:
            current = self._agent_costs.get(agent_name, 0.0)
            if current >= cost_limit:
                raise CostLimitExceededError(
                    current_cost=current,
                    limit=cost_limit,
                    agent_name=agent_name,
                )

        # Build isolated context for this agent
        user_msg = (
            f"Original request: {original_prompt}\n\n"
            f"Your task: {task}"
        )

        system_prompt = getattr(config, "system_prompt", "")

        response = client.chat(user_msg, system_prompt=system_prompt)

        self._record_cost(response, agent_name)

        # Update agent's isolated history
        if agent_name not in self._agent_histories:
            self._agent_histories[agent_name] = []
        self._agent_histories[agent_name].append(
            {"role": "user", "content": user_msg}
        )
        self._agent_histories[agent_name].append(
            {"role": "assistant", "content": response.content}
        )

        return response.content

    def _build_supervisor_prompt(self) -> str:
        """Inject agent manifest into supervisor prompt template.

        Returns:
            The formatted supervisor system prompt.
        """
        agent_lines: list[str] = []
        for name, config in self.agents.items():
            tools = getattr(config, "tools", [])
            sys_prompt = getattr(config, "system_prompt", "")
            tools_desc = f", tools={len(tools)}" if tools else ""
            agent_lines.append(
                f"  - {name}: {sys_prompt[:100]}...{tools_desc}"
            )
        agents_manifest = "\n".join(agent_lines)
        return self.supervisor_prompt.format(agents=agents_manifest)

    def _run_streaming(self, prompt: str) -> Iterator[str]:
        """Execute in streaming mode, yielding supervisor tokens.

        Args:
            prompt: User's request.

        Yields:
            Text chunks from the supervisor.
        """
        supervisor_sys = self._build_supervisor_prompt()
        yield from self.supervisor.stream(
            prompt, system_prompt=supervisor_sys
        )

    # ── Helpers ───────────────────────────────────────────────

    def _record_cost(
        self, response: LLMResponse, agent_name: str
    ) -> None:
        """Accumulate cost and token tracking.

        Safely handles mock or missing response attributes.
        """
        cost = getattr(response, "cost_usd", 0.0)
        tokens = getattr(response, "tokens_used", 0)

        with contextlib.suppress(TypeError, ValueError):
            self._cost_total += float(cost)

        with contextlib.suppress(TypeError, ValueError):
            self._tokens_total += int(tokens)

        with contextlib.suppress(TypeError, ValueError):
            prev = self._agent_costs.get(agent_name, 0.0)
            self._agent_costs[agent_name] = prev + float(cost)

        # Check team-level cost limit
        if (
            self.cost_limit_usd is not None
            and self._cost_total >= self.cost_limit_usd
        ):
            raise CostLimitExceededError(
                current_cost=self._cost_total,
                limit=self.cost_limit_usd,
            )

    @staticmethod
    def _parse_supervisor_response(
        content: str,
    ) -> dict[str, Any] | None:
        """Parse the supervisor's JSON response.

        Args:
            content: Raw text from the supervisor.

        Returns:
            Parsed dict if JSON was found, None otherwise.
        """
        content_stripped = content.strip()

        # Direct JSON
        if content_stripped.startswith("{"):
            try:
                return json.loads(content_stripped)
            except json.JSONDecodeError:
                pass

        # JSON inside a code block
        if "```" in content_stripped:
            parts = content_stripped.split("```")
            for part in parts[1::2]:
                cleaned = part.strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
                if cleaned.startswith("{"):
                    try:
                        return json.loads(cleaned)
                    except json.JSONDecodeError:
                        continue

        return None

    @staticmethod
    def _aggregate_results(
        supervisor_text: str, agent_results: dict[str, object]
    ) -> str:
        """Combine supervisor text with agent outputs.

        Args:
            supervisor_text: The supervisor's final text.
            agent_results: Per-agent outputs.

        Returns:
            Aggregated text string.
        """
        parts = [supervisor_text]
        for name, output in agent_results.items():
            parts.append(f"\n--- {name} ---\n{output}")
        return "\n".join(parts)
