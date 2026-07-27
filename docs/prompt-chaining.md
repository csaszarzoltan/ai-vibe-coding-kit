# Prompt Chaining & Agent Workflow Templates

Module: `src/ai_vibe_coding/chain_templates.py`  
Imported via: `from ai_vibe_coding import SequentialChain, ...`

## Overview

Prompt chaining lets you compose LLM calls into multi-step workflows. Use chains when
a single LLM call isn't enough — when you need branching, parallelism, tool use,
human approval, or processing of documents too large for one context window.

### When to use what

| Pattern | Use when | Example |
|---------|----------|---------|
| **Single LLM call** | One-shot Q&A, simple generation | "Summarize this text" |
| **Sequential chain** | Fixed N steps in known order | Research → Outline → Write |
| **Conditional chain** | Branching based on intermediate output | Classify → Route to handler |
| **Parallel chain** | Independent subtasks | Style + Security + Performance review |
| **Map-reduce chain** | Document exceeds context window | Split → Analyze each section → Synthesize |
| **Agent-with-tools** | LLM needs external data or actions | Web search → Read pages → Write report |
| **Human-in-the-loop** | Approval gates before dangerous ops | Review content before publishing |

## Quick Start

A 3-step sequential chain: research → outline → write.

```python
from ai_vibe_coding import LLMClient, SequentialChain

client = LLMClient(provider="openai")


def research_step(ctx):
    """Research step: generate raw material."""
    return client.chat(
        f"Research this topic and provide 3 key points: {ctx.steps.get('input', '')}"
    )


def outline_step(ctx):
    """Outline step: turn research into structure."""
    research_output = ctx.steps["research"]
    return client.chat(
        f"Based on this research:\n{research_output}\n\nCreate a detailed outline."
    )


def write_step(ctx):
    """Write step: expand outline into full article."""
    outline = ctx.steps["outline"]
    return client.chat(
        f"Write a full article based on this outline:\n{outline}"
    )


# Assign names so steps can reference each other's outputs
research_step.name = "research"
outline_step.name = "outline"
write_step.name = "write"

chain = SequentialChain(steps=[research_step, outline_step, write_step])
result = chain.run("Benefits of renewable energy")

print(f"Status: {result.status}")
print(f"Total cost: ${result.total_cost_usd:.4f}")
for step in result.steps:
    print(f"  [{step.status}] {step.name} — ${step.cost_usd:.4f}, {step.latency_ms:.0f}ms")
```

## Pattern Reference

---

### 1. Sequential Chain

A fixed-order pipeline where each step receives the accumulated context and can
reference any prior step's output by name.

**When to use:** You know the exact steps and their order at design time.

#### Constructor

```text
SequentialChain(steps: list, max_retries: int = 1)
```

| Param | Default | Description |
|-------|---------|-------------|
| `steps` | (required) | Ordered list of callable step objects. Each step receives a `ChainContext` and returns output. |
| `max_retries` | `1` | Number of times to retry a step on failure. Step names must be unique across the list. |

#### .run()

```text
chain.run(input_data: Any = None) -> ChainResult
```

Accepts a `ChainContext`, a `dict` (wrapped into `ChainContext(steps=...)`), or a raw value
(wrapped as `ChainContext(steps={"input": value})`).

#### Real-world use case: Blog post generation

```python
from ai_vibe_coding import LLMClient, SequentialChain

client = LLMClient(provider="openai")


def research(ctx):
    return client.chat(f"Research: {ctx.steps.get('input', '')}")


def outline(ctx):
    return client.chat(f"Create an outline from:\n{ctx.steps['research']}")


def write(ctx):
    return client.chat(f"Write full article from:\n{ctx.steps['outline']}")


def proofread(ctx):
    return client.chat(f"Proofread this article:\n{ctx.steps['write']}")


research.name = "research"
outline.name = "outline"
write.name = "write"
proofread.name = "proofread"

chain = SequentialChain(steps=[research, outline, write, proofread], max_retries=2)
result = chain.run("Explain prompt chaining in 500 words")
```

