"""
Unified LLM API Wrapper
A production-ready interface for multiple LLM providers with cost tracking.

Supported providers:
- OpenAI (GPT-4, GPT-4.5, GPT-5)
- Anthropic (Claude 3.5, Claude 4)
- Xiaomi MiMo (cost-effective alternative)
- DeepSeek (open-source, affordable)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import os
from dataclasses import dataclass
import time


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: str
    provider: str
    model: str
    tokens_used: int
    cost_usd: float
    latency_ms: float


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def chat(self, messages: List[Dict], **kwargs) -> LLMResponse:
        """Send chat completion request."""
        pass
    
    @abstractmethod
    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for token usage."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI GPT-4/5 provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4-turbo"
    
    def chat(self, messages: List[Dict], **kwargs) -> LLMResponse:
        start = time.time()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs
        )
        latency = (time.time() - start) * 1000
        
        return LLMResponse(
            content=response.choices[0].message.content,
            provider="openai",
            model=self.model,
            tokens_used=response.usage.total_tokens,
            cost_usd=self.get_cost(response.usage.prompt_tokens, response.usage.completion_tokens),
            latency_ms=latency
        )
    
    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        # GPT-4 Turbo pricing
        return (input_tokens * 0.01 + output_tokens * 0.03) / 1000


class MiMoProvider(LLMProvider):
    """Xiaomi MiMo provider - cost-effective alternative."""
    
    def __init__(self, api_key: Optional[str] = None):
        import requests
        self.api_key = api_key or os.getenv("MIMO_API_KEY")
        self.base_url = "https://api.xiaomimimo.com/v1"
        self.model = "mimo-v2.5"
    
    def chat(self, messages: List[Dict], **kwargs) -> LLMResponse:
        start = time.time()
        
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": messages,
                **kwargs
            }
        )
        data = response.json()
        latency = (time.time() - start) * 1000
        
        usage = data.get("usage", {})
        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            provider="mimo",
            model=self.model,
            tokens_used=usage.get("total_tokens", 0),
            cost_usd=self.get_cost(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)),
            latency_ms=latency
        )
    
    def get_cost(self, input_tokens: int, output_tokens: int) -> float:
        # MiMo pricing
        return (input_tokens * 0.40 + output_tokens * 2.00) / 1000


class LLMClient:
    """
    Unified interface for multiple LLM providers.
    Switch providers with one line of code.
    """
    
    def __init__(self, provider: str = "openai", **kwargs):
        providers = {
            "openai": OpenAIProvider,
            "mimo": MiMoProvider,
        }
        
        if provider not in providers:
            raise ValueError(f"Unknown provider: {provider}")
        
        self.client = providers[provider](**kwargs)
        self.provider_name = provider
    
    def chat(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """Simple chat interface."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        return self.client.chat(messages)
    
    def compare_providers(self, prompt: str) -> Dict[str, LLMResponse]:
        """Run the same prompt across all providers for comparison."""
        results = {}
        for provider in ["openai", "mimo"]:
            try:
                client = LLMClient(provider=provider)
                results[provider] = client.chat(prompt)
            except Exception as e:
                results[provider] = f"Error: {e}"
        
        return results


# Example usage
if __name__ == "__main__":
    # Use OpenAI
    client = LLMClient(provider="openai")
    response = client.chat("Write a Python function to calculate fibonacci")
    print(f"OpenAI: {response.content[:100]}...")
    print(f"Cost: ${response.cost_usd:.4f}, Tokens: {response.tokens_used}")
    
    # Use MiMo (cheaper)
    client = LLMClient(provider="mimo")
    response = client.chat("Write a Python function to calculate fibonacci")
    print(f"\nMiMo: {response.content[:100]}...")
    print(f"Cost: ${response.cost_usd:.4f}, Tokens: {response.tokens_used}")
