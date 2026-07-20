"""Cost tracking example — track spending across multiple providers and export reports.

Usage:
    python examples/cost_tracking_example.py

Requires:
    OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY environment variables.
"""

import sys
from pathlib import Path

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_vibe_coding import LLMClient
from ai_vibe_coding.cost_tracker import CostTracker


def main():
    tracker = CostTracker()

    prompts = [
        ("Explain Python decorators in 3 sentences", "You are a Python instructor."),
        (
            "Write a fibonacci function with memoization",
            "Use type hints and docstrings.",
        ),
        ("What is the difference between async and threading?", "Be concise."),
        ("Explain SOLID principles briefly", "You are a senior software engineer."),
    ]

    # Try multiple providers
    providers_to_try = ["openai", "deepseek"]

    for provider_name in providers_to_try:
        try:
            client = LLMClient(provider=provider_name)
        except Exception as e:
            print(f"Skipping {provider_name}: {e}")
            continue

        print(f"\n--- {provider_name} ---")
        for prompt, system in prompts:
            response = client.chat(prompt, system_prompt=system)
            tracker.record(response)
            print(
                f"{prompt[:50]}... | ${response.cost_usd:.4f} "
                f"| {response.tokens_used} tokens"
            )

    # Print summary
    print("\n" + "=" * 60)
    summary = tracker.get_summary()
    print(summary.to_table())

    # Export reports
    output_dir = Path("cost_reports")
    output_dir.mkdir(exist_ok=True)

    csv_path = tracker.export_csv(output_dir / "costs.csv")
    json_path = tracker.export_json(output_dir / "costs.json")

    print(f"\nCSV report: {csv_path}")
    print(f"JSON report: {json_path}")


if __name__ == "__main__":
    main()
