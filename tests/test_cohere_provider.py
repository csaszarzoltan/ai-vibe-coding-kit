"""Interface and behavioral tests for CohereProvider.

Interface tests verify the API surface (must pass immediately against stubs).
Behavioral tests verify expected behavior using mocked SDK calls.

Cohere extends the standard LLM provider interface with additional
methods: embed() and rerank() for RAG workflows.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ai_vibe_coding.provider_examples import CohereProvider

# ──────────────────────────────────────────────────────────────
# Interface smoke tests (should PASS against stubs)
# ──────────────────────────────────────────────────────────────


class TestCohereInterfaceSmoke:
    """Verify that CohereProvider exists with the correct API surface."""

    def test_import_cohere_provider(self):
        """CohereProvider should be importable."""
        assert CohereProvider is not None

    def test_cohere_provider_extends_llm_provider(self):
        """CohereProvider should be a subclass of LLMProvider."""
        from ai_vibe_coding.llm_wrapper import LLMProvider

        assert issubclass(CohereProvider, LLMProvider)

    def test_constructor_defaults(self):
        """Default model should be command-a-plus-05-2026."""
        provider = CohereProvider(api_key="fake-key")
        assert provider.model == "command-a-plus-05-2026"

    def test_constructor_custom_model(self):
        """Provider should accept a custom model name."""
        provider = CohereProvider(api_key="fake-key", model="command-r-plus-08-2024")
        assert provider.model == "command-r-plus-08-2024"

    def test_constructor_api_key_stored(self):
        """API key should be stored as instance attribute."""
        provider = CohereProvider(api_key="cohere-key-789")
        assert provider.api_key == "cohere-key-789"

    def test_chat_method_exists(self):
        """chat() method should exist with correct signature."""
        assert hasattr(CohereProvider, "chat")
        import inspect

        sig = inspect.signature(CohereProvider.chat)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "messages" in params
        assert "model" in params

    def test_stream_method_exists(self):
        """stream() method should exist with correct signature."""
        assert hasattr(CohereProvider, "stream")
        import inspect

        sig = inspect.signature(CohereProvider.stream)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "messages" in params
        assert "model" in params

    def test_embed_method_exists(self):
        """embed() method should exist."""
        assert hasattr(CohereProvider, "embed")

    def test_rerank_method_exists(self):
        """rerank() method should exist."""
        assert hasattr(CohereProvider, "rerank")

    def test_get_cost_method_exists(self):
        """get_cost() method should exist."""
        assert hasattr(CohereProvider, "get_cost")

    def test_get_model_list_method_exists(self):
        """get_model_list() method should exist."""
        assert hasattr(CohereProvider, "get_model_list")

    def test_chat_method_type_hints(self):
        """chat() should have correct type hints."""
        import typing

        hints = typing.get_type_hints(CohereProvider.chat)
        assert "messages" in hints
        assert "return" in hints
        assert "LLMResponse" in str(hints["return"])

    def test_stream_method_type_hints(self):
        """stream() should return Iterator[str]."""
        import typing

        hints = typing.get_type_hints(CohereProvider.stream)
        return_hint = hints["return"]
        assert "Iterator" in str(return_hint) or "str" in str(return_hint)

    def test_embed_method_signature(self):
        """embed() should accept texts list, model, input_type, embedding_types."""
        import inspect

        sig = inspect.signature(CohereProvider.embed)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "texts" in params
        assert "model" in params
        assert "input_type" in params

    def test_rerank_method_signature(self):
        """rerank() should accept query, documents, model, top_n."""
        import inspect

        sig = inspect.signature(CohereProvider.rerank)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "query" in params
        assert "documents" in params
        assert "model" in params
        assert "top_n" in params


# ──────────────────────────────────────────────────────────────
# Behavioral tests (mocked SDK calls)
# ──────────────────────────────────────────────────────────────


class TestCohereBehavioral:
    """Behavioral tests — verify real behavior with mocked SDK calls."""

    @patch("cohere.ClientV2")
    def test_chat_calls_client_chat(self, mock_cls):
        """chat() should call co.chat with correct model and messages."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.message.content = [MagicMock()]
        mock_response.message.content[0].text = "Hello from Cohere!"
        mock_response.usage.tokens.input_tokens = 10
        mock_response.usage.tokens.output_tokens = 5
        mock_client.chat.return_value = mock_response

        provider = CohereProvider(api_key="fake-key")
        result = provider.chat([{"role": "user", "content": "Hi"}])

        mock_client.chat.assert_called_once()
        assert result.content == "Hello from Cohere!"
        assert result.provider == "cohere"
        assert result.model == "command-a-plus-05-2026"
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.tokens_used == 15
        assert result.latency_ms >= 0

    @patch("cohere.ClientV2")
    def test_chat_uses_custom_model(self, mock_cls):
        """chat() should use custom model when provided."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.message.content = [MagicMock()]
        mock_response.message.content[0].text = "Response"
        mock_response.usage.tokens.input_tokens = 5
        mock_response.usage.tokens.output_tokens = 3
        mock_client.chat.return_value = mock_response

        provider = CohereProvider(api_key="fake-key")
        result = provider.chat(
            [{"role": "user", "content": "Hi"}], model="command-r-plus-08-2024"
        )

        call_kwargs = mock_client.chat.call_args
        assert call_kwargs.kwargs["model"] == "command-r-plus-08-2024"
        assert result.model == "command-r-plus-08-2024"

    @patch("cohere.ClientV2")
    def test_chat_handles_empty_content(self, mock_cls):
        """chat() should handle empty content list."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.message.content = []
        mock_response.usage.tokens.input_tokens = 0
        mock_response.usage.tokens.output_tokens = 0
        mock_client.chat.return_value = mock_response

        provider = CohereProvider(api_key="fake-key")
        result = provider.chat([{"role": "user", "content": "Hi"}])

        assert result.content == ""

    @patch("cohere.ClientV2")
    def test_chat_raises_on_sdk_error(self, mock_cls):
        """chat() should raise RuntimeError on SDK errors."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat.side_effect = Exception("API error")

        provider = CohereProvider(api_key="fake-key")
        with pytest.raises(RuntimeError, match="CohereProvider.chat\\(\\) failed"):
            provider.chat([{"role": "user", "content": "Hi"}])

    @patch("cohere.ClientV2")
    def test_stream_yields_content_deltas(self, mock_cls):
        """stream() should yield text from content-delta events."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        event1 = MagicMock()
        event1.type = "content-delta"
        event1.delta.message.content.text = "Hello"

        event2 = MagicMock()
        event2.type = "content-delta"
        event2.delta.message.content.text = " World"

        event3 = MagicMock()
        event3.type = "message-end"

        mock_client.chat_stream.return_value = [event1, event2, event3]

        provider = CohereProvider(api_key="fake-key")
        result = list(provider.stream([{"role": "user", "content": "Hi"}]))

        assert result == ["Hello", " World"]

    @patch("cohere.ClientV2")
    def test_stream_uses_custom_model(self, mock_cls):
        """stream() should use custom model when provided."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        event = MagicMock()
        event.type = "content-delta"
        event.delta.message.content.text = "Hi"
        mock_client.chat_stream.return_value = [event]

        provider = CohereProvider(api_key="fake-key")
        list(
            provider.stream(
                [{"role": "user", "content": "Hi"}], model="command-r-plus-08-2024"
            )
        )

        call_kwargs = mock_client.chat_stream.call_args
        assert call_kwargs.kwargs["model"] == "command-r-plus-08-2024"

    @patch("cohere.ClientV2")
    def test_stream_raises_on_sdk_error(self, mock_cls):
        """stream() should raise RuntimeError on SDK errors."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.chat_stream.side_effect = Exception("Stream error")

        provider = CohereProvider(api_key="fake-key")
        with pytest.raises(RuntimeError, match="CohereProvider.stream\\(\\) failed"):
            list(provider.stream([{"role": "user", "content": "Hi"}]))

    @patch("cohere.ClientV2")
    def test_embed_returns_embeddings(self, mock_cls):
        """embed() should return list of float vectors."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.embeddings.float = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        mock_client.embed.return_value = mock_response

        provider = CohereProvider(api_key="fake-key")
        result = provider.embed(["text one", "text two"])

        mock_client.embed.assert_called_once()
        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    @patch("cohere.ClientV2")
    def test_embed_uses_custom_model(self, mock_cls):
        """embed() should use custom model when provided."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.embeddings.float = [[0.1]]
        mock_client.embed.return_value = mock_response

        provider = CohereProvider(api_key="fake-key")
        provider.embed(["text"], model="embed-v4.0")

        call_kwargs = mock_client.embed.call_args
        assert call_kwargs.kwargs["model"] == "embed-v4.0"

    @patch("cohere.ClientV2")
    def test_embed_passes_input_type(self, mock_cls):
        """embed() should pass input_type parameter."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.embeddings.float = [[0.1]]
        mock_client.embed.return_value = mock_response

        provider = CohereProvider(api_key="fake-key")
        provider.embed(["text"], input_type="search_query")

        call_kwargs = mock_client.embed.call_args
        assert call_kwargs.kwargs["input_type"] == "search_query"

    @patch("cohere.ClientV2")
    def test_embed_raises_on_sdk_error(self, mock_cls):
        """embed() should raise RuntimeError on SDK errors."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.embed.side_effect = Exception("Embed error")

        provider = CohereProvider(api_key="fake-key")
        with pytest.raises(RuntimeError, match="CohereProvider.embed\\(\\) failed"):
            provider.embed(["text"])

    @patch("cohere.ClientV2")
    def test_rerank_returns_sorted_results(self, mock_cls):
        """rerank() should return list of {index, relevance_score, text} dicts."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        result1 = MagicMock()
        result1.index = 1
        result1.relevance_score = 0.95
        result1.document.text = "Paris is the capital."
        result2 = MagicMock()
        result2.index = 0
        result2.relevance_score = 0.3
        result2.document.text = "London is the capital."

        mock_response = MagicMock()
        mock_response.results = [result1, result2]
        mock_client.rerank.return_value = mock_response

        provider = CohereProvider(api_key="fake-key")
        results = provider.rerank(
            query="What is the capital of France?",
            documents=["London is the capital.", "Paris is the capital."],
        )

        mock_client.rerank.assert_called_once()
        assert len(results) == 2
        assert results[0]["index"] == 1
        assert results[0]["relevance_score"] == 0.95
        assert results[0]["text"] == "Paris is the capital."
        assert results[1]["index"] == 0
        assert results[1]["relevance_score"] == 0.3

    @patch("cohere.ClientV2")
    def test_rerank_uses_custom_model_and_top_n(self, mock_cls):
        """rerank() should use custom model and top_n."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        result1 = MagicMock()
        result1.index = 0
        result1.relevance_score = 0.9
        result1.document.text = "doc1"

        mock_response = MagicMock()
        mock_response.results = [result1]
        mock_client.rerank.return_value = mock_response

        provider = CohereProvider(api_key="fake-key")
        provider.rerank(
            query="test",
            documents=["doc1", "doc2"],
            model="rerank-v4.0-pro",
            top_n=1,
        )

        call_kwargs = mock_client.rerank.call_args
        assert call_kwargs.kwargs["model"] == "rerank-v4.0-pro"
        assert call_kwargs.kwargs["top_n"] == 1

    @patch("cohere.ClientV2")
    def test_rerank_raises_on_sdk_error(self, mock_cls):
        """rerank() should raise RuntimeError on SDK errors."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.rerank.side_effect = Exception("Rerank error")

        provider = CohereProvider(api_key="fake-key")
        with pytest.raises(RuntimeError, match="CohereProvider.rerank\\(\\) failed"):
            provider.rerank(query="test", documents=["doc1"])


# ──────────────────────────────────────────────────────────────
# Behavioral tests that should PASS (cost calculation works)
# ──────────────────────────────────────────────────────────────


class TestCohereCostCalculation:
    """Cost and model list methods work from PRICING dict."""

    def test_get_cost_returns_float(self):
        """get_cost() should return a positive float for known models."""
        provider = CohereProvider(api_key="fake-key", model="command-a-plus-05-2026")
        cost = provider.get_cost(input_tokens=1000, output_tokens=500)
        assert isinstance(cost, float)
        assert cost > 0

    def test_get_cost_zero_for_no_tokens(self):
        """get_cost() should return 0.0 for zero tokens."""
        provider = CohereProvider(api_key="fake-key")
        cost = provider.get_cost(input_tokens=0, output_tokens=0)
        assert cost == 0.0

    def test_get_model_list_returns_list(self):
        """get_model_list() should return a list of model names."""
        provider = CohereProvider(api_key="fake-key")
        models = provider.get_model_list()
        assert isinstance(models, list)
        assert len(models) > 0
        assert all(isinstance(m, str) for m in models)
        assert "command-a-plus-05-2026" in models


def test_cohere_provider_instantiable():
    """CohereProvider can be instantiated without an API key."""
    provider = CohereProvider(api_key="fake-key")
    assert provider is not None


@pytest.mark.parametrize(
    "model_name",
    [
        "command-a-plus-05-2026",
        "command-r-plus-08-2024",
        "command-r-08-2024",
    ],
)
def test_cohere_provider_known_models(model_name):
    """Known Cohere models should be in the model list."""
    provider = CohereProvider(api_key="fake-key", model=model_name)
    models = provider.get_model_list()
    assert model_name in models
