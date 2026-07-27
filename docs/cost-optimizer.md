# LLM Cost Optimizer — Provider Comparison, Budget Planning & Recommendations

Compare, estimate, and optimise LLM API costs across all 9 supported providers.
Get task-type-aware recommendations for coding, chat, analysis, translation, and
general-purpose workloads — all from a single CLI or Python API.

## Overview

The Cost Optimizer module (`src/ai_vibe_coding/cost_calculator.py`) provides
three core functions:

- **Cost Estimation** — Calculate the exact cost of any provider/model/token
  combination using current per-1K-token rates.
- **Provider Comparison** — Rank every model across all 9 providers by total
  cost, with per-1K-token normalised costs.
- **Task-Type Recommendations** — Score providers by a weighted composite of
  cost, quality, and speed to recommend the best model for your specific
  workload.

All functions are pure and deterministic — no I/O, no state, no API calls.
Pricing data is read from the `PRICING` dict in `llm_wrapper.py` and task
profiles from the `cost_profiles.json` file next to the module.

## Quick Start

```bash
# Install the kit
cd ai-vibe-coding-kit
pip install -e ".[dev]"

# Estimate a single GPT-4 call
ai-vibe-bench cost estimate openai gpt-4 500 200
```

The CLI is installed as `ai-vibe-bench`. Cost commands live under the `cost`
subcommand:

| Subcommand   | Purpose                                         |
|-------------|-------------------------------------------------|
| `estimate`  | Cost for one provider/model combo               |
| `compare`   | Compare costs across all (or selected) providers |
| `recommend` | Best provider for a task type                   |
| `pricing`   | Browse current per-model rates                  |

## Provider Pricing

All 9 providers with their models and per-1K-token rates (USD):

| Provider   | Model                     | Input $/1K | Output $/1K |
|------------|---------------------------|------------|-------------|
| OpenAI     | `gpt-4`                   | 0.030000   | 0.060000    |
| OpenAI     | `gpt-4-turbo`             | 0.010000   | 0.030000    |
| OpenAI     | `gpt-4.5`                 | 0.050000   | 0.150000    |
| OpenAI     | `gpt-5`                   | 0.080000   | 0.240000    |
| Anthropic  | `claude-3-5-sonnet`       | 0.003000   | 0.015000    |
| Anthropic  | `claude-4-sonnet`         | 0.003000   | 0.015000    |
| Anthropic  | `claude-4.5-sonnet`       | 0.005000   | 0.025000    |
| DeepSeek   | `deepseek-v3`             | 0.001400   | 0.002800    |
| DeepSeek   | `deepseek-r1`             | 0.001400   | 0.002800    |
| OpenRouter | `default`                 | 0.010000   | 0.030000    |
| MiMo       | `mimo-v2.5`               | 0.000400   | 0.002000    |
| Gemini     | `gemini-2.5-flash`        | 0.000075   | 0.000300    |
| Gemini     | `gemini-2.5-pro`          | 0.001250   | 0.005000    |
| Gemini     | `gemini-2.0-flash`        | 0.000040   | 0.000150    |
| Mistral    | `mistral-large-latest`    | 0.004000   | 0.012000    |
| Mistral    | `mistral-small-latest`    | 0.001000   | 0.003000    |
| Mistral    | `mistral-moderation-latest`| 0.000100  | 0.000100    |
| Cohere     | `command-a-plus-05-2026`  | 0.003000   | 0.015000    |
| Cohere     | `command-r-plus-08-2024`  | 0.003000   | 0.015000    |
| Cohere     | `command-r-08-2024`       | 0.000500   | 0.001500    |
| Cohere     | `embed-v4.0`              | 0.000100   | 0.000100    |
| Cohere     | `rerank-v4.0-pro`         | 0.001000   | 0.001000    |
| Ollama     | `gemma3`                  | 0.00 (local) | 0.00 (local) |
| Ollama     | `llama3`                  | 0.00 (local) | 0.00 (local) |
| Ollama     | `mistral`                 | 0.00 (local) | 0.00 (local) |
| Ollama     | `phi4`                    | 0.00 (local) | 0.00 (local) |
| Ollama     | `qwen2.5`                 | 0.00 (local) | 0.00 (local) |

