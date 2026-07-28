"""Content generation pipeline: Research → Writer → Reviewer.

Demonstrates a sequential AgentPipeline with 3 agents using
different LLM providers.  The pipeline chains the output of each
agent as input to the next.

Run:
    python -m examples.agent_pipeline_example

Note: Requires API keys for OpenAI, Anthropic, and DeepSeek.
"""

from __future__ import annotations

import os

from ai_vibe_coding.agent_templates import AgentPipeline, PipelineResult
from ai_vibe_coding.llm_wrapper import LLMClient


def main() -> None:
    """Run the content generation pipeline."""
    # ── 1. Create LLM clients for each provider ────────────────
    try:
        research_agent = LLMClient(
            provider="openai",
            model="gpt-4o-mini",
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        )
        writer_agent = LLMClient(
            provider="anthropic",
            model="claude-3-haiku-20240307",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        reviewer_agent = LLMClient(
            provider="deepseek",
            model="deepseek-chat",
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        )
    except Exception as e:
        print(f"Failed to initialise LLM clients: {e}")
        print("Set OPENAI_API_KEY, ANTHROPIC_API_KEY, and DEEPSEEK_API_KEY env vars.")
        return

    # ── 2. Build the pipeline ──────────────────────────────────
    pipeline = AgentPipeline(
        agents=[research_agent, writer_agent, reviewer_agent],
    )

    # ── 3. Run ─────────────────────────────────────────────────
    topic = "The impact of quantum computing on cryptography"
    print(f"Generating article on: {topic}\n")

    result: PipelineResult = pipeline.run(input_data=topic)

    print(f"Status: {result.status}")
    print(f"Final output:\n{result.final_output}")
    print(f"\nTotal cost: ${result.total_cost_usd:.4f}")
    print(f"Total tokens: {result.total_tokens}")
    print(f"Steps: {len(result.steps)}")


if __name__ == "__main__":
    main()
