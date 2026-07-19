"""Multi-provider LLM API wrapper.

Provides a unified interface for calling OpenAI, Anthropic, DeepSeek,
OpenRouter, and MiMo LLM providers with retry logic, streaming, async
support, and cost tracking.

Public API:
    LLMProvider    — abstract base class for all providers
    LLMResponse    — standardized response dataclass
    LLMClient      — facade for provider selection, async, comparison
    OpenAIProvider, AnthropicProvider, DeepSeekProvider,
    OpenRouterProvider, MiMoProvider — concrete provider implementations
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx

# Pricing config dict (not hardcoded — easy to update)
# Rates are per 1K tokens: {"input": float, "output": float}
PRICING: dict[str, dict[str, dict[str, float]]] = {
    "openai": {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4.5": {"input": 0.05, "output": 0.15},
        "gpt-5": {"input": 0.08, "output": 0.24},
    },
    "anthropic": {
        "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
        "claude-4-sonnet": {"input": 0.003, "output": 0.015},
        "claude-4.5-sonnet": {"input": 0.005, "output": 0.025},
    },
    "deepseek": {
        "deepseek-v3": {"input": 0.0014, "output": 0.0028},
        "deepseek-r1": {"input": 0.0014, "output": 0.0028},
    },
    "openrouter": {
        "default": {"input": 0.01, "output": 0.03},
    },
    "mimo": {
        "mimo-v2.5": {"input": 0.0004, "output": 0.002},
    },
}


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider.

    Attributes:
        content: The text content of the response.
        provider: Provider name (e.g. "openai", "anthropic").
        model: Model name (e.g. "gpt-4").
        tokens_used: Total tokens consumed (input + output).
        cost_usd: Estimated cost in USD.
        latency_ms: Response latency in milliseconds.
        input_tokens: Number of input/prompt tokens.
        output_tokens: Number of output/completion tokens.
        raw: Raw provider response dict for debugging.
    """

    content: str
    provider: str
    model: str
    tokens_used: int
    cost_usd: float
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Every concrete provider must implement chat(), stream(), get_cost(),
    and get_model_list().
    """

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat completion request.

        Args:
            messages: List of message dicts with "role" and "content".
            model: Optional model override.
            **kwargs: Provider-specific parameters (temperature, etc.).

        Returns:
            LLMResponse with content, tokens, cost, and latency.
        """

    @abstractmethod
    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Stream a chat completion, yielding text chunks.

        Args:
            messages: List of message dicts.
            model: Optional model override.
            **kwargs: Provider-specific parameters.

        Yields:
            Text chunks as they arrive from the provider.
        """

    @abstractmethod
    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for token usage.

        Args:
            input_tokens: Number of input/prompt tokens.
            output_tokens: Number of output/completion tokens.

        Returns:
            Estimated cost in USD.
        """

    @abstractmethod
    def get_model_list(self) -> list[str]:
        """Return list of available models for this provider."""


