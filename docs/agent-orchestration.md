# Agent Orchestration Templates

Module: `src/ai_vibe_coding/agent_templates.py`  
Backbone: `src/ai_vibe_coding/agent_team.py` (AgentTeam supervisor)  
Imported via: `from ai_vibe_coding import AgentPipeline, AgentFanOut, AgentFanIn, AgentSupervisor, AgentPubSubCoordinator, MessageBus, SharedState, ...`

## Overview

Agent orchestration lets you compose multiple LLM-powered agents into coordinated
workflows. A single LLM call handles one-shot questions; orchestration handles
multi-step, multi-agent processes where different specialists contribute to a
unified result.

### When to use what

| Approach | When to use | Example |
|----------|-------------|---------|
| **Single LLM call** | One-shot Q&A, simple generation | "Summarize this text" |
| **Sequential pipeline** | Fixed N steps, each feeds the next | Research → Write → Review |
| **Parallel fan-out/fan-in** | Same input, multiple perspectives | Technical + Business + Security analysis |
| **Hierarchical supervisor** | LLM-based routing to specialists | Code dev → review → test |
| **Pub/sub event-driven** | Agents react to events asynchronously | Sensor → Analyzer → Alerter |

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              AGENT ORCHESTRATION LAYER                      │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │Sequential│  │Parallel  │  │Supervisor│  │ Pub/Sub    │  │
│  │Pipeline  │  │FanOut/Fan│  │Hierarchy │  │ Coordinator│  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬──────┘  │
│       │             │             │              │          │
│       └─────────────┴─────────────┴──────────────┘          │
│                            │                                │
│                    ┌───────┴────────┐                       │
│                    │ Foundation     │                       │
│                    │  MessageBus    │                       │
│                    │  SharedState   │                       │
│                    └───────┬────────┘                       │
│                            │                                │
│                    ┌───────┴────────┐                       │
│                    │ Error Handling │                       │
│                    │  CircuitBreaker│                       │
│                    │  RetryPolicy   │                       │
│                    │  AgentFallback │                       │
│                    └────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

## Foundation — MessageBus & SharedState

Every orchestration pattern builds on two shared primitives.

### MessageBus

A thread-safe publish/subscribe message bus for agent-to-agent communication.
Supports type-filtered subscriptions with wildcard matching (`*` = single
segment, `**` = any depth).

```python
from ai_vibe_coding import AgentMessage, MessageBus

bus = MessageBus()

# Subscribe to all "sensor.*" messages
def sensor_handler(msg: AgentMessage) -> None:
    print(f"Sensor event: {msg.payload}")

sub_id = bus.subscribe(sensor_handler, type_filter="sensor.*")

# Publish a message
msg = AgentMessage(
    from_agent="cpu_monitor",
    to_agent=None,          # None = broadcast
    type="sensor.cpu",
    payload={"source": "server-1", "value": 85},
)
bus.publish(msg)

# Unsubscribe when done
bus.unsubscribe(sub_id)
```

Key features:
- **`subscribe(handler, type_filter=None)`** — register a handler. Returns a
  subscription ID. `type_filter=None` matches all messages.
- **`unsubscribe(sub_id)`** — remove a subscription.
- **`publish(msg)`** — deliver to all matching subscribers and queue the message
  for the recipient.
- **`get_messages(agent_name, since=None)`** — retrieve queued messages for a
  named agent.
- Wildcard patterns: `"sensor.*"` matches `"sensor.cpu"`, `"sensor.temp"`.
  `"**"` matches everything.

### SharedState

A thread-safe shared key-value store with namespace isolation.

```python
from ai_vibe_coding import SharedState

state = SharedState()

# Set and get values
state.set("project", "ai-vibe-coding-kit")
print(state.get("project"))  # "ai-vibe-coding-kit"

# Namespace isolation
work_ns = state.namespace("workflow")
work_ns.set("status", "running")
print(state.get("project"))          # "ai-vibe-coding-kit"
print(work_ns.get("status"))         # "running"
print(state.namespace("workflow").get("status"))  # "running"

state.clear()  # reset everything
```

