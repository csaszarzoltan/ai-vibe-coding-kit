"""LLM Cost Calculator & Optimizer — pure-function cost comparison engine.

Provides utilities for:
- Calculating costs for specific provider/model combos
- Comparing costs across all supported providers
- Recommending the best provider for a given task type

All functions are pure and deterministic — no I/O, no state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai_vibe_coding.llm_wrapper import PRICING

# ---------------------------------------------------------------------------
# Default quality / speed scores per provider (used when no benchmark data)
# Scale: 0.0 (worst) – 1.0 (best)
# ---------------------------------------------------------------------------
_PROVIDER_QUALITY: dict[str, float] = {
    "openai": 0.85,
    "anthropic": 0.85,
    "deepseek": 0.75,
    "openrouter": 0.70,
    "mimo": 0.45,
    "gemini": 0.75,
    "mistral": 0.70,
    "cohere": 0.60,
    "ollama": 0.30,
}

_PROVIDER_SPEED: dict[str, float] = {
    "openai": 0.85,
    "anthropic": 0.75,
    "deepseek": 0.80,
    "openrouter": 0.70,
    "mimo": 0.55,
    "gemini": 0.85,
    "mistral": 0.75,
    "cohere": 0.65,
    "ollama": 0.90,
}

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CostOption:
    """A single provider/model combination with calculated costs."""

    provider: str
    model: str
    input_cost: float
    output_cost: float
    total_cost: float
    cost_per_1k_tokens: float


@dataclass
class TaskProfile:
    """Weight profile for a task type."""

    name: str
    cost_weight: float
    quality_weight: float
    speed_weight: float
    min_quality_score: float
    suggested_models: list[str] = field(default_factory=list)


@dataclass
class RankedOption:
    """A recommended provider/model with ranking info."""

    provider: str
    model: str
    total_cost: float
    value_score: float
    explanation: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_default_model(provider: str) -> str:
    """Return the first (default) model for a provider."""
    models = list(PRICING[provider].keys())
    return models[0]


def _known_providers() -> list[str]:
    return list(PRICING.keys())


def _cost_per_1k(
    input_tokens: int, output_tokens: int, input_rate: float, output_rate: float
) -> float:
    """Cost per 1K tokens (total) for the given token mix."""
    total_tokens = input_tokens + output_tokens
    if total_tokens == 0:
        return 0.0
    total = (input_tokens / 1000 * input_rate) + (
        output_tokens / 1000 * output_rate
    )
    # Normalize to per-1K-token: (total_cost / total_tokens) * 1000
    return round((total / total_tokens) * 1000, 6)


def _load_profiles() -> dict[str, TaskProfile]:
    """Load task profiles from cost_profiles.json adjacent to this module."""
    path = Path(__file__).resolve().parent / "cost_profiles.json"
    data = json.loads(path.read_text())
    profiles: dict[str, TaskProfile] = {}
    for name, vals in data.items():
        profiles[name] = TaskProfile(
            name=name,
            cost_weight=vals["cost_weight"],
            quality_weight=vals["quality_weight"],
            speed_weight=vals["speed_weight"],
            min_quality_score=vals.get("min_quality_score", 0.0),
            suggested_models=vals.get("suggested_models", []),
        )
    return profiles


def _cost_option_to_dict(opt: CostOption) -> dict[str, Any]:
    return {
        "provider": opt.provider,
        "model": opt.model,
        "input_cost": opt.input_cost,
        "output_cost": opt.output_cost,
        "total_cost": opt.total_cost,
        "cost_per_1k_tokens": opt.cost_per_1k_tokens,
    }


def _ranked_option_to_dict(opt: RankedOption) -> dict[str, Any]:
    return {
        "provider": opt.provider,
        "model": opt.model,
        "total_cost": opt.total_cost,
        "value_score": opt.value_score,
        "explanation": opt.explanation,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    provider: str,
    model: str | None = None,
) -> float:
    """Calculate the cost of an LLM API call.

    Args:
        input_tokens: Number of input (prompt) tokens.
        output_tokens: Number of output (completion) tokens.
        provider: Provider name (e.g. "openai", "anthropic").
        model: Model name (e.g. "gpt-4"). If None, uses provider default.

    Returns:
        Total cost in USD, rounded to 6 decimal places.

    Raises:
        ValueError: If tokens are negative or provider is unknown.
    """
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError(
            f"Token counts must be non-negative, got "
            f"input={input_tokens}, output={output_tokens}"
        )

    if provider not in PRICING:
        known = ", ".join(sorted(_known_providers()))
        raise ValueError(
            f"Unknown provider '{provider}'. Known providers: {known}"
        )

    provider_pricing = PRICING[provider]
    if model is None or model not in provider_pricing:
        # Fall back to provider's default (first) model
        model = _get_default_model(provider)

    rates = provider_pricing[model]
    cost = (input_tokens / 1000 * rates["input"]) + (
        output_tokens / 1000 * rates["output"]
    )
    return round(cost, 6)


def compare_all(
    input_tokens: int,
    output_tokens: int,
    task_type: str = "general",
    providers: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Compare costs across all providers for given token counts.

    Args:
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        task_type: Task profile type (ignored in basic comparison).
        providers: Optional list of providers to filter by.

    Returns:
        Sorted list of CostOption dicts, cheapest first.
    """
    all_providers = providers or _known_providers()
    results: list[CostOption] = []

    for prov in all_providers:
        if prov not in PRICING:
            continue
        for model_name, rates in PRICING[prov].items():
            input_cost = round(input_tokens / 1000 * rates["input"], 6)
            output_cost = round(output_tokens / 1000 * rates["output"], 6)
            total_cost = round(input_cost + output_cost, 6)
            cpt = _cost_per_1k(
                input_tokens,
                output_tokens,
                rates["input"],
                rates["output"],
            )
            results.append(
                CostOption(
                    provider=prov,
                    model=model_name,
                    input_cost=input_cost,
                    output_cost=output_cost,
                    total_cost=total_cost,
                    cost_per_1k_tokens=cpt,
                )
            )

    results.sort(key=lambda x: x.total_cost)
    return [_cost_option_to_dict(r) for r in results]


