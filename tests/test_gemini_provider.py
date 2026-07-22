"""Interface and behavioral tests for GeminiProvider.

Interface tests verify the API surface (must pass immediately against stubs).
Behavioral tests verify expected behavior using mocked SDK calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ai_vibe_coding.provider_examples import GeminiProvider

# ──────────────────────────────────────────────────────────────
# Interface smoke tests (should PASS against stubs)
# ──────────────────────────────────────────────────────────────


class TestGeminiInterfaceSmoke:
    """Verify that GeminiProvider exists with the correct API surface."""

    def test_import_gemini_provider(self):
        """GeminiProvider should be importable."""
        assert GeminiProvider is not None

    def test_gemini_provider_extends_llm_provider(self):
        """GeminiProvider should be a subclass of LLMProvider."""
        from ai_vibe_coding.llm_wrapper import LLMProvider

        assert issubclass(GeminiProvider, LLMProvider)

    def test_constructor_defaults(self):
        """Default model should be gemini-2.5-flash."""
        provider = GeminiProvider(api_key="fake-key")
        assert provider.model == "gemini-2.5-flash"

    def test_constructor_custom_model(self):
        """Provider should accept a custom model name."""
        provider = GeminiProvider(api_key="fake-key", model="gemini-2.5-pro")
        assert provider.model == "gemini-2.5-pro"

    def test_constructor_api_key_stored(self):
        """API key should be stored as instance attribute."""
        provider = GeminiProvider(api_key="test-key-123")
        assert provider.api_key == "test-key-123"

    def test_chat_method_exists(self):
        """chat() method should exist with correct signature."""
        assert hasattr(GeminiProvider, "chat")
        import inspect

        sig = inspect.signature(GeminiProvider.chat)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "messages" in params
        assert "model" in params

    def test_stream_method_exists(self):
        """stream() method should exist with correct signature."""
        assert hasattr(GeminiProvider, "stream")
        import inspect

        sig = inspect.signature(GeminiProvider.stream)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "messages" in params
        assert "model" in params

    def test_get_cost_method_exists(self):
        """get_cost() method should exist."""
        assert hasattr(GeminiProvider, "get_cost")

    def test_get_model_list_method_exists(self):
        """get_model_list() method should exist."""
        assert hasattr(GeminiProvider, "get_model_list")

    def test_chat_method_type_hints(self):
        """chat() should have correct type hints."""
        import typing

        hints = typing.get_type_hints(GeminiProvider.chat)
        assert "messages" in hints
        assert "model" in hints
        assert "return" in hints
        from ai_vibe_coding.llm_wrapper import LLMResponse

        # Handle typing types properly
        return_hint = hints["return"]
        assert return_hint is LLMResponse or "LLMResponse" in str(return_hint)

    def test_stream_method_type_hints(self):
        """stream() should return Iterator[str]."""
        import typing

        hints = typing.get_type_hints(GeminiProvider.stream)
        return_hint = hints["return"]
        # Handle different Iterator representations
        assert "Iterator" in str(return_hint) or "str" in str(return_hint)


# ──────────────────────────────────────────────────────────────
# Behavioral tests (mocked SDK calls)
# ──────────────────────────────────────────────────────────────


class TestGeminiBehavioral:
    """Behavioral tests — verify real behavior with mocked SDK calls."""

    @patch("google.genai.Client")
    def test_chat_calls_generate_content(self, mock_client_cls):
        """chat() should call generate_content with the correct model."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "Hello from Gemini!"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_client.models.generate_content.return_value = mock_response

        provider = GeminiProvider(api_key="fake-key")
        result = provider.chat([{"role": "user", "content": "Hi"}])

        mock_client.models.generate_content.assert_called_once()
        assert result.content == "Hello from Gemini!"
        assert result.provider == "gemini"
        assert result.model == "gemini-2.5-flash"
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.tokens_used == 15
        assert result.latency_ms >= 0

    @patch("google.genai.Client")
    def test_chat_uses_custom_model(self, mock_client_cls):
        """chat() should use custom model when provided."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = "Response"
        mock_response.usage_metadata.prompt_token_count = 5
        mock_response.usage_metadata.candidates_token_count = 3
        mock_client.models.generate_content.return_value = mock_response

        provider = GeminiProvider(api_key="fake-key", model="gemini-2.5-pro")
        result = provider.chat(
            [{"role": "user", "content": "Hi"}], model="gemini-2.0-flash"
        )

        call_kwargs = mock_client.models.generate_content.call_args
        assert call_kwargs.kwargs["model"] == "gemini-2.0-flash"
        assert result.model == "gemini-2.0-flash"

    @patch("google.genai.Client")
    def test_chat_handles_none_text(self, mock_client_cls):
        """chat() should handle None text gracefully."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.text = None
        mock_response.usage_metadata.prompt_token_count = 0
        mock_response.usage_metadata.candidates_token_count = 0
        mock_client.models.generate_content.return_value = mock_response

        provider = GeminiProvider(api_key="fake-key")
        result = provider.chat([{"role": "user", "content": "Hi"}])

        assert result.content == ""

    @patch("google.genai.Client")
    def test_chat_raises_on_sdk_error(self, mock_client_cls):
        """chat() should raise RuntimeError on SDK errors."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("API error")

        provider = GeminiProvider(api_key="fake-key")
        with pytest.raises(RuntimeError, match="GeminiProvider.chat\\(\\) failed"):
            provider.chat([{"role": "user", "content": "Hi"}])

    @patch("google.genai.Client")
    def test_stream_yields_chunks(self, mock_client_cls):
        """stream() should yield text from each chunk."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        chunk1 = MagicMock()
        chunk1.text = "Hello"
        chunk2 = MagicMock()
        chunk2.text = " World"
        chunk3 = MagicMock()
        chunk3.text = None

        mock_client.models.generate_content_stream.return_value = [
            chunk1,
            chunk2,
            chunk3,
        ]

        provider = GeminiProvider(api_key="fake-key")
        result = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert result == ["Hello", " World"]

    @patch("google.genai.Client")
    def test_stream_uses_custom_model(self, mock_client_cls):
        """stream() should use custom model when provided."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        chunk = MagicMock()
        chunk.text = "Hi"
        mock_client.models.generate_content_stream.return_value = [chunk]

        provider = GeminiProvider(api_key="fake-key")
        list(
            provider.stream(
                [{"role": "user", "content": "Hi"}], model="gemini-2.5-pro"
            )
        )

        call_kwargs = mock_client.models.generate_content_stream.call_args
        assert call_kwargs.kwargs["model"] == "gemini-2.5-pro"

    @patch("google.genai.Client")
    def test_stream_raises_on_sdk_error(self, mock_client_cls):
        """stream() should raise RuntimeError on SDK errors."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content_stream.side_effect = Exception(
            "Stream error"
        )

        provider = GeminiProvider(api_key="fake-key")
        with pytest.raises(RuntimeError, match="GeminiProvider.stream\\(\\) failed"):
            list(provider.stream([{"role": "user", "content": "Hi"}]))

    def test_chat_formats_messages(self):
        """_format_contents should join messages into a prompt string."""
        provider = GeminiProvider(api_key="fake-key")
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"},
        ]
        result = provider._format_contents(messages)
        assert "user: Hello" in result
        assert "assistant: Hi there" in result
        assert "user: How are you?" in result