Key features:
- **`get(key, default=None)`** — thread-safe read.
- **`set(key, value)`** — thread-safe write.
- **`namespace(name)`** — returns an isolated sub-scope.
- **`clear()`** — reset all data.

---

## Pattern 1 — Sequential Pipeline

Use when you have a fixed sequence of steps where each agent's output becomes
the next agent's input. Classic example: research → writer → reviewer.

### Code example

```python
from ai_vibe_coding import AgentPipeline, PipelineResult
from ai_vibe_coding.llm_wrapper import LLMClient

# 1. Create LLM clients for each step
research_agent = LLMClient(provider="openai", model="gpt-4o-mini")
writer_agent = LLMClient(provider="anthropic", model="claude-3-haiku-20240307")
reviewer_agent = LLMClient(provider="deepseek", model="deepseek-chat")

# 2. Build the pipeline
pipeline = AgentPipeline(
    agents=[research_agent, writer_agent, reviewer_agent],
)

# 3. Run
result: PipelineResult = pipeline.run(
    input_data="The impact of quantum computing on cryptography"
)
print(f"Status: {result.status}")
print(f"Final output:\n{result.final_output}")
print(f"Total cost: ${result.total_cost_usd:.4f}")
print(f"Total tokens: {result.total_tokens}")
for step in result.steps:
    print(f"  {step.name}: {step.status} ({step.latency_ms:.0f}ms, ${step.cost_usd:.4f})")
```

### Pipeline with input/output transforms

```python
from ai_vibe_coding import AgentPipeline, PipelineAgentConfig

def shorten(text):
    return f"Summarize in one sentence: {text}"

def expand(text):
    return f"Now expand this into a paragraph: {text}"

pipeline = AgentPipeline(
    agents=[
        PipelineAgentConfig(agent=research_agent, input_mapping=shorten),
        PipelineAgentConfig(agent=writer_agent, output_mapping=expand),
    ],
    timeout_per_step=30.0,
)
```

### When to use a pipeline

- Content generation with distinct review phases
- Data processing: extract → transform → load
- Multi-pass analysis where each pass needs the previous result

### Architecture diagram

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Agent A │────▶│  Agent B │────▶│  Agent C │
│ (Research)│    │  (Write) │    │ (Review) │
└──────────┘     └──────────┘     └──────────┘
      │                │                │
      │  output A      │  output B      │  final output
      ▼                ▼                ▼
  input_data ───▶ AgentPipeline.run(input_data) ───▶ PipelineResult
```

### API reference

```python
class AgentPipeline:
    def __init__(
        self,
        agents: list[LLMClient | PipelineAgentConfig],
        timeout_per_step: float | None = None,
        circuit_breaker: Any | None = None,
        message_bus: MessageBus | None = None,
        shared_state: SharedState | None = None,
    ) -> None: ...

    def run(self, input_data: Any) -> PipelineResult: ...
```

`PipelineAgentConfig` fields:
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `agent` | `LLMClient` | (required) | The LLM client for this step |
| `input_mapping` | `Callable[[Any], str]` | `None` | Transform input before passing to agent |
| `output_mapping` | `Callable[[str], Any]` | `None` | Transform output before passing to next |

`PipelineResult` fields:
| Field | Type | Description |
|-------|------|-------------|
| `steps` | `list[PipelineStep]` | Per-agent step records |
| `final_output` | `Any` | Output of the last successful agent |
| `total_cost_usd` | `float` | Accumulated cost |
| `total_tokens` | `int` | Accumulated tokens |
| `status` | `"completed" \| "failed"` | Overall execution status |

`PipelineStep` fields:
| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Agent name |
| `output` | `str` | Step output text |
| `cost_usd` | `float` | Cost of this step |
| `tokens_used` | `int` | Tokens consumed |
| `latency_ms` | `float` | Execution latency in ms |
| `status` | `"completed" \| "failed" \| "skipped"` | Step status |
| `error` | `str \| None` | Error message if failed |

---

## Pattern 2 — Parallel Fan-Out / Fan-In

Use when you need multiple perspectives on the same input simultaneously.
Fan-out dispatches the input to N agents concurrently; fan-in aggregates
their results.

### Code example

```python
from ai_vibe_coding import AgentFanIn, AgentFanOut
from ai_vibe_coding.llm_wrapper import LLMClient

