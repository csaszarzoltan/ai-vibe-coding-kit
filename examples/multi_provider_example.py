"""Multi-provider comparison example — run the same prompt across all providers.

Usage:
    python examples/multi_provider_example.py

Requires:
    OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY,
    OPENROUTER_API_KEY, MIMO_API_KEY
"""

import sys
from pathlib import Path

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_vibe_coding import LLMClient
from ai_vibe_coding.cost_tracker import CostTracker


def main():
    prompt = (
        "Write a Python function that checks if a string is a valid email address. "
        "Include docstring and type hints."
    )

    tracker = CostTracker()

    providers = ["openai", "anthropic", "deepseek", "openrouter", "mimo"]

    print(f"Prompt: {prompt}\n")
    print(f"{'Provider':<12} {'Model':<20} {'Cost':>10} {'Tokens':>8} {'Latency':>10}")
    print("-" * 65)

    for provider_name in providers:
        try:
            client = LLMClient(provider=provider_name)
            response = client.chat(prompt)
            tracker.record(response)
            print(
                f"{provider_name:<12} {response.model:<20} "
                f"${response.cost_usd:>8.4f} {response.tokens_used:>8} "
                f"{response.latency_ms:>8.0f}ms"
            )
        except Exception as e:
            print(f"{provider_name:<12} ERROR: {e}")

    # Summary
    print("\n" + tracker.get_summary().to_table())


if __name__ == "__main__":
    main()