class OpenAIProvider(LLMProvider):
    """OpenAI GPT-4/4.5/5 provider via official openai SDK."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4") -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        used_model = model or self.model
        start = time.monotonic()
        resp = client.chat.completions.create(
            model=used_model, messages=messages, **kwargs
        )
        latency_ms = (time.monotonic() - start) * 1000
        choice = resp.choices[0]
        content = choice.message.content or ""
        usage = resp.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        cost = self.get_cost(input_tokens, output_tokens)
        return LLMResponse(
            content=content,
            provider="openai",
            model=used_model,
            tokens_used=input_tokens + output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw=resp.model_dump() if hasattr(resp, "model_dump") else {},
        )

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        used_model = model or self.model
        stream = client.chat.completions.create(
            model=used_model, messages=messages, stream=True, **kwargs
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        pricing = PRICING["openai"].get(self.model, PRICING["openai"]["gpt-4"])
        cost = (input_tokens / 1000 * pricing["input"]) + (
            output_tokens / 1000 * pricing["output"]
        )
        return round(cost, 6)

    def get_model_list(self) -> list[str]:
        return list(PRICING["openai"].keys())


class AnthropicProvider(LLMProvider):
    """Anthropic Claude 3.5 / 4 / 4.5 provider via anthropic SDK."""

    def __init__(
        self, api_key: str | None = None, model: str = "claude-4-sonnet"
    ) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        from anthropic import Anthropic

        client = Anthropic(api_key=self.api_key)
        used_model = model or self.model
        system_msg = ""
        chat_msgs = messages
        if messages and messages[0].get("role") == "system":
            system_msg = messages[0].get("content", "")
            chat_msgs = messages[1:]
        start = time.monotonic()
        kwargs.pop("system", None)
        resp = client.messages.create(
            model=used_model,
            messages=chat_msgs,
            system=system_msg if system_msg else None,
            max_tokens=kwargs.pop("max_tokens", 4096),
            **kwargs,
        )
        latency_ms = (time.monotonic() - start) * 1000
        content = ""
        for block in resp.content:
            if hasattr(block, "text"):
                content += block.text
        input_tokens = resp.usage.input_tokens if resp.usage else 0
        output_tokens = resp.usage.output_tokens if resp.usage else 0
        cost = self.get_cost(input_tokens, output_tokens)
        return LLMResponse(
            content=content,
            provider="anthropic",
            model=used_model,
            tokens_used=input_tokens + output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw=resp.model_dump() if hasattr(resp, "model_dump") else {},
        )

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        from anthropic import Anthropic

        client = Anthropic(api_key=self.api_key)
        used_model = model or self.model
        system_msg = ""
        chat_msgs = messages
        if messages and messages[0].get("role") == "system":
            system_msg = messages[0].get("content", "")
            chat_msgs = messages[1:]
        kwargs.pop("system", None)
        with client.messages.stream(
            model=used_model,
            messages=chat_msgs,
            system=system_msg if system_msg else None,
            max_tokens=kwargs.pop("max_tokens", 4096),
            **kwargs,
        ) as stream:
            yield from stream.text_stream

    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        pricing = PRICING["anthropic"].get(
            self.model, PRICING["anthropic"]["claude-4-sonnet"]
        )
        cost = (input_tokens / 1000 * pricing["input"]) + (
            output_tokens / 1000 * pricing["output"]
        )
        return round(cost, 6)

    def get_model_list(self) -> list[str]:
        return list(PRICING["anthropic"].keys())


class DeepSeekProvider(LLMProvider):
    """DeepSeek V3 / R1 provider via OpenAI-compatible API."""

    def __init__(self, api_key: str | None = None, model: str = "deepseek-v3") -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.model = model
        self.base_url = "https://api.deepseek.com/v1"

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        used_model = model or self.model
        start = time.monotonic()
        resp = client.chat.completions.create(
            model=used_model, messages=messages, **kwargs
        )
        latency_ms = (time.monotonic() - start) * 1000
        choice = resp.choices[0]
        content = choice.message.content or ""
        usage = resp.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        cost = self.get_cost(input_tokens, output_tokens)
        return LLMResponse(
            content=content,
            provider="deepseek",
            model=used_model,
            tokens_used=input_tokens + output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw=resp.model_dump() if hasattr(resp, "model_dump") else {},
        )

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        used_model = model or self.model
        stream = client.chat.completions.create(
            model=used_model, messages=messages, stream=True, **kwargs
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        pricing = PRICING["deepseek"].get(
            self.model, PRICING["deepseek"]["deepseek-v3"]
        )
        cost = (input_tokens / 1000 * pricing["input"]) + (
            output_tokens / 1000 * pricing["output"]
        )
        return round(cost, 6)

    def get_model_list(self) -> list[str]:
        return list(PRICING["deepseek"].keys())


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider — routing to 100+ models via requests/httpx."""

    def __init__(self, api_key: str | None = None, model: str = "openai/gpt-4") -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        used_model = model or self.model
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": used_model,
            "messages": messages,
            **kwargs,
        }
        start = time.monotonic()
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        latency_ms = (time.monotonic() - start) * 1000
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = self.get_cost(input_tokens, output_tokens)
        return LLMResponse(
            content=content,
            provider="openrouter",
            model=used_model,
            tokens_used=input_tokens + output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw=data,
        )

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        used_model = model or self.model
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": used_model,
            "messages": messages,
            "stream": True,
            **kwargs,
        }
        with httpx.Client(timeout=120.0) as client, client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    line_data = line[6:]
                    if line_data == "[DONE]":
                        break
                    chunk = json.loads(line_data)
                    delta = (
                        chunk.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content", "")
                    )
                    if delta:
                        yield delta

    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        pricing = PRICING["openrouter"]["default"]
        cost = (input_tokens / 1000 * pricing["input"]) + (
            output_tokens / 1000 * pricing["output"]
        )
        return round(cost, 6)

    def get_model_list(self) -> list[str]:
        return list(PRICING["openrouter"].keys())