# 1. Create specialist agents
tech_agent = LLMClient(provider="openai", model="gpt-4o-mini")
biz_agent = LLMClient(provider="anthropic", model="claude-3-haiku-20240307")
sec_agent = LLMClient(provider="deepseek", model="deepseek-chat")

# 2. Fan out — same input to all agents in parallel
fanout = AgentFanOut(
    agents={
        "Technical": tech_agent,
        "Business": biz_agent,
        "Security": sec_agent,
    },
    timeout=30.0,
)

topic = "Adopting a polyglot microservices architecture"
results = fanout.run(input_data=topic)
for name, output in results.items():
    print(f"  [{name}] {str(output)[:100]}...")

# 3. Fan in — aggregate results
fanin = AgentFanIn(strategy="join")
aggregated = fanin.run(results=results)
```

### Aggregation strategies

| Strategy | Behavior |
|----------|----------|
| `"concatenate"` | Join all outputs with `\n\n` separators |
| `"join"` | Return the raw dict of per-agent results |
| `"vote"` | Return the most common output value (majority vote) |
| `callable` | Custom function: `def my_aggregator(results: dict[str, Any]) -> Any` |

### When to use fan-out/fan-in

- Multi-perspective analysis (technical + business + security)
- Ensemble generation (multiple drafts, pick best)
- Parallel validation (run N checks simultaneously)

### Architecture diagram

```
                   input_data
                       │
         ┌─────────────┼─────────────┐
         │             │             │
    ┌────▼────┐  ┌────▼────┐  ┌────▼────┐
    │ Agent A │  │ Agent B │  │ Agent C │
    │  (Tech) │  │  (Biz)  │  │  (Sec)  │
    └────┬────┘  └────┬────┘  └────┬────┘
         │             │             │
         └─────────────┼─────────────┘
                       │
                  ┌────▼────┐
                  │  FanIn  │
                  │ (aggregate)│
                  └─────────┘
```

### API reference

```python
class AgentFanOut:
    def __init__(
        self,
        agents: dict[str, LLMClient],
        timeout: float = 30.0,
        max_workers: int | None = None,
        track_costs: bool = False,
        message_bus: MessageBus | None = None,
    ) -> None: ...

    def run(self, input_data: Any) -> dict[str, Any]: ...

class AgentFanIn:
    def __init__(
        self,
        strategy: str | Callable[[dict[str, Any]], Any],
    ) -> None: ...

    def run(self, results: dict[str, Any]) -> Any: ...
```

---

## Pattern 3 — Hierarchical Supervisor

Use when you need an LLM to decide which specialist agent to call, possibly
multiple times in sequence. The supervisor acts as a router, parsing the
user request and delegating subtasks to registered workers.

### Code example

```python
from ai_vibe_coding import AgentSupervisor
from ai_vibe_coding.agent_team import AgentConfig, AgentTeamResult
from ai_vibe_coding.llm_wrapper import LLMClient

# 1. Supervisor client (routes the work)
supervisor_client = LLMClient(provider="openai", model="gpt-4o-mini")

# 2. Worker agents
dev_client = LLMClient(provider="anthropic", model="claude-3-haiku-20240307")
review_client = LLMClient(provider="deepseek", model="deepseek-chat")
test_client = LLMClient(provider="openai", model="gpt-4o-mini")

# 3. Configure workers with system prompts
agent_cfg = {
    "developer": AgentConfig(
        name="developer",
        client=dev_client,
        system_prompt="You are a senior Python developer. Write clean, "
        "well-documented code.",
    ),
    "reviewer": AgentConfig(
        name="reviewer",
        client=review_client,
        system_prompt="You are a code reviewer. Find bugs, style issues, "
        "and security flaws.",
    ),
    "tester": AgentConfig(
        name="tester",
        client=test_client,
        system_prompt="You are a QA engineer. Write comprehensive tests "
        "for the given code.",
    ),
}

