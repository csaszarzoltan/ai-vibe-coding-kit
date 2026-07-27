"""Pre-development acceptance tests for LLM Cost Calculator & Optimizer.

RED phase: ALL tests must fail because the production code has not been written yet.

Test categories:
    - Interface tests:  verify functions/dataclasses exist in cost_calculator.py
    - Behavioral tests: define expected behavior contract (parametrized, edge cases)
    - Profile tests:    validate cost_profiles.json structure
    - CLI tests:        verify cost subcommands registered in argparse

Run:
    pytest tests/test_cost_calculator.py -v --tb=short          # full suite
    pytest tests/test_cost_calculator.py -v -k TestInterface    # interface smoke
    pytest tests/test_cost_calculator.py -v -k TestBehavioral   # behavioral contract
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ai_vibe_coding import cli, cost_calculator

_REPO_ROOT = Path(__file__).resolve().parent.parent


# ===================================================================
# Interface tests — all FAIL with NotImplementedError
# ===================================================================


class TestCostCalculatorInterface:
    """Verify API surface exists — all fail because stubs raise NotImplementedError."""

    def test_calculate_cost_function_exists(self) -> None:
        """calculate_cost should be a callable function."""
        cost_calculator.calculate_cost(1000, 500, "openai", "gpt-4")

    def test_compare_all_function_exists(self) -> None:
        """compare_all should be a callable function."""
        cost_calculator.compare_all(1000, 500)

    def test_recommend_for_task_function_exists(self) -> None:
        """recommend_for_task should be a callable function."""
        cost_calculator.recommend_for_task(1000, 500, "coding")

    def test_cost_option_dataclass(self) -> None:
        """CostOption should be a dataclass with provider, model, input_cost,
        output_cost, total_cost, cost_per_1k_tokens."""
        cost_calculator.CostOption(
            provider="openai",
            model="gpt-4",
            input_cost=0.03,
            output_cost=0.06,
            total_cost=0.06,
            cost_per_1k_tokens=0.04,
        )

    def test_ranked_option_dataclass(self) -> None:
        """RankedOption should be a dataclass with provider, model, total_cost,
        value_score, explanation."""
        cost_calculator.RankedOption(
            provider="openai",
            model="gpt-4",
            total_cost=0.06,
            value_score=8.5,
            explanation="Good balance of quality and cost",
        )

    def test_task_profile_dataclass(self) -> None:
        """TaskProfile should be a dataclass with all fields."""
        cost_calculator.TaskProfile(
            name="coding",
            quality_weight=0.6,
            cost_weight=0.3,
            speed_weight=0.1,
            min_quality_score=0.7,
        )

    def test_all_9_providers_supported(self) -> None:
        """Calculate cost for all 9 supported providers without error."""
        providers = [
            "openai",
            "anthropic",
            "deepseek",
            "openrouter",
            "mimo",
            "gemini",
            "mistral",
            "cohere",
            "ollama",
        ]
        for provider in providers:
            cost_calculator.calculate_cost(1000, 500, provider)


# ===================================================================
# Behavioral tests — all FAIL with NotImplementedError
# ===================================================================


class TestCostCalculatorBehavioral:
    """Define expected cost calculation behavior — all fail RED phase."""

    def test_calculate_cost_basic(self) -> None:
        """openai/gpt-4, 1000 in + 500 out should return $0.06."""
        result = cost_calculator.calculate_cost(1000, 500, "openai", "gpt-4")
        assert result == 0.06, f"Expected 0.06, got {result}"

    @pytest.mark.parametrize(
        ("provider", "model", "input_tokens", "output_tokens", "expected_cost"),
        [
            ("openai", "gpt-4", 1000, 500, 0.06),
            ("anthropic", "claude-4-sonnet", 2000, 1000, 0.021),
            ("deepseek", "deepseek-v3", 1500, 750, 0.0042),
            ("gemini", "gemini-2.5-flash", 5000, 2000, 0.000975),
            ("mistral", "mistral-large-latest", 1000, 500, 0.01),
        ],
    )
    def test_calculate_cost_all_providers(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        expected_cost: float,
    ) -> None:
        """Each provider/model combination should compute the correct cost."""
        result = cost_calculator.calculate_cost(
            input_tokens, output_tokens, provider, model
        )
        assert abs(result - expected_cost) < 0.0001, (
            f"{provider}/{model}: expected {expected_cost}, got {result}"
        )

    def test_calculate_cost_zero_tokens(self) -> None:
        """Zero input and output tokens should return 0.0."""
        result = cost_calculator.calculate_cost(0, 0, "openai", "gpt-4")
        assert result == 0.0, f"Expected 0.0, got {result}"

    def test_calculate_cost_negative_tokens(self) -> None:
        """Negative tokens should raise ValueError."""
        with pytest.raises(ValueError):
            cost_calculator.calculate_cost(-100, 0, "openai", "gpt-4")
        with pytest.raises(ValueError):
            cost_calculator.calculate_cost(0, -100, "openai", "gpt-4")

    def test_calculate_cost_unknown_provider(self) -> None:
        """Unknown provider should raise ValueError with known providers list."""
        with pytest.raises(ValueError) as excinfo:
            cost_calculator.calculate_cost(100, 100, "nonexistent_provider")
        error_msg = str(excinfo.value).lower()
        # The error message should mention known providers
        assert any(
            p in error_msg for p in ["openai", "anthropic", "deepseek", "openrouter"]
        ), f"Error should list known providers: {error_msg}"

    def test_calculate_cost_unknown_model(self) -> None:
        """Unknown model should fall back to provider default model (not raise)."""
        result = cost_calculator.calculate_cost(
            1000, 500, "openai", "nonexistent-model-99"
        )
        # Should return a reasonable cost, not raise
        assert result >= 0.0

    def test_compare_all_returns_sorted(self) -> None:
        """compare_all should return cheapest option first."""
        results = cost_calculator.compare_all(1000, 500, "general")
        assert len(results) >= 1
        costs = [r.get("total_cost", 0.0) for r in results]
        assert costs == sorted(costs), (
            f"Results not sorted by cost: {costs}"
        )

    def test_compare_all_zero_tokens(self) -> None:
        """compare_all with zero tokens should return all options at $0.00."""
        results = cost_calculator.compare_all(0, 0)
        for r in results:
            assert r.get("total_cost", -1) == 0.0, (
                f"Expected cost 0.0, got {r.get('total_cost')}"
            )

    def test_compare_all_providers_filter(self) -> None:
        """compare_all with providers filter should only return specified providers."""
        results = cost_calculator.compare_all(
            1000, 500, providers=["openai", "anthropic"]
        )
        for r in results:
            assert r.get("provider") in ("openai", "anthropic"), (
                f"Unexpected provider: {r.get('provider')}"
            )

    def test_recommend_for_task_coding(self) -> None:
        """recommend_for_task should return ranked recommendations."""
        results = cost_calculator.recommend_for_task(1000, 500, "coding")
        assert len(results) >= 1
        for r in results:
            assert "provider" in r
            assert "model" in r
            assert "value_score" in r
            assert isinstance(r.get("value_score", -1), (int, float))
            assert 0 <= r.get("value_score", -1) <= 10

    def test_recommend_for_task_unknown_type(self) -> None:
        """Unknown task type should fall back to 'general' profile (not raise)."""
        results = cost_calculator.recommend_for_task(1000, 500, "made_up_task_type")
        assert len(results) >= 1

    def test_recommend_for_task_zero_tokens(self) -> None:
        """recommend_for_task should work with zero tokens."""
        results = cost_calculator.recommend_for_task(0, 0, "general")
        assert len(results) >= 1
        # All should be at $0.00 cost
        for r in results:
            assert r.get("total_cost", -1) == 0.0

    def test_recommend_for_task_providers_filter(self) -> None:
        """recommend_for_task should only consider specified providers."""
        results = cost_calculator.recommend_for_task(
            1000, 500, "general", providers=["openai", "anthropic"]
        )
        for r in results:
            assert r.get("provider") in ("openai", "anthropic"), (
                f"Unexpected provider: {r.get('provider')}"
            )


# ===================================================================
# Cost profiles JSON tests — fail because file doesn't exist yet
# ===================================================================


class TestCostProfiles:
    """Validate cost_profiles.json structure — fails RED phase."""

    COST_PROFILES_PATH = _REPO_ROOT / "src" / "ai_vibe_coding" / "cost_profiles.json"

    def test_cost_profiles_valid_json(self) -> None:
        """cost_profiles.json should parse as valid JSON."""
        data = json.loads(self.COST_PROFILES_PATH.read_text())
        assert isinstance(data, dict), "Top level must be a dict"
        assert len(data) > 0, "Must not be empty"

    def test_cost_profiles_5_types(self) -> None:
        """Should contain 5 task types: coding, chat, analysis, translation, general."""
        data = json.loads(self.COST_PROFILES_PATH.read_text())
        task_types = {"coding", "chat", "analysis", "translation", "general"}
        assert task_types.issubset(set(data.keys())), (
            "Missing task types. Expected at least "
            f"{task_types}, got {set(data.keys())}"
        )

    def test_cost_profiles_weights_sum_to_1(self) -> None:
        """Each profile's quality_cost_speed weights should sum to 1.0."""
        data = json.loads(self.COST_PROFILES_PATH.read_text())
        for name, profile in data.items():
            weights = [
                profile.get(k, 0.0)
                for k in ("quality_weight", "cost_weight", "speed_weight")
            ]
            total = sum(weights)
            assert abs(total - 1.0) < 0.001, (
                f"Profile '{name}' weights sum to {total}, expected 1.0"
            )

    def test_cost_profiles_quality_score_range(self) -> None:
        """All min_quality_score values should be between 0 and 1."""
        data = json.loads(self.COST_PROFILES_PATH.read_text())
        for name, profile in data.items():
            score = profile.get("min_quality_score")
            assert score is not None, f"Profile '{name}' missing min_quality_score"
            assert 0 <= score <= 1, (
                f"Profile '{name}' min_quality_score is {score}, "
                "expected between 0 and 1"
            )