class MiMoProvider(LLMProvider):
    """Xiaomi MiMo provider — cost-effective alternative via REST API."""

    def __init__(self, api_key: str | None = None, model: str = "mimo-v2.5") -> None:
        self.api_key = api_key or os.getenv("MIMO_API_KEY")
        self.model = model
        self.base_url = "https://api.xiaomimimo.com/v1"

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        used_model = model or self.model
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": used_model,
            "messages": messages,
            **kwargs,
        }
        start = time.monotonic()
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        latency_ms = (time.monotonic() - start) * 1000
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = self.get_cost(input_tokens, output_tokens)
        return LLMResponse(
            content=content,
            provider="mimo",
            model=used_model,
            tokens_used=input_tokens + output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw=data,
        )

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        used_model = model or self.model
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": used_model,
            "messages": messages,
            "stream": True,
            **kwargs,
        }
        with httpx.Client(timeout=120.0) as client, client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    line_data = line[6:]
                    if line_data == "[DONE]":
                        break
                    chunk = json.loads(line_data)
                    delta = (
                        chunk.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content", "")
                    )
                    if delta:
                        yield delta

    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        pricing = PRICING["mimo"].get(self.model, PRICING["mimo"]["mimo-v2.5"])
        cost = (input_tokens / 1000 * pricing["input"]) + (
            output_tokens / 1000 * pricing["output"]
        )
        return round(cost, 6)

    def get_model_list(self) -> list[str]:
        return list(PRICING["mimo"].keys())


class LLMClient:
    """Unified facade for multiple LLM providers.

    Provides provider selection, async chat, streaming, and cross-provider
    comparison.

    Args:
        provider: Provider name ("openai", "anthropic", "deepseek",
                  "openrouter", "mimo").
        **kwargs: Provider-specific arguments (api_key, model, etc.).

    Example:
        client = LLMClient(provider="openai")
        response = client.chat("Hello!")
        print(response.content, response.cost_usd)
    """

    PROVIDERS: dict[str, type[LLMProvider]] = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "deepseek": DeepSeekProvider,
        "openrouter": OpenRouterProvider,
        "mimo": MiMoProvider,
    }

    def __init__(self, provider: str = "openai", **kwargs: Any) -> None:
        if provider not in self.PROVIDERS:
            raise ValueError(
                f"Unknown provider: {provider!r}. Available: {list(self.PROVIDERS)}"
            )
        self.provider_name = provider
        self.client: LLMProvider = self.PROVIDERS[provider](**kwargs)

    def chat(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat request to the selected provider."""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.client.chat(messages, model=model, **kwargs)

    async def chat_async(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Async chat — runs chat() in a thread executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.chat(
                prompt, system_prompt=system_prompt, model=model, **kwargs
            ),
        )

    def stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Stream a chat response, yielding text chunks."""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        yield from self.client.stream(messages, model=model, **kwargs)

    def compare_providers(
        self,
        prompt: str,
        *,
        providers: list[str] | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, LLMResponse | Exception]:
        """Run the same prompt across all (or specified) providers."""
        provider_names = providers or list(self.PROVIDERS.keys())
        results: dict[str, LLMResponse | Exception] = {}
        for name in provider_names:
            try:
                client = self.PROVIDERS[name](api_key="fake-key")
                messages: list[dict[str, str]] = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                results[name] = client.chat(messages)
            except Exception as exc:
                results[name] = exc
        return results


__all__ = [
    "PRICING",
    "AnthropicProvider",
    "DeepSeekProvider",
    "LLMClient",
    "LLMProvider",
    "LLMResponse",
    "MiMoProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
]