def on_delegation(event):
    print(f"  Delegated to {event.to_agent}: {event.task_description[:60]}...")

# 4. Build supervisor
supervisor = AgentSupervisor(
    supervisor=supervisor_client,
    agents=agent_cfg,
    cost_limit_usd=0.05,
    on_delegation=on_delegation,
)

# 5. Run
task = "Write a Python function that validates email addresses"
result = supervisor.run(task)
```

### Delegation strategies

| Strategy | Behavior |
|----------|----------|
| `"auto"` (default) | LLM-based routing — supervisor decides via JSON tool calls |
| `"round_robin"` | Cycle through workers in order |
| `"cost_based"` | Pick the worker with the lowest `cost_limit_usd` |
| `"capability_based"` | Match worker metadata `capabilities` to prompt keywords |

### Dynamic worker management

```python
# Add or remove workers at runtime
supervisor.add_worker("security_auditor", AgentConfig(...))
supervisor.remove_worker("reviewer")

# List all registered workers
workers = supervisor.list_workers()

# Direct delegation (bypass supervisor)
output = supervisor.delegate_to("developer", "Write a sort function")
```

### When to use a hierarchical supervisor

- Complex tasks requiring multiple specialist skills
- Workflows where the sequence of steps isn't predetermined
- When you want an LLM to decide delegation strategy dynamically
- Code review pipelines, content moderation, multi-step QA

### Architecture diagram

```
                   user prompt
                       │
               ┌───────▼────────┐
               │   Supervisor   │
               │  (LLM Router)  │
               └───┬───┬───┬───┘
                   │   │   │
        ┌──────────┘   │   └──────────┐
        │              │              │
   ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
   │Developer│   │Reviewer │   │ Tester  │
   │  (code) │   │ (review)│   │  (test) │
   └────┬────┘   └────┬────┘   └────┬────┘
        │              │              │
        └──────────────┼──────────────┘
                       │
               ┌───────▼────────┐
               │  Aggregated    │
               │    Result      │
               └────────────────┘
```

### API reference

```python
class AgentSupervisor:
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
    ) -> None: ...

    def add_worker(self, name: str, config: AgentConfig) -> None: ...
    def remove_worker(self, name: str) -> None: ...
    def list_workers(self) -> dict[str, AgentConfig]: ...
    def get_worker(self, name: str) -> AgentConfig | None: ...
    def delegate_to(self, agent_name: str, task: str) -> Any: ...
    def render_prompt(self) -> str: ...
    def run(self, prompt: str, stream: bool = False) -> Any: ...
```

`AgentConfig` fields:
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | (required) | Agent name, must match routing keys |
| `client` | `LLMClient` | (required) | The LLM client for this agent |
| `system_prompt` | `str` | (required) | System prompt for this agent |
| `tools` | `list[object]` | `[]` | Tool definitions available to the agent |
| `max_iterations` | `int` | `10` | Max tool-call iterations per invocation |
| `cost_limit_usd` | `float\|None` | `None` | Optional per-agent cost cap |

---

## Pattern 4 — Pub/Sub Event-Driven

Use when agents should react to events asynchronously. The
`AgentPubSubCoordinator` manages agent lifecycles around a `MessageBus`,
triggering agents when messages matching their subscriptions arrive.

### Code example

```python
from ai_vibe_coding import (
    AgentMessage,
    AgentPubSubCoordinator,
    MessageBus,
)

bus = MessageBus()
coordinator = AgentPubSubCoordinator(message_bus=bus)

# Collect results for verification
sensor_events = []
alert_events = []

def sensor_handler(msg: AgentMessage) -> None:
    sensor_events.append(msg)
    bus.publish(AgentMessage(
        from_agent="sensor",
        to_agent=None,
        type="log.info",
        payload=msg.payload,
    ))