def recommend_for_task(
    input_tokens: int,
    output_tokens: int,
    task_type: str = "general",
    providers: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Recommend the best provider for a task type based on value scoring.

    Args:
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        task_type: Task profile type (coding, chat, analysis, translation, general).
        providers: Optional list of providers to filter by.

    Returns:
        Sorted list of RankedOption dicts, best value first.
    """
    profiles = _load_profiles()

    # Fall back to "general" for unknown task types
    if task_type not in profiles:
        task_type = "general"

    profile = profiles[task_type]

    all_providers = providers or _known_providers()

    # Collect cost options first
    cost_options: list[tuple[str, str, float]] = []  # (provider, model, total_cost)
    for prov in all_providers:
        if prov not in PRICING:
            continue
        for model_name, rates in PRICING[prov].items():
            tc = round(
                (input_tokens / 1000 * rates["input"])
                + (output_tokens / 1000 * rates["output"]),
                6,
            )
            cost_options.append((prov, model_name, tc))

    if not cost_options:
        return []

    # Compute cost scores: normalized 0-1 (cheapest = 1.0)
    costs = [c[2] for c in cost_options]
    min_cost = min(costs)
    max_cost = max(costs)

    results: list[RankedOption] = []
    for prov, model_name, total_cost in cost_options:
        # Cost score: cheaper is better
        if max_cost > min_cost:
            cost_score = 1.0 - (total_cost - min_cost) / (max_cost - min_cost)
        else:
            cost_score = 1.0  # all equal (e.g., zero tokens)

        quality_score = _PROVIDER_QUALITY.get(prov, 0.5)
        speed_score = _PROVIDER_SPEED.get(prov, 0.5)

        # Composite value score
        raw_score = (
            profile.cost_weight * cost_score
            + profile.quality_weight * quality_score
            + profile.speed_weight * speed_score
        )
        value_score = round(raw_score * 10, 2)

        # Build explanation
        parts = []
        if profile.quality_weight > 0 and quality_score >= profile.min_quality_score:
            parts.append("meets quality threshold")
        elif profile.quality_weight > 0:
            parts.append("below quality threshold")
        if profile.cost_weight > 0:
            parts.append(f"cost score {cost_score:.2f}")
        parts.append(f"quality score {quality_score:.2f}")
        explanation = "; ".join(parts)

        results.append(
            RankedOption(
                provider=prov,
                model=model_name,
                total_cost=total_cost,
                value_score=value_score,
                explanation=explanation,
            )
        )

    # Sort by value_score descending (best first)
    results.sort(key=lambda x: x.value_score, reverse=True)
    return [_ranked_option_to_dict(r) for r in results]


__all__ = [
    "CostOption",
    "RankedOption",
    "TaskProfile",
    "calculate_cost",
    "compare_all",
    "recommend_for_task",
]