---

### 2. Conditional Chain (Routing)

A gate function decides which branch to execute. After the branch runs, optional
converge steps execute. Multiple additional gates can be chained.

**When to use:** The next step depends on the output of previous steps.

#### Constructor

```text
ConditionalChain(
    gate_fn: Callable[[Any], bool],
    true_branch: list,
    false_branch: list,
    converge_steps: list | None = None,
    additional_gates: list | None = None,
)
```

| Param | Default | Description |
|-------|---------|-------------|
| `gate_fn` | (required) | Callable `(context) -> bool` that decides which branch to run. |
| `true_branch` | (required) | Steps executed when the gate returns `True`. |
| `false_branch` | (required) | Steps executed when the gate returns `False`. |
| `converge_steps` | `None` | Optional steps run after either branch completes. |
| `additional_gates` | `None` | List of `(gate_fn, true_branch, false_branch)` tuples for multi-gate sequences. |

#### Real-world use case: Customer support routing

```python
from ai_vibe_coding import LLMClient, LLMResponse, ConditionalChain

client = LLMClient(provider="openai")


def classify_intent(ctx):
    """Classify customer query intent."""
    response = client.chat(
        f"Classify the intent of this message as 'billing', 'tech', or 'sales': "
        f"{ctx.steps.get('input', '')}"
    )
    return response


def handle_billing(ctx):
    return client.chat(
        f"The customer has a billing issue: {ctx.steps['input']}\n"
        f"Write a helpful billing response."
    )


def handle_tech(ctx):
    return client.chat(
        f"The customer has a technical issue: {ctx.steps['input']}\n"
        f"Write a helpful technical support response."
    )


def handle_sales(ctx):
    return client.chat(
        f"The customer has a sales inquiry: {ctx.steps['input']}\n"
        f"Write a helpful sales response."
    )


classify_intent.name = "classify"
handle_billing.name = "billing_response"
handle_tech.name = "tech_response"
handle_sales.name = "sales_response"


def is_tech(ctx):
    output = str(ctx.steps.get("classify", ""))
    return "tech" in output.lower()


def is_billing(ctx):
    output = str(ctx.steps.get("classify", ""))
    return "billing" in output.lower()


chain = ConditionalChain(
    gate_fn=is_tech,
    true_branch=[handle_tech],
    false_branch=[handle_billing],
    additional_gates=[(is_billing, [handle_billing], [handle_sales])],
)
result = chain.run("My payment didn't go through")
```

---

### 3. Parallel Chain (Fan-Out / Fan-In)

All steps execute concurrently using a `ThreadPoolExecutor`. Each step receives the
same input context. Results are aggregated by the configured strategy.

**When to use:** Multiple independent analyses that can run simultaneously.

#### Constructor

```text
ParallelChain(
    steps: list,
    max_workers: int | None = None,
    timeout: float = 30.0,
    aggregation: str = "join",
)
```

| Param | Default | Description |
|-------|---------|-------------|
| `steps` | (required) | List of callable step objects to execute concurrently. |
| `max_workers` | `len(steps)` | Maximum thread pool size. |
| `timeout` | `30.0` | Per-step timeout in seconds. |
| `aggregation` | `"join"` | Aggregation strategy: `"join"` or `"concatenate"`. |

#### Real-world use case: Multi-aspect code review

```python
from ai_vibe_coding import LLMClient, ParallelChain

client = LLMClient(provider="openai")


def check_style(ctx):
    code = ctx.steps.get("input", "")
    prompt = "Review this code for style issues. Put your answer in a code block:\n" + code
    return client.chat(prompt)


def check_security(ctx):
    code = ctx.steps.get("input", "")
    prompt = "Review this code for security vulnerabilities. Put your answer in a code block:\n" + code
    return client.chat(prompt)


def check_performance(ctx):
    code = ctx.steps.get("input", "")
    prompt = "Review this code for performance issues. Put your answer in a code block:\n" + code
    return client.chat(prompt)


check_style.name = "style"
check_security.name = "security"
check_performance.name = "performance"

chain = ParallelChain(
    steps=[check_style, check_security, check_performance],
    max_workers=3,
    timeout=60.0,
)
result = chain.run("def fib(n):\n    return n if n < 2 else fib(n-1) + fib(n-2)")

for step in result.steps:
    print(f"[{step.status}] {step.name} — {step.output[:80]}...")
```