def analyzer_handler(msg: AgentMessage) -> None:
    # Detect anomalies — publish alert if value > 80
    if msg.payload.get("value", 0) > 80:
        bus.publish(AgentMessage(
            from_agent="analyzer",
            to_agent=None,
            type="alert.critical",
            payload={
                "source": msg.payload.get("source", "unknown"),
                "value": msg.payload.get("value", 0),
            },
        ))

def alerter_handler(msg: AgentMessage) -> None:
    alert_events.append(msg)

# Register agents with topic subscriptions
coordinator.register_agent("sensor", sensor_handler,
                           subscription="sensor.*")
coordinator.register_agent("analyzer", analyzer_handler,
                           subscription="log.*")
coordinator.register_agent("alerter", alerter_handler,
                           subscription="alert.*")

coordinator.start()

# Simulate sensor events
for i in range(5):
    msg = AgentMessage(
        from_agent="sensor",
        to_agent=None,
        type="sensor.cpu",
        payload={"source": f"server-{i}", "value": 50 + i * 15},
    )
    bus.publish(msg)

coordinator.stop()
```

### Using AgentPubSubConfig (structured config)

```python
from ai_vibe_coding import AgentPubSubConfig
from ai_vibe_coding.agent_team import AgentConfig

pubsub_config = {
    "sensor": AgentPubSubConfig(
        agent_config=AgentConfig(
            name="sensor",
            client=LLMClient(provider="openai"),
            system_prompt="You are a sensor monitor.",
        ),
        subscriptions=["sensor.*"],
        hooks={
            "on_message": sensor_handler,
            "on_error": lambda e: print(f"Error: {e}"),
        },
    ),
}
coordinator = AgentPubSubCoordinator(agents=pubsub_config)
```

### Lifecycle hooks

| Hook | Called when | Signature |
|------|-------------|-----------|
| `on_start` | `coordinator.start()` | `() -> None` |
| `on_message` | Any message published | `(AgentMessage) -> None` |
| `on_error` | Handler raises an exception | `(Exception) -> None` |
| `on_complete` | `coordinator.stop()` | `() -> None` |

### Scheduled agent activation

```python
def daily_report():
    bus.publish(AgentMessage(
        from_agent="reporter",
        to_agent=None,
        type="report.daily",
        payload={"date": "2026-07-28"},
    ))

coordinator.schedule_agent(name="daily_reporter",
                           func=daily_report,
                           interval=3600.0)  # every hour
```

### When to use pub/sub

- Monitoring pipelines (sensor → analyzer → alerter)
- Event-driven microservice workflows
- Asynchronous multi-step processing
- Systems where agents need to react to external events

### Architecture diagram

```
          ┌───────────── MessageBus ─────────────┐
          │                                       │
    ┌─────▼──────┐                    ┌───────────▼───┐
    │  Sensor    │  "sensor.cpu"     │   Analyzer    │
    │ Agent      │──────────────────▶│   Agent       │
    │            │                    │               │
    └────────────┘                    └───────┬───────┘
                                              │ "alert.critical"
                                              │
                                         ┌────▼────┐
                                         │ Alerter │
                                         │ Agent   │
                                         └─────────┘

    AgentPubSubCoordinator.start()
    ├── Registers agents with MessageBus subscriptions
    ├── Starts lifecycle hooks
    └── Agents react when matching messages arrive
```

### API reference

```python
class AgentPubSubCoordinator:
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
    ) -> None: ...

    def register_agent(
        self,
        name: str,
        handler: Callable | AgentPubSubConfig,
        subscription: str | None = None,
    ) -> None: ...

    def publish(self, msg: AgentMessage) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def schedule_agent(self, name: str, func: Callable,
                       interval: float = 60.0) -> None: ...
    @property
    def scheduled_tasks(self) -> list[dict[str, Any]]: ...
```

---

## Multi-Provider Configuration

Every orchestration pattern supports heterogeneous providers — each agent can
use a different LLM provider for its specific task.

### Pipeline with 3 providers

```python
research_agent = LLMClient(provider="openai", model="gpt-4o-mini")
writer_agent   = LLMClient(provider="anthropic", model="claude-3-haiku-20240307")
reviewer_agent = LLMClient(provider="deepseek", model="deepseek-chat")

