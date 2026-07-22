"""Interface and behavioral tests for OllamaProvider.

Interface tests verify the API surface (must pass immediately against stubs).
Behavioral tests verify expected behavior using mocked SDK calls.

OllamaProvider extends the standard LLM provider interface with additional
methods: generate() for non-chat completions, and embed() for local embeddings.
Cost is zero since Ollama runs locally.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ai_vibe_coding.provider_examples import OllamaProvider

# ──────────────────────────────────────────────────────────────
# Interface smoke tests (should PASS against stubs)
# ──────────────────────────────────────────────────────────────


class TestOllamaInterfaceSmoke:
    """Verify that OllamaProvider exists with the correct API surface."""

    def test_import_ollama_provider(self):
        """OllamaProvider should be importable."""
        assert OllamaProvider is not None

    def test_ollama_provider_extends_llm_provider(self):
        """OllamaProvider should be a subclass of LLMProvider."""
        from ai_vibe_coding.llm_wrapper import LLMProvider

        assert issubclass(OllamaProvider, LLMProvider)

    def test_constructor_defaults(self):
        """Default model should be gemma3, host should be localhost:11434."""
        provider = OllamaProvider()
        assert provider.model == "gemma3"
        assert provider.host == "http://localhost:11434"

    def test_constructor_custom_host_and_model(self):
        """Provider should accept custom host and model."""
        provider = OllamaProvider(host="http://ollama:11434", model="llama3")
        assert provider.host == "http://ollama:11434"
        assert provider.model == "llama3"

    def test_constructor_custom_host_only(self):
        """Provider should accept custom host with default model."""
        provider = OllamaProvider(host="https://ollama.example.com")
        assert provider.host == "https://ollama.example.com"
        assert provider.model == "gemma3"

    def test_chat_method_exists(self):
        """chat() method should exist with correct signature."""
        assert hasattr(OllamaProvider, "chat")
        import inspect

        sig = inspect.signature(OllamaProvider.chat)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "messages" in params
        assert "model" in params

    def test_stream_method_exists(self):
        """stream() method should exist with correct signature."""
        assert hasattr(OllamaProvider, "stream")
        import inspect

        sig = inspect.signature(OllamaProvider.stream)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "messages" in params
        assert "model" in params

    def test_generate_method_exists(self):
        """generate() method should exist."""
        assert hasattr(OllamaProvider, "generate")

    def test_embed_method_exists(self):
        """embed() method should exist."""
        assert hasattr(OllamaProvider, "embed")

    def test_get_cost_method_exists(self):
        """get_cost() method should exist."""
        assert hasattr(OllamaProvider, "get_cost")

    def test_get_model_list_method_exists(self):
        """get_model_list() method should exist."""
        assert hasattr(OllamaProvider, "get_model_list")

    def test_chat_method_type_hints(self):
        """chat() should have correct type hints."""
        import typing

        hints = typing.get_type_hints(OllamaProvider.chat)
        assert "messages" in hints
        assert "return" in hints
        assert "LLMResponse" in str(hints["return"])

    def test_stream_method_type_hints(self):
        """stream() should return Iterator[str]."""
        import typing

        hints = typing.get_type_hints(OllamaProvider.stream)
        return_hint = hints["return"]
        assert "Iterator" in str(return_hint) or "str" in str(return_hint)

    def test_generate_method_signature(self):
        """generate() should accept prompt, model."""
        import inspect

        sig = inspect.signature(OllamaProvider.generate)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "prompt" in params
        assert "model" in params

    def test_embed_method_signature(self):
        """embed() should accept input_text, model."""
        import inspect

        sig = inspect.signature(OllamaProvider.embed)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "input_text" in params
        assert "model" in params


# ──────────────────────────────────────────────────────────────
# Behavioral tests (mocked SDK calls)
# ──────────────────────────────────────────────────────────────


class TestOllamaBehavioral:
    """Behavioral tests — verify real behavior with mocked SDK calls."""

    @patch("ollama.Client")
    def test_chat_calls_client_chat(self, mock_cls):
        """chat() should call ollama chat with correct model and messages."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = {
            "message": {"content": "Hello from Ollama!"},
            "prompt_eval_count": 10,
            "eval_count": 5,
        }
        mock_client.chat.return_value = mock_response

        provider = OllamaProvider()
        result = provider.chat([{"role": "user", "content": "Hi"}])

        mock_client.chat.assert_called_once()
        assert result.content == "Hello from Ollama!"
        assert result.provider == "ollama"
        assert result.model == "gemma3"
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.tokens_used == 15
        assert result.cost_usd == 0.0
        assert result.latency_ms >= 0

    @patch("ollama.Client")
    def test_chat_uses_custom_model(self, mock_cls):
        """chat() should use custom model when provided."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = {
            "message": {"content": "Response"},
            "prompt_eval_count": 5,
            "eval_count": 3,
        }
        mock_client.chat.return_value = mock_response

        provider = OllamaProvider()
        result = provider.chat(
            [{"role": "user", "content": "Hi"}], model="llama3"
        )

        call_kwargs = mock_client.chat.call_args
        assert call_kwargs.kwargs["model"] == "llama3"
        assert result.model == "llama3"

    @patch("ollama.Client")
    def test_chat_handles_missing_token_counts(self, mock_cls):
        """chat() should handle missing token counts gracefully."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = {"message": {"content": "OK"}}
        mock_client.chat.return_value = mock_response

        provider = OllamaProvider()
        result = provider.chat([{"role": "user", "content": "Hi"}])

        assert result.content == "OK"
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    @patch("ollama.Client")
    def test_chat_raises_on_sdk_error(self, mock_cls):
        """chat() should raise RuntimeError on SDK errors."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.side_effect = Exception("Ollama error")

        provider = OllamaProvider()
        with pytest.raises(RuntimeError, match="OllamaProvider.chat\\(\\) failed"):
            provider.chat([{"role": "user", "content": "Hi"}])

    @patch("ollama.Client")
    def test_chat_uses_custom_host(self, mock_cls):
        """chat() should create client with custom host."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = {
            "message": {"content": "Hi"},
            "prompt_eval_count": 1,
            "eval_count": 1,
        }
        mock_client.chat.return_value = mock_response

        provider = OllamaProvider(host="http://remote:11434")
        provider.chat([{"role": "user", "content": "Hi"}])

        mock_cls.assert_called_with(host="http://remote:11434")

    @patch("ollama.Client")
    def test_stream_yields_chunks(self, mock_cls):
        """stream() should yield content from each chunk."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        chunk1 = {"message": {"content": "Hello"}}
        chunk2 = {"message": {"content": " World"}}
        mock_client.chat.return_value = [chunk1, chunk2]

        provider = OllamaProvider()
        result = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert result == ["Hello", " World"]

    @patch("ollama.Client")
    def test_stream_uses_custom_model(self, mock_cls):
        """stream() should use custom model when provided."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        chunk = {"message": {"content": "Hi"}}
        mock_client.chat.return_value = [chunk]

        provider = OllamaProvider()
        list(provider.stream([{"role": "user", "content": "Hi"}], model="llama3"))

        call_kwargs = mock_client.chat.call_args
        assert call_kwargs.kwargs["model"] == "llama3"
        assert call_kwargs.kwargs["stream"] is True

    @patch("ollama.Client")
    def test_stream_raises_on_sdk_error(self, mock_cls):
        """stream() should raise RuntimeError on SDK errors."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.side_effect = Exception("Stream error")

        provider = OllamaProvider()
        with pytest.raises(RuntimeError, match="OllamaProvider.stream\\(\\) failed"):
            list(provider.stream([{"role": "user", "content": "Hi"}]))

    @patch("ollama.Client")
    def test_generate_returns_response(self, mock_cls):
        """generate() should return the response text."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = {"response": "Once upon a time..."}
        mock_client.generate.return_value = mock_response

        provider = OllamaProvider()
        result = provider.generate("Tell me a story")

        mock_client.generate.assert_called_once()
        assert result == "Once upon a time..."

    @patch("ollama.Client")
    def test_generate_uses_custom_model(self, mock_cls):
        """generate() should use custom model when provided."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = {"response": "OK"}
        mock_client.generate.return_value = mock_response

        provider = OllamaProvider()
        result = provider.generate("Hi", model="llama3")

        call_kwargs = mock_client.generate.call_args
        assert call_kwargs.kwargs["model"] == "llama3"
        assert result == "OK"

    @patch("ollama.Client")
    def test_generate_raises_on_sdk_error(self, mock_cls):
        """generate() should raise RuntimeError on SDK errors."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.generate.side_effect = Exception("Generate error")

        provider = OllamaProvider()
        with pytest.raises(RuntimeError, match="OllamaProvider.generate\\(\\) failed"):
            provider.generate("Hi")

    @patch("ollama.Client")
    def test_embed_returns_single_vector(self, mock_cls):
        """embed() should return a single vector for a string input."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = {"embeddings": [[0.1, 0.2, 0.3]]}
        mock_client.embed.return_value = mock_response

        provider = OllamaProvider()
        result = provider.embed("text to embed")

        mock_client.embed.assert_called_once()
        assert result == [0.1, 0.2, 0.3]

    @patch("ollama.Client")
    def test_embed_returns_multiple_vectors(self, mock_cls):
        """embed() should return list of vectors for a list input."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
        mock_client.embed.return_value = mock_response

        provider = OllamaProvider()
        result = provider.embed(["text one", "text two"])

        assert result == [[0.1, 0.2], [0.3, 0.4]]

    @patch("ollama.Client")
    def test_embed_uses_custom_model(self, mock_cls):
        """embed() should use custom model when provided."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = {"embeddings": [[0.1]]}
        mock_client.embed.return_value = mock_response

        provider = OllamaProvider()
        provider.embed("text", model="llama3")

        call_kwargs = mock_client.embed.call_args
        assert call_kwargs.kwargs["model"] == "llama3"

    @patch("ollama.Client")
    def test_embed_raises_on_sdk_error(self, mock_cls):
        """embed() should raise RuntimeError on SDK errors."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.embed.side_effect = Exception("Embed error")

        provider = OllamaProvider()
        with pytest.raises(RuntimeError, match="OllamaProvider.embed\\(\\) failed"):
            provider.embed("text")

    @patch("ollama.Client")
    def test_embed_passes_list_input(self, mock_cls):
        """embed() should pass list input directly to SDK."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = {"embeddings": [[0.1], [0.2]]}
        mock_client.embed.return_value = mock_response

        provider = OllamaProvider()
        provider.embed(["text1", "text2"])

        call_kwargs = mock_client.embed.call_args
        assert call_kwargs.kwargs["input"] == ["text1", "text2"]


# ──────────────────────────────────────────────────────────────
# Behavioral tests that should PASS (cost is zero, model list works)
# ──────────────────────────────────────────────────────────────


class TestOllamaCostAndModels:
    """Cost calculation returns zero for local inference; model list works."""

    def test_get_cost_returns_zero(self):
        """get_cost() should return 0.0 since Ollama runs locally."""
        provider = OllamaProvider()
        cost = provider.get_cost(input_tokens=10000, output_tokens=5000)
        assert cost == 0.0

    def test_get_cost_always_zero(self):
        """get_cost() should return 0.0 regardless of token count."""
        provider = OllamaProvider()
        assert provider.get_cost(input_tokens=0, output_tokens=0) == 0.0
        assert provider.get_cost(input_tokens=1000, output_tokens=500) == 0.0
        assert provider.get_cost(input_tokens=100000, output_tokens=50000) == 0.0

    def test_get_model_list_returns_list(self):
        """get_model_list() should return a list of model names."""
        provider = OllamaProvider()
        models = provider.get_model_list()
        assert isinstance(models, list)
        assert len(models) > 0
        assert all(isinstance(m, str) for m in models)
        assert "gemma3" in models
        assert "llama3" in models


def test_ollama_provider_instantiable():
    """OllamaProvider can be instantiated without arguments."""
    provider = OllamaProvider()
    assert provider is not None
    assert provider.host == "http://localhost:11434"
    assert provider.model == "gemma3"


@pytest.mark.parametrize(
    "model_name",
    [
        "gemma3",
        "llama3",
        "mistral",
        "phi4",
    ],
)
def test_ollama_provider_known_models(model_name):
    """Known Ollama models should be in the model list."""
    provider = OllamaProvider(model=model_name)
    models = provider.get_model_list()
    assert model_name in models