---

### 4. Map-Reduce Chain

Splits input into N chunks, processes each chunk independently, then merges the
individual results via a reduce function.

**When to use:** Documents or inputs larger than the LLM's context window.

#### Constructor

```text
MapReduceChain(
    map_fn: Callable[[Any, int], list[Any]],
    reduce_fn: Callable[[list[Any]], Any],
    chunk_count: int = 1,
)
```

| Param | Default | Description |
|-------|---------|-------------|
| `map_fn` | (required) | Callable `(input_data, chunk_count) -> list[str]` that splits input into chunks. The chunks are what each map step processes. |
| `reduce_fn` | (required) | Callable `(list[Any]) -> Any` that merges individual chunk outputs. |
| `chunk_count` | `1` | Number of chunks to split into. |

#### Real-world use case: Long contract analysis

```python
from ai_vibe_coding import LLMClient, MapReduceChain

client = LLMClient(provider="openai")


def split_contract(text, n):
    """Split contract text into n roughly equal sections by paragraph."""
    paragraphs = text.split("\n\n")
    chunk_size = max(1, len(paragraphs) // n)
    return ["\n\n".join(paragraphs[i:i + chunk_size]) for i in range(0, len(paragraphs), chunk_size)]


def analyze_section(section):
    """Analyze a single section — this runs per chunk in the map phase."""
    return client.chat(
        f"Extract all obligations and deadlines from this contract section:\n{section}"
    )


def merge_obligations(analyses):
    """Merge individual section analyses into a master list."""
    combined = "\n\n".join(
        str(a) for a in analyses if a is not None
    )
    return client.chat(
        f"Merge these section analyses into a master list of obligations:\n{combined}"
    )


# Wrap the map_fn so it processes chunks through the LLM
def map_and_analyze(text, n):
    chunks = split_contract(text, n)
    return [analyze_section(chunk) for chunk in chunks]


chain = MapReduceChain(
    map_fn=map_and_analyze,
    reduce_fn=merge_obligations,
    chunk_count=4,
)
result = chain.run(long_contract_text)

for step in result.steps:
    print(f"[{step.status}] {step.name}")
```

---

### 5. Agent-with-Tools Chain (ReAct)

A ReAct (Reasoning + Acting) loop that iterates: think → decide tool → call tool →
observe → repeat, until the LLM responds directly or max iterations are reached.

**When to use:** The LLM needs to call external tools, search the web, or perform
actions that aren't text generation alone.

#### Constructor

```text
AgentWithToolsChain(
    llm_client: LLMClient,
    tools: list[ToolDef],
    max_iterations: int = 10,
)
```

| Param | Default | Description |
|-------|---------|-------------|
| `llm_client` | (required) | `LLMClient` instance for chat completion. |
| `tools` | (required) | List of `ToolDef` definitions available to the agent. |
| `max_iterations` | `10` | Maximum ReAct loop iterations. |

#### Real-world use case: Research assistant

```python
from ai_vibe_coding import LLMClient
from ai_vibe_coding.chain_templates import AgentWithToolsChain
from ai_vibe_coding.structured import ToolDef

client = LLMClient(provider="openai")

tools = [
    ToolDef(
        name="search_web",
        description="Search the web for information on a topic",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    ),
    ToolDef(
        name="read_url",
        description="Read the content of a web page",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to read"},
            },
            "required": ["url"],
        },
    ),
    ToolDef(
        name="calculate",
        description="Perform a mathematical calculation",
        parameters={
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression"},
            },
            "required": ["expression"],
        },
    ),
]

chain = AgentWithToolsChain(
    llm_client=client,
    tools=tools,
    max_iterations=8,
)
result = chain.run("What is the current population of Tokyo in millions?")

for step in result.steps:
    print(f"[{step.status}] {step.name} — ${step.cost_usd:.4f}, {step.latency_ms:.0f}ms")
```