pipeline = AgentPipeline(agents=[research_agent, writer_agent, reviewer_agent])
```

### Supervisor with mixed providers

```python
supervisor = AgentSupervisor(
    supervisor=LLMClient(provider="openai", model="gpt-4"),
    agents={
        "fast": AgentConfig(
            name="fast",
            client=LLMClient(provider="mimo", model="mimo-v2.5"),
            system_prompt="Respond quickly and concisely.",
        ),
        "accurate": AgentConfig(
            name="accurate",
            client=LLMClient(provider="anthropic", model="claude-4-sonnet"),
            system_prompt="Reason carefully and provide detailed answers.",
            cost_limit_usd=0.02,
        ),
    },
)
```

### Fan-out with 4 providers

```python
fanout = AgentFanOut(
    agents={
        "OpenAI":    LLMClient(provider="openai", model="gpt-4o-mini"),
        "Anthropic": LLMClient(provider="anthropic", model="claude-3-haiku-20240307"),
        "DeepSeek":  LLMClient(provider="deepseek", model="deepseek-chat"),
        "Ollama":    LLMClient(provider="ollama", model="gemma3"),
    },
)
```

### Environment setup

Set API keys for each provider you plan to use:

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export DEEPSEEK_API_KEY="sk-..."
export OPENROUTER_API_KEY="sk-or-..."
export MIMO_API_KEY="..."
export GEMINI_API_KEY="..."
export MISTRAL_API_KEY="..."
export CO_API_KEY="..."
# Ollama runs locally — no API key needed
```

---

## Cost Management

Every orchestration pattern tracks cost and can enforce limits.

### Per-agent cost limits

```python
# Per-agent cap via AgentConfig
expensive_agent = AgentConfig(
    name="deep-research",
    client=LLMClient(provider="anthropic", model="claude-4-sonnet"),
    system_prompt="Do deep research.",
    cost_limit_usd=0.05,  # cap at $0.05 per invocation
)
```

### Team-level cost limits

```python
# Team cost cap in AgentSupervisor
supervisor = AgentSupervisor(
    supervisor=LLMClient(provider="openai"),
    agents=agent_cfg,
    cost_limit_usd=0.10,  # total team spend cap
)
```

### Cost tracking from results

```python
# Pipeline
result = pipeline.run(input_data)
print(f"Total cost: ${result.total_cost_usd:.4f}")
print(f"Total tokens: {result.total_tokens}")
for step in result.steps:
    print(f"  {step.name}: ${step.cost_usd:.4f} / {step.tokens_used}tokens")

# Supervisor (returns AgentTeamResult)
result = supervisor.run(prompt)
print(f"Total cost: ${result.total_cost_usd:.4f}")
print(f"Delegation trace:")
for event in result.delegation_trace:
    print(f"  {event.from_agent} → {event.to_agent}: "
          f"{event.task_description[:60]}")
```

### CostLimitExceededError

When a cost limit is hit, the system raises `CostLimitExceededError`:

```python
from ai_vibe_coding import CostLimitExceededError

try:
    result = supervisor.run(expensive_prompt)
except CostLimitExceededError as e:
    print(f"Cost limit exceeded: {e}")
    # e.current_cost — the cost at violation
    # e.limit — the configured limit
    # e.agent_name — which agent exceeded (None = team-level)
```

### Budgeting recommendations

| Scenario | Strategy |
|----------|----------|
| Prototyping | Use cheap models (MiMo, Ollama, Gemini Flash) with no cost limits |
| Production | Set per-agent limits and a team cap |
| Cost-sensitive | Route simple queries to cheap providers, complex to capable ones |
| High-volume | Use `AgentFanOut` with cheap parallel agents, aggregate with free fan-in |

---

## Error Handling

The agent templates include dedicated error-handling wrappers.

### AgentCircuitBreaker

Tracks failures per provider and opens the circuit after a threshold.

