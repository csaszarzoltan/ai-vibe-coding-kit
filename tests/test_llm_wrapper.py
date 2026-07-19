"""Smoke tests for the LLM API wrapper (TASK-1).

Interface tests verify that the public API exists with correct signatures.
Behavioral tests define the expected pre-states that the developer must
make green by implementing the stubs.

pytest markers:
    @pytest.mark.unit — mocked HTTP, no real API keys needed
    @pytest.mark.integration — requires real API keys (skipped without)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ai_vibe_coding.llm_wrapper import (
    PRICING,
    AnthropicProvider,
    DeepSeekProvider,
    LLMClient,
    LLMProvider,
    LLMResponse,
    MiMoProvider,
    OpenAIProvider,
    OpenRouterProvider,
)

# ──────────────────────────────────────────────────────────────
# Interface smoke tests (should pass — verify API surface exists)
# ──────────────────────────────────────────────────────────────


class TestInterfaceSmoke:
    """Verify that all classes, methods, and dataclasses exist."""

    def test_llm_response_is_dataclass(self):
        """LLMResponse should be instantiable with required fields."""
        resp = LLMResponse(
            content="hello",
            provider="openai",
            model="gpt-4",
            tokens_used=10,
            cost_usd=0.001,
            latency_ms=50.0,
        )
        assert resp.content == "hello"
        assert resp.provider == "openai"
        assert resp.input_tokens == 0  # default
        assert resp.output_tokens == 0  # default

    def test_llm_response_has_optional_fields(self):
        """LLMResponse should have input_tokens, output_tokens, raw fields."""
        resp = LLMResponse(
            content="",
            provider="",
            model="",
            tokens_used=0,
            cost_usd=0.0,
            latency_ms=0.0,
            input_tokens=5,
            output_tokens=10,
            raw={"key": "val"},
        )
        assert resp.input_tokens == 5
        assert resp.output_tokens == 10
        assert resp.raw == {"key": "val"}

    def test_llm_provider_is_abc(self):
        """LLMProvider should be an abstract base class."""
        assert issubclass(OpenAIProvider, LLMProvider)
        assert issubclass(AnthropicProvider, LLMProvider)
        assert issubclass(DeepSeekProvider, LLMProvider)
        assert issubclass(OpenRouterProvider, LLMProvider)
        assert issubclass(MiMoProvider, LLMProvider)

    @pytest.mark.parametrize(
        "provider_class",
        [
            OpenAIProvider,
            AnthropicProvider,
            DeepSeekProvider,
            OpenRouterProvider,
            MiMoProvider,
        ],
    )
    def test_provider_implements_all_abstract_methods(self, provider_class):
        """Each provider must define chat, stream, get_cost, get_model_list."""
        assert hasattr(provider_class, "chat")
        assert hasattr(provider_class, "stream")
        assert hasattr(provider_class, "get_cost")
        assert hasattr(provider_class, "get_model_list")

    def test_llm_client_has_provider_registry(self):
        """LLMClient should support all 5 providers."""
        assert "openai" in LLMClient.PROVIDERS
        assert "anthropic" in LLMClient.PROVIDERS
        assert "deepseek" in LLMClient.PROVIDERS
        assert "openrouter" in LLMClient.PROVIDERS
        assert "mimo" in LLMClient.PROVIDERS
        assert len(LLMClient.PROVIDERS) >= 5

    def test_llm_client_rejects_unknown_provider(self):
        """LLMClient should raise ValueError for unknown provider."""
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMClient(provider="nonexistent")

    def test_llm_client_has_chat_method(self):
        """LLMClient should have chat, chat_async, stream, compare_providers."""
        assert hasattr(LLMClient, "chat")
        assert hasattr(LLMClient, "chat_async")
        assert hasattr(LLMClient, "stream")
        assert hasattr(LLMClient, "compare_providers")

    def test_pricing_dict_has_all_providers(self):
        """PRICING dict should have entries for all 5 providers."""
        for provider in ["openai", "anthropic", "deepseek", "openrouter", "mimo"]:
            assert provider in PRICING, f"Missing pricing for {provider}"

    @pytest.mark.parametrize(
        "provider_class,expected_default_model",
        [
            (OpenAIProvider, "gpt-4"),
            (AnthropicProvider, "claude-4-sonnet"),
            (DeepSeekProvider, "deepseek-v3"),
            (OpenRouterProvider, "openai/gpt-4"),
            (MiMoProvider, "mimo-v2.5"),
        ],
    )
    def test_provider_default_model(self, provider_class, expected_default_model):
        """Each provider should have the expected default model."""
        instance = provider_class(api_key="fake-key")
        assert instance.model == expected_default_model


# ──────────────────────────────────────────────────────────────
# Behavioral pre-state tests (should FAIL until implementation)
# These define the contract the developer must satisfy.
# ──────────────────────────────────────────────────────────────


class TestLLMClientChat:
    """Behavioral tests for LLMClient.chat() — fail until implemented."""

    @pytest.mark.unit
    def test_chat_returns_llm_response(self):
        """chat() should return an LLMResponse object with populated fields."""
        with patch.object(OpenAIProvider, "chat") as mock_chat:
            mock_chat.return_value = LLMResponse(
                content="Hello!",
                provider="openai",
                model="gpt-4",
                tokens_used=15,
                cost_usd=0.0002,
                latency_ms=120.0,
                input_tokens=5,
                output_tokens=10,
            )
            client = LLMClient(provider="openai", api_key="fake")
            resp = client.chat("Hi")

        assert isinstance(resp, LLMResponse)
        assert resp.content == "Hello!"
        assert resp.tokens_used == 15
        assert resp.cost_usd > 0

    @pytest.mark.unit
    def test_chat_with_system_prompt(self):
        """chat() should accept system_prompt and pass it to provider."""
        with patch.object(OpenAIProvider, "chat") as mock_chat:
            mock_chat.return_value = LLMResponse(
                content="ok", provider="openai", model="gpt-4",
                tokens_used=5, cost_usd=0.0001, latency_ms=10.0,
            )
            client = LLMClient(provider="openai", api_key="fake")
            client.chat("Hello", system_prompt="You are helpful")

        # Verify messages list was built with system prompt
        call_args = mock_chat.call_args
        messages = call_args[0][0] if call_args[0] else call_args[1].get("messages", [])
        assert isinstance(messages, list)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"


class TestLLMClientStream:
    """Behavioral tests for stream() — fail until implemented."""

    @pytest.mark.unit
    def test_stream_yields_text_chunks(self):
        """stream() should yield text chunks as a generator."""
        with patch.object(OpenAIProvider, "stream") as mock_stream:
            mock_stream.return_value = iter(["Hello", " world", "!"])
            client = LLMClient(provider="openai", api_key="fake")
            chunks = list(client.stream("Hi"))

        assert chunks == ["Hello", " world", "!"]
        assert len(chunks) == 3


class TestLLMClientAsync:
    """Behavioral tests for chat_async() — fail until implemented."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_async_returns_llm_response(self):
        """chat_async() should return an LLMResponse."""
        with patch.object(OpenAIProvider, "chat") as mock_chat:
            mock_chat.return_value = LLMResponse(
                content="async hello", provider="openai", model="gpt-4",
                tokens_used=5, cost_usd=0.0001, latency_ms=10.0,
            )
            client = LLMClient(provider="openai", api_key="fake")
            resp = await client.chat_async("Hello")

        assert isinstance(resp, LLMResponse)
        assert resp.content == "async hello"


