"""Multi-perspective analysis with parallel fan-out / fan-in.

Demonstrates AgentFanOut dispatching the same input to three
specialist agents concurrently, then AgentFanIn aggregating
their outputs with "join" strategy.

Run:
    python -m examples.agent_parallel_example

Note: Requires API keys for OpenAI, Anthropic, and DeepSeek.
"""

from __future__ import annotations

import os

from ai_vibe_coding.agent_templates import AgentFanIn, AgentFanOut
from ai_vibe_coding.llm_wrapper import LLMClient


def main() -> None:
    """Run multi-perspective analysis."""
    # ── 1. Create LLM clients ──────────────────────────────────
    try:
        tech_agent = LLMClient(
            provider="openai",
            model="gpt-4o-mini",
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        )
        biz_agent = LLMClient(
            provider="anthropic",
            model="claude-3-haiku-20240307",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        sec_agent = LLMClient(
            provider="deepseek",
            model="deepseek-chat",
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        )
    except Exception as e:
        print(f"Failed to initialise LLM clients: {e}")
        print("Set OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY env vars.")
        return

    # ── 2. Fan out ──────────────────────────────────────────────
    fanout = AgentFanOut(
        agents={
            "Technical": tech_agent,
            "Business": biz_agent,
            "Security": sec_agent,
        },
        timeout=30.0,
    )

    topic = "Adopting a polyglot microservices architecture"
    print(f"Analysing: {topic}\n")

    results = fanout.run(input_data=topic)
    print("Fan-out results per agent:")
    for name, output in results.items():
        print(f"  [{name}] {str(output)[:100]}...")

    # ── 3. Fan in ───────────────────────────────────────────────
    fanin = AgentFanIn(strategy="join")
    aggregated = fanin.run(results=results)

    print(f"\nAggregated type: {type(aggregated).__name__}")
    print(f"Agents in result: {list(aggregated.keys())}")


if __name__ == "__main__":
    main()
