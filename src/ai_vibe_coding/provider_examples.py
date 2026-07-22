"""LLM provider implementations for Gemini, Mistral, Cohere, and Ollama.

Each provider extends LLMProvider with the standard interface:
chat(), stream(), get_cost(), get_model_list().

Real implementations call the actual SDKs. Cost calculation and model
listing work from the PRICING dict in llm_wrapper.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

from ai_vibe_coding.llm_wrapper import LLMProvider, LLMResponse  # noqa: TC001

# ──────────────────────────────────────────────────────────────
# GeminiProvider (google-genai SDK)
# ──────────────────────────────────────────────────────────────


class GeminiProvider(LLMProvider):
    """Google Gemini provider via the google-genai SDK.

    Uses the unified google.genai.Client with centralized API surface.
    Requires: pip install google-genai
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash",
    ) -> None:
        """Initialize GeminiProvider.

        Args:
            api_key: Gemini API key. Reads GEMINI_API_KEY or GOOGLE_API_KEY env var.
            model: Model name (default: gemini-2.5-flash).
        """
        import os

        self.api_key = (
            api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        self.model = model

    def _format_contents(self, messages: list[dict[str, str]]) -> str:
        """Convert message list to a prompt string for Gemini."""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"{role}: {content}")
        return "\n".join(parts)

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat completion via Gemini.

        Uses client.models.generate_content() from the google-genai SDK.
        """
        import google.genai as genai

        use_model = model or self.model
        contents = self._format_contents(messages)

        try:
            start = time.time()
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=use_model, contents=contents
            )
            latency_ms = (time.time() - start) * 1000

            content = response.text or ""
            prompt_tokens = (
                getattr(response.usage_metadata, "prompt_token_count", 0)
                or 0
            )
            candidate_tokens = (
                getattr(response.usage_metadata, "candidates_token_count", 0) or 0
            )

            return LLMResponse(
                content=content,
                provider="gemini",
                model=use_model,
                tokens_used=prompt_tokens + candidate_tokens,
                cost_usd=self.get_cost(prompt_tokens, candidate_tokens),
                latency_ms=latency_ms,
                input_tokens=prompt_tokens,
                output_tokens=candidate_tokens,
            )
        except Exception as e:
            raise RuntimeError(f"GeminiProvider.chat() failed: {e}") from e

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Stream a chat completion via Gemini.

        Uses client.models.generate_content_stream() from the google-genai SDK.
        """
        import google.genai as genai

        use_model = model or self.model
        contents = self._format_contents(messages)

        try:
            client = genai.Client(api_key=self.api_key)
            for chunk in client.models.generate_content_stream(
                model=use_model, contents=contents
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            raise RuntimeError(f"GeminiProvider.stream() failed: {e}") from e

    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate Gemini cost from PRICING dict."""
        from ai_vibe_coding.llm_wrapper import PRICING

        pricing = PRICING.get("gemini", {}).get(
            self.model, {"input": 0.0001, "output": 0.0004}
        )
        cost = (input_tokens / 1000 * pricing["input"]) + (
            output_tokens / 1000 * pricing["output"]
        )
        return round(cost, 6)

    def get_model_list(self) -> list[str]:
        """Return list of available Gemini models."""
        from ai_vibe_coding.llm_wrapper import PRICING

        return list(PRICING.get("gemini", {}).keys())


# ──────────────────────────────────────────────────────────────
# MistralProvider (mistralai SDK)
# ──────────────────────────────────────────────────────────────


class MistralProvider(LLMProvider):
    """Mistral AI provider via the mistralai SDK.

    Uses the official Mistral Python client.
    Requires: pip install mistralai
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "mistral-large-latest",
    ) -> None:
        """Initialize MistralProvider.

        Args:
            api_key: Mistral API key. Reads MISTRAL_API_KEY env var.
            model: Model name (default: mistral-large-latest).
        """
        import os

        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        self.model = model

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat completion via Mistral.

        Uses client.chat.complete() from the mistralai SDK.
        """
        from mistralai.client import Mistral

        use_model = model or self.model

        try:
            start = time.time()
            client = Mistral(api_key=self.api_key)
            response = client.chat.complete(model=use_model, messages=messages)
            latency_ms = (time.time() - start) * 1000

            if not response.choices:
                raise RuntimeError("MistralProvider.chat() returned no choices")
            content = response.choices[0].message.content or ""
            prompt_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
            completion_tokens = (
                getattr(response.usage, "completion_tokens", 0) or 0
            )

            return LLMResponse(
                content=content,
                provider="mistral",
                model=use_model,
                tokens_used=prompt_tokens + completion_tokens,
                cost_usd=self.get_cost(prompt_tokens, completion_tokens),
                latency_ms=latency_ms,
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
            )
        except Exception as e:
            raise RuntimeError(f"MistralProvider.chat() failed: {e}") from e

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Stream a chat completion via Mistral.

        Uses client.chat.stream() from the mistralai SDK.
        """
        from mistralai.client import Mistral

        use_model = model or self.model

        try:
            client = Mistral(api_key=self.api_key)
            stream = client.chat.stream(model=use_model, messages=messages)
            for event in stream:
                if event.data.choices and event.data.choices[0].delta.content:
                    yield event.data.choices[0].delta.content
        except Exception as e:
            raise RuntimeError(f"MistralProvider.stream() failed: {e}") from e

    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate Mistral cost from PRICING dict."""
        from ai_vibe_coding.llm_wrapper import PRICING

        pricing = PRICING.get("mistral", {}).get(
            self.model, {"input": 0.003, "output": 0.009}
        )
        cost = (input_tokens / 1000 * pricing["input"]) + (
            output_tokens / 1000 * pricing["output"]
        )
        return round(cost, 6)

    def get_model_list(self) -> list[str]:
        """Return list of available Mistral models."""
        from ai_vibe_coding.llm_wrapper import PRICING

        return list(PRICING.get("mistral", {}).keys())


# ──────────────────────────────────────────────────────────────
# CohereProvider (cohere SDK)
# ──────────────────────────────────────────────────────────────


class CohereProvider(LLMProvider):
    """Cohere provider via the cohere SDK.

    Supports chat, streaming, embeddings, and reranking.
    Requires: pip install cohere
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "command-a-plus-05-2026",
    ) -> None:
        """Initialize CohereProvider.

        Args:
            api_key: Cohere API key. Reads CO_API_KEY env var.
            model: Model name (default: command-a-plus-05-2026).
        """
        import os

        self.api_key = api_key or os.getenv("CO_API_KEY")
        self.model = model

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat completion via Cohere.

        Uses co.chat() from the cohere SDK (ClientV2).
        Supports RAG via the documents parameter.
        """
        import cohere

        use_model = model or self.model

        try:
            start = time.time()
            client = cohere.ClientV2(api_key=self.api_key)
            response = client.chat(model=use_model, messages=messages)
            latency_ms = (time.time() - start) * 1000

            content = ""
            if response.message and response.message.content:
                content = response.message.content[0].text

            prompt_tokens = getattr(response.usage.tokens, "input_tokens", 0) or 0
            output_tokens = getattr(response.usage.tokens, "output_tokens", 0) or 0

            return LLMResponse(
                content=content,
                provider="cohere",
                model=use_model,
                tokens_used=prompt_tokens + output_tokens,
                cost_usd=self.get_cost(prompt_tokens, output_tokens),
                latency_ms=latency_ms,
                input_tokens=prompt_tokens,
                output_tokens=output_tokens,
            )
        except Exception as e:
            raise RuntimeError(f"CohereProvider.chat() failed: {e}") from e

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Stream a chat completion via Cohere.

        Uses co.chat_stream() from the cohere SDK.
        """
        import cohere

        use_model = model or self.model

        try:
            client = cohere.ClientV2(api_key=self.api_key)
            for event in client.chat_stream(model=use_model, messages=messages):
                if event.type == "content-delta":
                    msg = getattr(event.delta, "message", None)
                    content = getattr(msg, "content", None) if msg else None
                    text = getattr(content, "text", None) if content else None
                    if text:
                        yield text
        except Exception as e:
            raise RuntimeError(f"CohereProvider.stream() failed: {e}") from e

    def embed(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        input_type: str = "search_document",
        embedding_types: list[str] | None = None,
    ) -> list[list[float]]:
        """Generate embeddings via Cohere.

        Uses co.embed() from the cohere SDK.
        Supports search_document, search_query, classification, clustering input types.
        """
        import cohere

        use_model = model or self.model

        try:
            client = cohere.ClientV2(api_key=self.api_key)
            response = client.embed(
                model=use_model,
                texts=texts,
                input_type=input_type,
                embedding_types=embedding_types or ["float"],
            )
            return response.embeddings.float
        except Exception as e:
            raise RuntimeError(f"CohereProvider.embed() failed: {e}") from e

    def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        model: str | None = None,
        top_n: int = 5,
    ) -> list[dict[str, Any]]:
        """Rerank documents via Cohere.

        Uses co.rerank() from the cohere SDK.
        Returns list of {index, relevance_score, text} dicts.
        """
        import cohere

        use_model = model or self.model

        try:
            client = cohere.ClientV2(api_key=self.api_key)
            response = client.rerank(
                model=use_model, query=query, documents=documents, top_n=top_n
            )
            return [
                {
                    "index": result.index,
                    "relevance_score": result.relevance_score,
                    "text": result.document.text,
                }
                for result in response.results
            ]
        except Exception as e:
            raise RuntimeError(f"CohereProvider.rerank() failed: {e}") from e

    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate Cohere cost from PRICING dict."""
        from ai_vibe_coding.llm_wrapper import PRICING

        pricing = PRICING.get("cohere", {}).get(
            self.model, {"input": 0.003, "output": 0.015}
        )
        cost = (input_tokens / 1000 * pricing["input"]) + (
            output_tokens / 1000 * pricing["output"]
        )
        return round(cost, 6)

    def get_model_list(self) -> list[str]:
        """Return list of available Cohere models."""
        from ai_vibe_coding.llm_wrapper import PRICING

        return list(PRICING.get("cohere", {}).keys())


# ──────────────────────────────────────────────────────────────
# OllamaProvider (ollama SDK — local models)
# ──────────────────────────────────────────────────────────────


class OllamaProvider(LLMProvider):
    """Ollama/local model provider via the ollama Python SDK.

    Connects to a local (or remote) Ollama server for self-hosted LLMs.
    Requires: pip install ollama, plus a running Ollama server.
    """

    def __init__(
        self,
        host: str | None = None,
        model: str = "gemma3",
    ) -> None:
        """Initialize OllamaProvider.

        Args:
            host: Ollama server URL (default: http://localhost:11434).
            model: Model name (default: gemma3).
        """
        self.host = host or "http://localhost:11434"
        self.model = model

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat completion via a local Ollama model.

        Uses ollama.chat() from the ollama SDK.
        """
        import ollama

        use_model = model or self.model

        try:
            start = time.time()
            client = ollama.Client(host=self.host)
            response = client.chat(model=use_model, messages=messages)
            latency_ms = (time.time() - start) * 1000

            content = response.get("message", {}).get("content", "")
            prompt_tokens = response.get("prompt_eval_count", 0) or 0
            eval_tokens = response.get("eval_count", 0) or 0

            return LLMResponse(
                content=content,
                provider="ollama",
                model=use_model,
                tokens_used=prompt_tokens + eval_tokens,
                cost_usd=0.0,
                latency_ms=latency_ms,
                input_tokens=prompt_tokens,
                output_tokens=eval_tokens,
            )
        except Exception as e:
            raise RuntimeError(f"OllamaProvider.chat() failed: {e}") from e

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Stream a chat completion via Ollama.

        Uses ollama.chat(stream=True) from the ollama SDK.
        """
        import ollama

        use_model = model or self.model

        try:
            client = ollama.Client(host=self.host)
            for chunk in client.chat(model=use_model, messages=messages, stream=True):
                yield chunk["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"OllamaProvider.stream() failed: {e}") from e

    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate a completion via Ollama (non-chat interface).

        Uses ollama.generate() from the ollama SDK.
        """
        import ollama

        use_model = model or self.model

        try:
            client = ollama.Client(host=self.host)
            response = client.generate(model=use_model, prompt=prompt)
            return response["response"]
        except Exception as e:
            raise RuntimeError(f"OllamaProvider.generate() failed: {e}") from e

    def embed(
        self,
        input_text: str | list[str],
        *,
        model: str | None = None,
    ) -> list[float] | list[list[float]]:
        """Generate embeddings via Ollama.

        Uses ollama.embed() from the ollama SDK.
        """
        import ollama

        use_model = model or self.model

        try:
            client = ollama.Client(host=self.host)
            texts = [input_text] if isinstance(input_text, str) else input_text
            response = client.embed(model=use_model, input=texts)
            embeddings = response["embeddings"]
            if isinstance(input_text, str):
                return embeddings[0]
            return embeddings
        except Exception as e:
            raise RuntimeError(f"OllamaProvider.embed() failed: {e}") from e

    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Ollama runs locally — cost is zero.

        Override this if using Ollama Cloud or a paid remote endpoint.
        """
        return 0.0

    def get_model_list(self) -> list[str]:
        """Return list of available models from local Ollama server.

        Returns a default list since listing requires a running server.
        """
        return ["gemma3", "llama3", "mistral", "phi4", "qwen2.5"]


__all__ = [
    "GeminiProvider",
    "MistralProvider",
    "CohereProvider",
    "OllamaProvider",
]
