"""AI Vibe Coding Kit - Multi-provider LLM API wrapper with cost tracking.

Provides a unified interface for calling multiple LLM providers (OpenAI,
Anthropic, DeepSeek, OpenRouter, MiMo) with built-in cost tracking,
structured output, and tool calling support.

Quick start:
    from ai_vibe_coding import LLMClient

    client = LLMClient(provider="openai")
    response = client.chat("Hello, world!")
    print(response.content, response.cost_usd)
"""

from ai_vibe_coding.llm_wrapper import (
    LLMClient,
    LLMProvider,
    LLMResponse,
)

__all__ = [
    "LLMClient",
    "LLMProvider",
    "LLMResponse",
]