```python
from ai_vibe_coding import AgentCircuitBreaker

breaker = AgentCircuitBreaker(
    agent_config=some_agent,
    failure_threshold=5,
    reset_timeout=30.0,
)

# Use with a pipeline
pipeline = AgentPipeline(
    agents=[agent_a, agent_b],
    circuit_breaker=breaker,
)
```

When the circuit is open, the pipeline skips further agents with
`PipelineStep(status="skipped", error="Circuit breaker open")`.

Internal API (for custom integration):
- **`record_failure(provider)`** — increment failure count for a provider
- **`is_open(provider)`** — check if circuit is open
- **`allow_probe`** — check if any circuit is open for probing
- **`try_probe(provider)`** — attempt a probe request (resets to closed)

### AgentRetryPolicy

Retries an agent call with exponential backoff and optional dead-letter queue.

```python
from ai_vibe_coding import AgentRetryPolicy, MessageBus

dlq = MessageBus()

retry_policy = AgentRetryPolicy(
    agent=LLMClient(provider="openai"),
    max_retries=3,
    dead_letter_queue=dlq,
    base_delay=0.5,
)

try:
    result = retry_policy.run_with_retry("Hello")
except Exception as e:
    print(f"All {retry_policy.max_retries} retries exhausted: {e}")

# Check retry count
print(f"Retries: {retry_policy.retry_count}")
```

The dead-letter queue receives an `AgentMessage` with type `"error.dead_letter"`
containing the original input, the error, and the retry count — useful for
building error dashboards or replay pipelines.

### AgentFallback

Tries primary agent first, then each fallback in order.

```python
from ai_vibe_coding import AgentFallback

fallback = AgentFallback(
    primary=LLMClient(provider="openai", model="gpt-4"),
    fallbacks=[
        LLMClient(provider="anthropic", model="claude-4-sonnet"),
        LLMClient(provider="deepseek", model="deepseek-chat"),
    ],
)

result = fallback.run("Explain neural networks")
print(f"From: {result['content'][:100]}...")
print(f"Cost: ${result['total_cost_usd']:.4f}")
```

### Error handling reference

| Exception | Raised when | Handled by |
|-----------|-------------|------------|
| `AgentTimeoutError` | Agent execution exceeds timeout | `AgentPipeline` (timeout_per_step) |
| `AgentCircuitOpenError` | Circuit breaker rejects call | `AgentPipeline` (skips step) |
| `AgentMaxRetriesError` | All retries exhausted | `AgentRetryPolicy` |
| `CostLimitExceededError` | Cost limit breached | `AgentSupervisor`, `AgentTeam` |
| `AgentError` (base) | All agent template errors | Catch-all |

---

## Migration from Single-Agent to Multi-Agent

### Step 1: Single agent call

```python
client = LLMClient(provider="openai")
response = client.chat("Generate a blog post about AI")
print(response.content)
```

### Step 2: Sequential pipeline (fixed steps)

```python
outline = LLMClient(provider="openai")
writer  = LLMClient(provider="anthropic")
pipeline = AgentPipeline(agents=[outline, writer])
result = pipeline.run("Generate a blog post about AI")
print(result.final_output)
```

### Step 3: Add a review step

```python
outline  = LLMClient(provider="openai")
writer   = LLMClient(provider="anthropic")
reviewer = LLMClient(provider="deepseek")
pipeline = AgentPipeline(agents=[outline, writer, reviewer])
result = pipeline.run("Generate a blog post about AI")
```

### Step 4: Supervisor for dynamic delegation

```python
supervisor = AgentSupervisor(
    supervisor=LLMClient(provider="openai"),
    agents={
        "outliner": AgentConfig(name="outliner", client=outline_client, ...),
        "writer":   AgentConfig(name="writer",   client=writer_client, ...),
        "reviewer": AgentConfig(name="reviewer", client=review_client, ...),
    },
)
result = supervisor.run("Generate a blog post about AI")
```

### Step 5: Event-driven architecture

```python
coordinator = AgentPubSubCoordinator(message_bus=MessageBus())
# Register agents that react to events rather than being called directly
```

### Migration tips