class TestCompareProviders:
    """Behavioral tests for compare_providers() — fail until implemented."""

    @pytest.mark.unit
    def test_compare_providers_returns_dict(self):
        """compare_providers() should return a dict keyed by provider name."""
        client = LLMClient(provider="openai", api_key="fake")
        with patch.object(OpenAIProvider, "chat") as mock_openai_chat:
            mock_openai_chat.return_value = LLMResponse(
                content="resp", provider="openai", model="gpt-4",
                tokens_used=5, cost_usd=0.0001, latency_ms=10.0,
            )
            results = client.compare_providers("test prompt", providers=["openai"])

        assert isinstance(results, dict)
        assert "openai" in results
        assert isinstance(results["openai"], LLMResponse)


class TestProviderCostCalc:
    """Behavioral tests for get_cost() — fail until implemented."""

    @pytest.mark.unit
    def test_openai_cost_calculation(self):
        """OpenAI get_cost() should calculate cost from PRICING dict."""
        provider = OpenAIProvider(api_key="fake")
        cost = provider.get_cost(input_tokens=1000, output_tokens=500)
        assert cost > 0
        # GPT-4: 0.03/1K input + 0.06/1K output
        # 1000 * 0.03/1000 + 500 * 0.06/1000 = 0.03 + 0.03 = 0.06
        assert cost == pytest.approx(0.06, rel=0.01)

    @pytest.mark.unit
    def test_mimo_cost_calculation(self):
        """MiMo get_cost() should calculate cost from PRICING dict."""
        provider = MiMoProvider(api_key="fake")
        cost = provider.get_cost(input_tokens=1000, output_tokens=500)
        assert cost > 0
        # MiMo: 0.0004/1K input + 0.002/1K output
        # 1000 * 0.0004/1000 + 500 * 0.002/1000 = 0.0004 + 0.001 = 0.0014
        assert cost == pytest.approx(0.0014, rel=0.01)


class TestProviderModelList:
    """Behavioral tests for get_model_list() — fail until implemented."""

    @pytest.mark.unit
    def test_openai_model_list(self):
        """OpenAI get_model_list() should return list of model strings."""
        provider = OpenAIProvider(api_key="fake")
        models = provider.get_model_list()
        assert isinstance(models, list)
        assert len(models) > 0
        assert all(isinstance(m, str) for m in models)