# ===================================================================
# CLI subcommand tests — fail because cost subcommands not registered
# ===================================================================


class TestCLICostSubcommands:
    """Verify cost subcommands are registered in argparse — fails RED phase."""

    def test_cli_cost_estimate_subcommand(self) -> None:
        """'ai-vibe-bench cost estimate' subcommand should be registered in argparse."""
        saved_argv = sys.argv
        try:
            sys.argv = ["ai-vibe-bench", "cost", "estimate"]
            cli.main()
        finally:
            sys.argv = saved_argv

    def test_cli_cost_compare_subcommand(self) -> None:
        """'ai-vibe-bench cost compare' subcommand should be registered in argparse."""
        saved_argv = sys.argv
        try:
            sys.argv = ["ai-vibe-bench", "cost", "compare"]
            cli.main()
        finally:
            sys.argv = saved_argv

    def test_cli_cost_recommend_subcommand(self) -> None:
        """'ai-vibe-bench cost recommend' subcommand registered in argparse."""
        saved_argv = sys.argv
        try:
            sys.argv = ["ai-vibe-bench", "cost", "recommend"]
            cli.main()
        finally:
            sys.argv = saved_argv

    def test_cli_cost_pricing_subcommand(self) -> None:
        """'ai-vibe-bench cost pricing' subcommand should be registered in argparse."""
        saved_argv = sys.argv
        try:
            sys.argv = ["ai-vibe-bench", "cost", "pricing"]
            cli.main()
        finally:
            sys.argv = saved_argv


# ===================================================================
# Coverage edge cases (developer-added for 100% line coverage)
# ===================================================================


class TestCoverageEdgeCases:
    """Coverage for defensive branches not hit by normal tests."""

    def test_compare_all_unknown_provider_filter(self) -> None:
        """compare_all with a provider not in PRICING should skip it gracefully."""
        results = cost_calculator.compare_all(
            1000, 500, providers=["unknown_provider"]
        )
        assert results == []

    def test_recommend_for_task_unknown_provider_filter(self) -> None:
        """recommend_for_task with unknown provider should return empty."""
        results = cost_calculator.recommend_for_task(
            100, 100, "general", providers=["unknown_provider"]
        )
        assert results == []