1. **Start simple** — migrate a single `client.chat()` call to a 2-agent pipeline
2. **Add cost limits early** — prevent surprise bills during iteration
3. **Test with mocked responses** — all tests use `unittest.mock`, no API keys needed
4. **Use the delegation trace** — `supervisor.run()` returns delegation events showing
   exactly what was delegated to whom
5. **Mix providers strategically** — cheap models for routine steps, capable models
   for complex reasoning

---

## Complete API Reference

### Foundation classes

| Class | Module | Description |
|-------|--------|-------------|
| `AgentMessage` | `agent_templates` | Immutable message dataclass with auto-generated id/timestamp |
| `MessageBus` | `agent_templates` | Thread-safe pub/sub with wildcard type filtering |
| `SharedState` | `agent_templates` | Thread-safe key-value store with namespace isolation |

### Pattern classes

| Class | Module | Pattern | Description |
|-------|--------|---------|-------------|
| `AgentPipeline` | `agent_templates` | Sequential | Ordered chain with input/output mapping |
| `AgentFanOut` | `agent_templates` | Parallel | Concurrent dispatch to N agents |
| `AgentFanIn` | `agent_templates` | Parallel | Aggregation with join/concatenate/vote strategies |
| `AgentSupervisor` | `agent_templates` | Hierarchical | LLM-based routing with 4 delegation strategies |
| `AgentPubSubCoordinator` | `agent_templates` | Event-driven | MessageBus-based lifecycle coordinator |
| `AgentTeam` | `agent_team` | Hierarchical | Low-level supervisor (wrapped by AgentSupervisor) |

### Error handling classes

| Class | Module | Description |
|-------|--------|-------------|
| `AgentCircuitBreaker` | `agent_templates` | Per-provider circuit breaker |
| `AgentRetryPolicy` | `agent_templates` | Retry with exponential backoff + DLQ |
| `AgentFallback` | `agent_templates` | Primary → fallback failover |
| `AgentTimeoutError` | `agent_templates` | Raised on agent timeout |
| `AgentCircuitOpenError` | `agent_templates` | Raised when circuit breaker is open |
| `AgentMaxRetriesError` | `agent_templates` | Raised when retries exhausted |
| `CostLimitExceededError` | `agent_team` | Raised when cost limit exceeded |

### Result classes

| Class | Description |
|-------|-------------|
| `PipelineResult` | Pipeline execution result with per-step records |
| `PipelineStep` | Single step in a pipeline execution |
| `FanOutResult` | Fan-out execution result |
| `AgentTeamResult` | AgentTeam/supervisor execution result |
| `DelegationEvent` | One delegation event in the trace |

### Full import

```python
from ai_vibe_coding import (
    # Foundation
    AgentMessage,
    MessageBus,
    SharedState,
    # Patterns
    AgentPipeline,
    PipelineAgentConfig,
    PipelineResult,
    PipelineStep,
    AgentFanOut,
    AgentFanIn,
    FanOutResult,
    AgentSupervisor,
    AgentPubSubCoordinator,
    AgentPubSubConfig,
    # Error handling
    AgentCircuitBreaker,
    AgentRetryPolicy,
    AgentFallback,
    AgentError,
    AgentTimeoutError,
    AgentCircuitOpenError,
    AgentMaxRetriesError,
    # AgentTeam (low-level)
    AgentTeam,
    AgentConfig,
    AgentTeamResult,
    DelegationEvent,
    CostLimitExceededError,
)
```

---

## Running the Examples

All four example scripts are in the `examples/` directory. Each requires API
keys for its providers:

```bash
# Sequential pipeline (needs OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY)
python -m examples.agent_pipeline_example

# Parallel fan-out/fan-in
python -m examples.agent_parallel_example

# Hierarchical supervisor
python -m examples.agent_supervisor_example

# Pub/sub event-driven (no API keys needed — pure Python simulation)
python -m examples.agent_pubsub_example
```

Set the required environment variables first — see the [Multi-Provider
Configuration](#multi-provider-configuration) section above.

---

*Module: `src/ai_vibe_coding/agent_templates.py` · Version: v0.9.0*