---

### 6. ChainRunner

Unified runner that dispatches to any chain type. Also supports streaming mode
where step events are yielded as they complete.

#### Constructor

```text
ChainRunner()
```

No arguments — `ChainRunner` is stateless. Instantiate and call `.run()`.

#### .run()

```text
runner.run(
    chain: Any,
    input_data: Any = None,
    stream: bool = False,
) -> ChainResult | list[dict[str, Any]]
```

| Param | Default | Description |
|-------|---------|-------------|
| `chain` | (required) | A chain instance (`SequentialChain`, `ConditionalChain`, `ParallelChain`, `MapReduceChain`, or `AgentWithToolsChain`). |
| `input_data` | `None` | Input to pass to the chain. |
| `stream` | `False` | If `True`, yields step completion events as a list of dicts instead of returning a single `ChainResult`. |

**Raises:** `TypeError` if chain is a string or bytes.

#### Streaming mode

```python
from ai_vibe_coding import ChainRunner, SequentialChain, LLMClient

client = LLMClient(provider="openai")

step1 = lambda ctx: client.chat(f"Research: {ctx.steps.get('input', '')}")
step2 = lambda ctx: client.chat(f"Summarize: {ctx.steps['step1']}")
step1.name = "step1"
step2.name = "step2"

chain = SequentialChain(steps=[step1, step2])
runner = ChainRunner()

events = runner.run(chain, "Quantum computing basics", stream=True)
for event in events:
    print(f"{event['name']}: {event['status']} ({event['latency_ms']:.0f}ms)")
```

---

### 7. Human-in-the-Loop (HITLStep)

Pauses chain execution to request approval via an `CallableApprovalChannel`. On
denial, the step can execute an alternative path instead.

#### Constructor

```text
HITLStep(
    name: str,
    approval_channel: CallableApprovalChannel,
    prompt: str = "",
    on_denied: list | None = None,
)
```

| Param | Default | Description |
|-------|---------|-------------|
| `name` | (required) | Step name (appears in `ChainStep` records). |
| `approval_channel` | (required) | `CallableApprovalChannel` instance — callable `(tool_name, arguments) -> bool`. |
| `prompt` | `""` | Context message shown for approval. |
| `on_denied` | `None` | Optional list of steps to execute if approval is denied. |

#### Example: Approve content before publishing

```python
from ai_vibe_coding import SequentialChain, HITLStep
from ai_vibe_coding.structured import CallableApprovalChannel


def get_approval(step_name, context):
    """Simple approval function — in practice this would notify a human."""
    print(f"Approve '{step_name}'?")
    print(f"Context: {context}")
    return input("y/n: ").lower() == "y"


def draft_content(ctx):
    return "Draft article about AI trends..."


def publish(ctx):
    return "Published!"


def archive(ctx):
    return "Content archived."


draft_content.name = "draft"
publish.name = "publish"
archive.name = "archive"

hitl = HITLStep(
    name="review",
    approval_channel=CallableApprovalChannel(get_approval),
    prompt="Review the draft before publishing",
    on_denied=[archive],
)

chain = SequentialChain(steps=[draft_content, hitl, publish])
result = chain.run("Write an article about AI")

for step in result.steps:
    print(f"[{step.status}] {step.name} — {step.output[:50]}")
```

---

## Data Model Reference

### ChainContext

```text
ChainContext(steps: dict[str, Any] = {})
```

Execution context holding step outputs accessible by name.

| Attribute | Type | Description |
|-----------|------|-------------|
| `steps` | `dict[str, Any]` | Maps step names to their outputs. |

---

### ChainStep

```text
ChainStep(
    name: str,
    provider: str = "",
    prompt: str = "",
    output: str = "",
    latency_ms: float = 0.0,
    cost_usd: float = 0.0,
    status: str = "pending",
)
```

