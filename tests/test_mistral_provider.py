"""Interface and behavioral tests for MistralProvider.

Interface tests verify the API surface (must pass immediately against stubs).
Behavioral tests verify expected behavior using mocked SDK calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ai_vibe_coding.provider_examples import MistralProvider

# ──────────────────────────────────────────────────────────────
# Interface smoke tests (should PASS against stubs)
# ──────────────────────────────────────────────────────────────


class TestMistralInterfaceSmoke:
    """Verify that MistralProvider exists with the correct API surface."""

    def test_import_mistral_provider(self):
        """MistralProvider should be importable."""
        assert MistralProvider is not None

    def test_mistral_provider_extends_llm_provider(self):
        """MistralProvider should be a subclass of LLMProvider."""
        from ai_vibe_coding.llm_wrapper import LLMProvider

        assert issubclass(MistralProvider, LLMProvider)

    def test_constructor_defaults(self):
        """Default model should be mistral-large-latest."""
        provider = MistralProvider(api_key="fake-key")
        assert provider.model == "mistral-large-latest"

    def test_constructor_custom_model(self):
        """Provider should accept a custom model name."""
        provider = MistralProvider(api_key="fake-key", model="mistral-small-latest")
        assert provider.model == "mistral-small-latest"

    def test_constructor_api_key_stored(self):
        """API key should be stored as instance attribute."""
        provider = MistralProvider(api_key="test-key-456")
        assert provider.api_key == "test-key-456"

    def test_chat_method_exists(self):
        """chat() method should exist with correct signature."""
        assert hasattr(MistralProvider, "chat")
        import inspect

        sig = inspect.signature(MistralProvider.chat)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "messages" in params
        assert "model" in params

    def test_stream_method_exists(self):
        """stream() method should exist with correct signature."""
        assert hasattr(MistralProvider, "stream")
        import inspect

        sig = inspect.signature(MistralProvider.stream)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "messages" in params
        assert "model" in params

    def test_get_cost_method_exists(self):
        """get_cost() method should exist."""
        assert hasattr(MistralProvider, "get_cost")

    def test_get_model_list_method_exists(self):
        """get_model_list() method should exist."""
        assert hasattr(MistralProvider, "get_model_list")

    def test_chat_method_type_hints(self):
        """chat() should have correct type hints."""
        import typing

        hints = typing.get_type_hints(MistralProvider.chat)
        assert "messages" in hints
        assert "return" in hints
        assert "LLMResponse" in str(hints["return"])

    def test_stream_method_type_hints(self):
        """stream() should return Iterator[str]."""
        import typing

        hints = typing.get_type_hints(MistralProvider.stream)
        return_hint = hints["return"]
        assert "Iterator" in str(return_hint) or "str" in str(return_hint)


# ──────────────────────────────────────────────────────────────
# Behavioral tests (mocked SDK calls)
# ──────────────────────────────────────────────────────────────


class TestMistralBehavioral:
    """Behavioral tests — verify real behavior with mocked SDK calls."""

    @patch("mistralai.client.Mistral")
    def test_chat_calls_complete(self, mock_cls):
        """chat() should call chat.complete with correct model and messages."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello from Mistral!"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_client.chat.complete.return_value = mock_response

        provider = MistralProvider(api_key="fake-key")
        result = provider.chat([{"role": "user", "content": "Hi"}])

        mock_client.chat.complete.assert_called_once()
        assert result.content == "Hello from Mistral!"
        assert result.provider == "mistral"
        assert result.model == "mistral-large-latest"
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.tokens_used == 15
        assert result.latency_ms >= 0

    @patch("mistralai.client.Mistral")
    def test_chat_uses_custom_model(self, mock_cls):
        """chat() should use custom model when provided."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 3
        mock_client.chat.complete.return_value = mock_response

        provider = MistralProvider(api_key="fake-key")
        result = provider.chat(
            [{"role": "user", "content": "Hi"}], model="mistral-small-latest"
        )

        call_kwargs = mock_client.chat.complete.call_args
        assert call_kwargs.kwargs["model"] == "mistral-small-latest"
        assert result.model == "mistral-small-latest"

    @patch("mistralai.client.Mistral")
    def test_chat_handles_none_content(self, mock_cls):
        """chat() should handle None content gracefully."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.usage.prompt_tokens = 0
        mock_response.usage.completion_tokens = 0
        mock_client.chat.complete.return_value = mock_response

        provider = MistralProvider(api_key="fake-key")
        result = provider.chat([{"role": "user", "content": "Hi"}])

        assert result.content == ""

    @patch("mistralai.client.Mistral")
    def test_chat_raises_on_sdk_error(self, mock_cls):
        """chat() should raise RuntimeError on SDK errors."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.complete.side_effect = Exception("API error")

        provider = MistralProvider(api_key="fake-key")
        with pytest.raises(RuntimeError, match="MistralProvider.chat\\(\\) failed"):
            provider.chat([{"role": "user", "content": "Hi"}])

    @patch("mistralai.client.Mistral")
    def test_stream_yields_deltas(self, mock_cls):
        """stream() should yield delta content from stream events."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        event1 = MagicMock()
        event1.data.choices = [MagicMock()]
        event1.data.choices[0].delta.content = "Hello"
        event2 = MagicMock()
        event2.data.choices = [MagicMock()]
        event2.data.choices[0].delta.content = " World"
        event3 = MagicMock()
        event3.data.choices = [MagicMock()]
        event3.data.choices[0].delta.content = None

        mock_client.chat.stream.return_value = [event1, event2, event3]

        provider = MistralProvider(api_key="fake-key")
        result = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert result == ["Hello", " World"]

    @patch("mistralai.client.Mistral")
    def test_stream_uses_custom_model(self, mock_cls):
        """stream() should use custom model when provided."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        event = MagicMock()
        event.data.choices = [MagicMock()]
        event.data.choices[0].delta.content = "Hi"
        mock_client.chat.stream.return_value = [event]

        provider = MistralProvider(api_key="fake-key")
        list(
            provider.stream(
                [{"role": "user", "content": "Hi"}], model="mistral-small-latest"
            )
        )

        call_kwargs = mock_client.chat.stream.call_args
        assert call_kwargs.kwargs["model"] == "mistral-small-latest"

    @patch("mistralai.client.Mistral")
    def test_stream_raises_on_sdk_error(self, mock_cls):
        """stream() should raise RuntimeError on SDK errors."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.stream.side_effect = Exception("Stream error")

        provider = MistralProvider(api_key="fake-key")
        with pytest.raises(RuntimeError, match="MistralProvider.stream\\(\\) failed"):
            list(provider.stream([{"role": "user", "content": "Hi"}]))

    @patch("mistralai.client.Mistral")
    def test_chat_passes_messages_correctly(self, mock_cls):
        """chat() should pass messages list directly to SDK."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "OK"
        mock_response.usage.prompt_tokens = 1
        mock_response.usage.completion_tokens = 1
        mock_client.chat.complete.return_value = mock_response

        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hi"},
        ]
        provider = MistralProvider(api_key="fake-key")
        provider.chat(messages)

        call_kwargs = mock_client.chat.complete.call_args
        assert call_kwargs.kwargs["messages"] == messages


# ──────────────────────────────────────────────────────────────
# Behavioral tests that should PASS (cost calculation works)
# ──────────────────────────────────────────────────────────────


class TestMistralCostCalculation:
    """Cost and model list methods work from PRICING dict."""

    def test_get_cost_returns_float(self):
        """get_cost() should return a positive float for known models."""
        provider = MistralProvider(api_key="fake-key", model="mistral-large-latest")
        cost = provider.get_cost(input_tokens=1000, output_tokens=500)
        assert isinstance(cost, float)
        assert cost > 0

    def test_get_cost_zero_for_no_tokens(self):
        """get_cost() should return 0.0 for zero tokens."""
        provider = MistralProvider(api_key="fake-key")
        cost = provider.get_cost(input_tokens=0, output_tokens=0)
        assert cost == 0.0

    def test_get_model_list_returns_list(self):
        """get_model_list() should return a list of model names."""
        provider = MistralProvider(api_key="fake-key")
        models = provider.get_model_list()
        assert isinstance(models, list)
        assert len(models) > 0
        assert all(isinstance(m, str) for m in models)
        assert "mistral-large-latest" in models


def test_mistral_provider_instantiable():
    """MistralProvider can be instantiated without an API key."""
    provider = MistralProvider(api_key="fake-key")
    assert provider is not None
    assert provider.api_key == "fake-key"


@pytest.mark.parametrize(
    "model_name",
    [
        "mistral-large-latest",
        "mistral-small-latest",
        "mistral-moderation-latest",
    ],
)
def test_mistral_provider_known_models(model_name):
    """Known Mistral models should be in the model list."""
    provider = MistralProvider(api_key="fake-key", model=model_name)
    models = provider.get_model_list()
    assert model_name in models