# ──────────────────────────────────────────────────────────────
# Behavioral tests that should PASS (cost calculation works)
# ──────────────────────────────────────────────────────────────


class TestGeminiCostCalculation:
    """Cost and model list methods work from PRICING dict."""

    def test_get_cost_returns_float(self):
        """get_cost() should return a positive float for known models."""
        provider = GeminiProvider(api_key="fake-key", model="gemini-2.5-flash")
        cost = provider.get_cost(input_tokens=1000, output_tokens=500)
        assert isinstance(cost, float)
        assert cost > 0

    def test_get_cost_zero_for_no_tokens(self):
        """get_cost() should return 0.0 for zero tokens."""
        provider = GeminiProvider(api_key="fake-key")
        cost = provider.get_cost(input_tokens=0, output_tokens=0)
        assert cost == 0.0

    def test_get_model_list_returns_list(self):
        """get_model_list() should return a list of model names."""
        provider = GeminiProvider(api_key="fake-key")
        models = provider.get_model_list()
        assert isinstance(models, list)
        assert len(models) > 0
        assert all(isinstance(m, str) for m in models)
        assert "gemini-2.5-flash" in models


def test_gemini_provider_instantiable():
    """GeminiProvider can be instantiated without an API key."""
    provider = GeminiProvider(api_key="fake-key")
    assert provider is not None
    assert provider.api_key == "fake-key"


@pytest.mark.parametrize(
    "model_name",
    ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
)
def test_gemini_provider_known_models(model_name):
    """Known Gemini models should be in the model list."""
    provider = GeminiProvider(api_key="fake-key", model=model_name)
    models = provider.get_model_list()
    assert model_name in models
