"""Hierarchical supervisor with specialised worker agents.

Demonstrates AgentSupervisor routing tasks to a team of workers
(developer, reviewer, tester) using an LLM-based delegation strategy.

Run:
    python -m examples.agent_supervisor_example

Note: Requires API keys for OpenAI, Anthropic, and DeepSeek.
"""

from __future__ import annotations

import os

from ai_vibe_coding.agent_team import AgentConfig, AgentTeamResult
from ai_vibe_coding.agent_templates import AgentSupervisor
from ai_vibe_coding.llm_wrapper import LLMClient


def main() -> None:
    """Run hierarchical development team example."""
    # ── 1. Create LLM clients ──────────────────────────────────
    try:
        supervisor_client = LLMClient(
            provider="openai",
            model="gpt-4o-mini",
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        )
        dev_client = LLMClient(
            provider="anthropic",
            model="claude-3-haiku-20240307",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
        review_client = LLMClient(
            provider="deepseek",
            model="deepseek-chat",
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        )
        test_client = LLMClient(
            provider="openai",
            model="gpt-4o-mini",
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        )
    except Exception as e:
        print(f"Failed to initialise LLM clients: {e}")
        print("Set OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY env vars.")
        return

    # ── 2. Configure workers ────────────────────────────────────
    agent_cfg = {
        "developer": AgentConfig(
            name="developer",
            client=dev_client,
            system_prompt="You are a senior Python developer. Write clean, "
            "well-documented code.",
        ),
        "reviewer": AgentConfig(
            name="reviewer",
            client=review_client,
            system_prompt="You are a code reviewer. Find bugs, style issues, "
            "and security flaws.",
        ),
        "tester": AgentConfig(
            name="tester",
            client=test_client,
            system_prompt="You are a QA engineer. Write comprehensive tests "
            "for the given code.",
        ),
    }

    def on_delegation(event: object) -> None:
        """Trace callback for delegation events."""
        print(f"  Delegated: {event}")

    # ── 3. Build supervisor ─────────────────────────────────────
    supervisor = AgentSupervisor(
        supervisor=supervisor_client,
        agents=agent_cfg,
        cost_limit_usd=0.05,
        on_delegation=on_delegation,
    )

    # ── 4. Run ──────────────────────────────────────────────────
    task = "Write a Python function that validates email addresses"
    print(f"Task: {task}\n")

    result = supervisor.run(task)
    print(f"\nResult type: {type(result).__name__}")


if __name__ == "__main__":
    main()