Pricing is stored in the `PRICING` dict in `src/ai_vibe_coding/llm_wrapper.py`.
See [Pricing Updates](#pricing-updates) for how to update when rates change.

## Cost Estimation

### CLI — Single Call

```bash
ai-vibe-bench cost estimate openai gpt-4 500 200
```

Expected output:

```
Provider:     openai
Model:        gpt-4
Input tokens: 500
Output tokens:200
Total cost:   $0.027000
```

**Positional arguments:** `<provider> <model> <input_tokens> <output_tokens>`

### CLI — Batch Comparison Script

Estimate costs across multiple providers in a single shell loop:

```bash
for pair in "openai,gpt-4" "anthropic,claude-4-sonnet" "deepseek,deepseek-v3"; do
  IFS=',' read -r prov model <<< "$pair"
  ai-vibe-bench cost estimate "$prov" "$model" 5000 2000
  echo "---"
done
```

### Python API

```python
from ai_vibe_coding.cost_calculator import calculate_cost

# Single GPT-4 call: 500 input tokens, 200 output
cost = calculate_cost(500, 200, "openai", "gpt-4")
print(f"Cost: ${cost:.6f}")

# Using provider default model (first model in PRICING)
cost = calculate_cost(1000, 500, "mimo")  # uses mimo-v2.5
print(f"MiMo default: ${cost:.6f}")

# Zero tokens
cost = calculate_cost(0, 0, "openai", "gpt-4")
print(f"Zero cost: ${cost:.6f}")  # 0.0
```

The function signature:

```python
def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    provider: str,
    model: str | None = None,
) -> float: ...
```

- Raises `ValueError` for negative tokens or unknown providers.
- Unknown models fall back to the provider's default (first listed) model.
- Returns total cost in USD, rounded to 6 decimal places.

## Provider Comparison

### CLI — Default (All Providers)

```bash
ai-vibe-bench cost compare 1000 500
```

Output table (truncated — all 24 models sorted by total cost):

```
Provider     Model                      Input Cost    Output Cost    Total Cost  Cost/1K
-------------------------------------------------------------------------------------
ollama       gemma3                    $0.000000     $0.000000     $0.000000   $0.000000
ollama       llama3                    $0.000000     $0.000000     $0.000000   $0.000000
gemini       gemini-2.0-flash          $0.000040     $0.000075     $0.000115   $0.000077
gemini       gemini-2.5-flash          $0.000075     $0.000150     $0.000225   $0.000150
mimo         mimo-v2.5                 $0.000400     $0.001000     $0.001400   $0.000933
deepseek     deepseek-v3               $0.001400     $0.001400     $0.002800   $0.001867
mistral      mistral-small-latest      $0.001000     $0.001500     $0.002500   $0.001667
anthropic    claude-4-sonnet           $0.003000     $0.007500     $0.010500   $0.007000
openai       gpt-4                     $0.030000     $0.030000     $0.060000   $0.040000
...
```

The table is sorted by total cost (cheapest first). Each row shows:

| Column         | Meaning                                           |
|----------------|---------------------------------------------------|
| Provider       | Provider slug                                      |
| Model          | Model name                                         |
| Input Cost     | Cost for input tokens alone                        |
| Output Cost    | Cost for output tokens alone                       |
| Total Cost     | Input cost + output cost                           |
| Cost/1K        | Normalised cost per 1,000 total tokens             |

### CLI — Filtered Providers

```bash
ai-vibe-bench cost compare 1000 500 --providers openai,anthropic,deepseek
```

Only the specified providers appear in the output.

### Python API

```python
from ai_vibe_coding.cost_calculator import compare_all

# All providers, sorted by cost
all_options = compare_all(1000, 500)
for opt in all_options[:5]:
    print(f"{opt['provider']:12s} {opt['model']:20s} ${opt['total_cost']:.6f}")

# Filtered to specific providers
filtered = compare_all(1000, 500, providers=["openai", "anthropic"])
print(f"Options for OpenAI + Anthropic: {len(filtered)}")

# With explicit task type (affects display only in basic comparison)
options = compare_all(2000, 1000, task_type="coding")
```

Function signature:

```python
def compare_all(
    input_tokens: int,
    output_tokens: int,
    task_type: str = "general",
    providers: list[str] | None = None,
) -> list[dict]: ...
```

Returns a list of dicts with keys: `provider`, `model`, `input_cost`,
`output_cost`, `total_cost`, `cost_per_1k_tokens`.

## Task-Type Recommendations

The recommendation engine scores each provider/model by a weighted composite of
cost, quality, and speed:

```
value_score = cost_weight × cost_score
            + quality_weight × quality_score
            + speed_weight × speed_score
```

Each score is normalised 0–1. The result is scaled to a 0–10 scale for
readability.

### 5 Task Types

| Task Type     | Cost Weight | Quality Weight | Speed Weight | Min Quality | Best For                        |
|---------------|-------------|----------------|--------------|-------------|----------------------------------|
| **coding**    | 0.3         | 0.6            | 0.1          | 0.70        | Code generation, debugging       |
| **chat**      | 0.4         | 0.3            | 0.3          | 0.50        | Conversational AI, customer support |
| **analysis**  | 0.2         | 0.7            | 0.1          | 0.80        | Document analysis, data extraction |
| **translation**| 0.5        | 0.3            | 0.2          | 0.40        | Language translation, i18n workflows |
| **general**   | 0.5         | 0.3            | 0.2          | 0.00        | Balanced default                   |

### CLI — Basic Recommendation

```bash
ai-vibe-bench cost recommend coding 5000 2000
```

Output table (truncated — best-ranked options):

```
Rank  Provider     Model                    Total Cost   Value Score  Explanation
----------------------------------------------------------------------------------------------------
1     deepseek     deepseek-v3              $0.012600    8.78         meets quality threshold; cost score 0.52; quality score 0.75
2     mistral      mistral-small-latest     $0.011000    8.37         below quality threshold; cost score 0.56; quality score 0.70
3     gemini       gemini-2.5-flash         $0.000975    8.30         meets quality threshold; cost score 0.99; quality score 0.75
...
```

### CLI — Real-World Scenario

```bash
# "I need to analyze 10K documents with ~2000 tokens each"
ai-vibe-bench cost recommend analysis 2000 1000 --providers anthropic,openai,gemini
```

### CLI — Filtered Recommendation

```bash
# Only consider local + cheap providers for translation
ai-vibe-bench cost recommend translation 1000 500 --providers ollama,mimo,gemini
```

### Python API

```python
from ai_vibe_coding.cost_calculator import recommend_for_task

# Top recommendations for a coding task
recs = recommend_for_task(5000, 2000, "coding")
for rec in recs[:3]:
    print(f"{rec['provider']:12s} {rec['model']:20s} "
          f"${rec['total_cost']:.6f}  score={rec['value_score']:.2f}  "
          f"{rec['explanation']}")

# Filter to specific providers only
recs = recommend_for_task(2000, 1000, "analysis",
                          providers=["anthropic", "openai", "gemini"])

# Unknown task type falls back to 'general'
recs = recommend_for_task(1000, 500, "unknown_type")
```

Function signature:

```python
def recommend_for_task(
    input_tokens: int,
    output_tokens: int,
    task_type: str = "general",
    providers: list[str] | None = None,
) -> list[dict]: ...
```

Returns a list of dicts sorted by `value_score` descending (best first).
Each dict has keys: `provider`, `model`, `total_cost`, `value_score`,
`explanation`.

## Cost Profiles Reference

Task profiles are stored in `src/ai_vibe_coding/cost_profiles.json`. You can
edit this file to adjust weights, add new task types, or pin suggested models.

### JSON Structure

```json
{
  "coding": {
    "cost_weight": 0.3,
    "quality_weight": 0.6,
    "speed_weight": 0.1,
    "min_quality_score": 0.7,
    "suggested_models": [
      "openai/gpt-4",
      "anthropic/claude-4-sonnet",
      "deepseek/deepseek-v3",
      "gemini/gemini-2.5-pro",
      "mistral/mistral-large-latest"
    ]
  }
}
```

### Fields

| Field              | Type    | Description                                         |
|--------------------|---------|-----------------------------------------------------|
| `cost_weight`      | float   | Importance of low cost in the value score (0.0–1.0) |
| `quality_weight`   | float   | Importance of output quality (0.0–1.0)              |
| `speed_weight`     | float   | Importance of response speed (0.0–1.0)              |
| `min_quality_score`| float   | Minimum quality score (0–1) a provider needs to qualify |
| `suggested_models` | string[]| Models recommended as good starting points           |

The three weight fields should sum to 1.0.

### Adding a Custom Task Type

```json
{
  "summarization": {
    "cost_weight": 0.3,
    "quality_weight": 0.5,
    "speed_weight": 0.2,
    "min_quality_score": 0.5,
    "suggested_models": [
      "anthropic/claude-4-sonnet",
      "openai/gpt-4"
    ]
  }
}
```

After editing, test with:

```bash
ai-vibe-bench cost recommend summarization 2000 500
```

## Pricing Updates

Provider rates change over time. To update pricing:

1. Edit the `PRICING` dict in `src/ai_vibe_coding/llm_wrapper.py` (lines 30–76).
2. Each entry: `"provider": { "model-name": {"input": rate, "output": rate} }`
3. Run the calculator tests to verify:

```bash
pytest tests/test_cost_calculator.py -v --tb=short
```

The calculator tests have hardcoded expected costs — update them if rates
changed. The test file is at `tests/test_cost_calculator.py`.

## Integration with Benchmark Suite

While the Cost Optimizer works independently (no benchmark data required), it
integrates naturally with the Benchmark Suite:

- Use `ai-vibe-bench run` to measure actual accuracy, latency, and cost.
- Use `ai-vibe-cost compare` to plan which providers to benchmark.
- Use `ai-vibe-cost recommend` to pick the best provider for your workload
  before running a full benchmark.

The quality and speed scores in `cost_calculator.py` (the
`_PROVIDER_QUALITY` / `_PROVIDER_SPEED` dicts) are manually calibrated defaults.
Future versions may ingest benchmark report data to auto-tune these scores.

## API Reference

All public functions and dataclasses from `src/ai_vibe_coding/cost_calculator.py`.

### `calculate_cost()`

```python
def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    provider: str,
    model: str | None = None,
) -> float
```

Calculate the USD cost of a single LLM API call.

| Parameter      | Type     | Description                                  |
|----------------|----------|----------------------------------------------|
| `input_tokens` | `int`    | Number of prompt tokens (must be >= 0)       |
| `output_tokens`| `int`    | Number of completion tokens (must be >= 0)   |
| `provider`     | `str`    | Provider slug: `openai`, `anthropic`, etc.   |
| `model`        | `str\|None` | Model name. `None` = provider default.     |

**Returns:** `float` — total cost in USD, rounded to 6 decimal places.

**Raises:** `ValueError` on negative tokens or unknown provider.

### `compare_all()`

```python
def compare_all(
    input_tokens: int,
    output_tokens: int,
    task_type: str = "general",
    providers: list[str] | None = None,
) -> list[dict]
```

Compare costs across all (or selected) providers.

| Parameter      | Type                | Description                                    |
|----------------|---------------------|------------------------------------------------|
| `input_tokens` | `int`               | Number of input tokens                         |
| `output_tokens`| `int`               | Number of output tokens                        |
| `task_type`    | `str`               | Profile name (ignored in simple comparison)    |
| `providers`    | `list[str]\|None`   | Filter to these providers. `None` = all.      |

**Returns:** `list[dict]` with keys `provider`, `model`, `input_cost`,
`output_cost`, `total_cost`, `cost_per_1k_tokens`. Sorted by total cost
ascending.

### `recommend_for_task()`

```python
def recommend_for_task(
    input_tokens: int,
    output_tokens: int,
    task_type: str = "general",
    providers: list[str] | None = None,
) -> list[dict]
```

Recommend the best provider/model for a task type.

| Parameter      | Type                | Description                                    |
|----------------|---------------------|------------------------------------------------|
| `input_tokens` | `int`               | Number of input tokens                         |
| `output_tokens`| `int`               | Number of output tokens                        |
| `task_type`    | `str`               | Profile: `coding`, `chat`, `analysis`, `translation`, `general` |
| `providers`    | `list[str]\|None`   | Filter to these providers. `None` = all.      |

**Returns:** `list[dict]` with keys `provider`, `model`, `total_cost`,
`value_score`, `explanation`. Sorted by `value_score` descending (best first).

### Dataclasses

```python
@dataclass
class CostOption:
    provider: str
    model: str
    input_cost: float
    output_cost: float
    total_cost: float
    cost_per_1k_tokens: float

@dataclass
class RankedOption:
    provider: str
    model: str
    total_cost: float
    value_score: float
    explanation: str

@dataclass
class TaskProfile:
    name: str
    cost_weight: float
    quality_weight: float
    speed_weight: float
    min_quality_score: float
    suggested_models: list[str] = []
```

These are re-exported from the top-level package:

```python
from ai_vibe_coding import CostOption, RankedOption, TaskProfile
from ai_vibe_coding import calculate_cost, compare_all, recommend_for_task
```

## Troubleshooting

### "Unknown provider 'xxx'" error

The provider slug is misspelled or not yet in the `PRICING` dict. Run `pricing`
to see all known providers:

```bash
ai-vibe-bench cost pricing
```

Valid slugs: `openai`, `anthropic`, `deepseek`, `openrouter`, `mimo`,
`gemini`, `mistral`, `cohere`, `ollama`.

### Negative token values

Input and output token counts must be >= 0. Passing negative values raises
`ValueError`.

### Empty results from `compare_all` or `recommend_for_task`

If you filtered by `--providers` and the result is empty, none of the specified
providers exist in the `PRICING` dict. Check spelling:

```bash
ai-vibe-bench cost pricing --provider openai
```

### "Unknown task type 'xxx'" on `recommend`

Unknown task types fall back to the `general` profile. The CLI prints a
warning but continues. Add a custom profile to `cost_profiles.json` if you
want dedicated weights.

### Tests fail after pricing update

If you changed rates in the `PRICING` dict, the calculator tests have
hardcoded expected values. Update them in
`tests/test_cost_calculator.py` (`test_calculate_cost_all_providers`
parametrize table) to match the new rates.