Record of a single step execution.

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Step name. |
| `provider` | `str` | LLM provider used. |
| `prompt` | `str` | The prompt sent. |
| `output` | `str` | Step output text. |
| `latency_ms` | `float` | Execution latency in milliseconds. |
| `cost_usd` | `float` | Cost in USD. |
| `status` | `str` | One of `"pending"`, `"completed"`, `"failed"`, `"denied"`. |

---

### ChainResult

```text
ChainResult(
    steps: list[ChainStep],
    total_cost_usd: float,
    total_tokens: int,
    status: str,
)
```

Result of executing a chain.

| Attribute | Type | Description |
|-----------|------|-------------|
| `steps` | `list[ChainStep]` | Ordered list of step records. |
| `total_cost_usd` | `float` | Accumulated cost across all steps. |
| `total_tokens` | `int` | Accumulated token count. |
| `status` | `str` | `"completed"` or `"failed"`. |

#### Methods

- `to_dict() -> dict[str, Any]` — JSON-serializable dict representation.

---

### ChainError

```text
ChainError(step_name: str, message: str, original_exception: Exception)
```

Error information for a failed chain step.

| Attribute | Type | Description |
|-----------|------|-------------|
| `step_name` | `str` | Name of the step that failed. |
| `message` | `str` | Human-readable error message. |
| `original_exception` | `Exception` | The original exception. |

---

## Best Practices

1. **Start sequential, add complexity only when needed.** A `SequentialChain` is
   the simplest and most predictable pattern. Don't reach for `AgentWithToolsChain`
   unless the LLM genuinely needs to call external tools.

2. **Use programmatic gates instead of LLM gates when possible.** A string
   contains-check or regex is cheaper and more reliable than asking an LLM to
   classify. Reserve LLM-based gates for ambiguous natural language decisions.

3. **Set `max_iterations` on ReAct loops.** Without a cap, an agent can loop
   indefinitely. Start with 5–8 iterations for most search/analysis tasks.

4. **Inspect `ChainResult.steps` for debugging.** Every step records its status,
   latency, cost, and output. Use `result.to_dict()` for JSON export.

5. **Name your step functions.** Step names must be unique within a chain and
   let downstream steps reference outputs by name via `ctx.steps["name"]`.

6. **Handle failures gracefully.** `SequentialChain` stops on the first failed step
   and returns status `"failed"`. Wrap chain execution in try/except for
   production use.

7. **Monitor total cost.** Check `result.total_cost_usd` after each chain run.
   For long-running agents, consider pairing with `CostTracker` from
   `ai_vibe_coding.cost_tracker`.

## Full API Reference

All exported classes from `ai_vibe_coding.chain_templates`:

| Class | Constructor | .run() return |
|-------|-------------|---------------|
| `SequentialChain` | `(steps, max_retries=1)` | `ChainResult` |
| `ConditionalChain` | `(gate_fn, true_branch, false_branch, converge_steps=None, additional_gates=None)` | `ChainResult` |
| `ParallelChain` | `(steps, max_workers=None, timeout=30.0, aggregation="join")` | `ChainResult` |
| `MapReduceChain` | `(map_fn, reduce_fn, chunk_count=1)` | `ChainResult` |
| `AgentWithToolsChain` | `(llm_client, tools, max_iterations=10)` | `ChainResult` |
| `ChainRunner` | `()` with `.run(chain, input_data=None, stream=False)` | `ChainResult` or `list[dict]` |
| `HITLStep` | `(name, approval_channel, prompt="", on_denied=None)` | `ChainResult` |
| `ChainContext` | `(steps={})` | — |
| `ChainStep` | `(name, provider="", ...)` | — |
| `ChainResult` | `(steps, total_cost_usd, total_tokens, status)` | — |
| `ChainError` | `(step_name, message, original_exception)` | — |

All chain classes expose a `.run(input_data=None) -> ChainResult` method.
