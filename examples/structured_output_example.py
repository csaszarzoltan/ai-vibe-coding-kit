"""Structured output and tool calling example.

Usage:
    python examples/structured_output_example.py

Requires:
    OPENAI_API_KEY environment variable.
"""

import sys
from pathlib import Path

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_vibe_coding import LLMClient
from ai_vibe_coding.structured import (
    LLMJSONError,
    ToolNotFoundError,
    ToolDef,
    chat_json,
    chat_with_tools,
)


def demo_json_output():
    """Force JSON output from the LLM."""
    print("=== JSON Output Demo ===\n")

    client = LLMClient(provider="openai", model="gpt-4-turbo")

    result = chat_json(
        client,
        "List 3 Python testing frameworks with their main features and pytest compatibility",
        schema={
            "type": "object",
            "properties": {
                "frameworks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "features": {"type": "array", "items": {"type": "string"}},
                            "pytest_compatible": {"type": "boolean"},
                        },
                    },
                },
            },
        },
    )

    for fw in result.get("frameworks", []):
        name = fw.get("name", "?")
        features = ", ".join(fw.get("features", []))
        compatible = fw.get("pytest_compatible", False)
        print(f"  {name}: {features}")
        print(f"    pytest compatible: {compatible}")
    print()


def demo_tool_calling():
    """Use tool calling to let the LLM choose an action."""
    print("=== Tool Calling Demo ===\n")

    client = LLMClient(provider="openai", model="gpt-4-turbo")

    tools = [
        ToolDef(
            name="search_documentation",
            description="Search technical documentation for a query",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "language": {"type": "string"},
                },
                "required": ["query"],
            },
        ),
        ToolDef(
            name="run_test",
            description="Run a test file and return results",
            parameters={
                "type": "object",
                "properties": {
                    "test_file": {"type": "string"},
                    "verbose": {"type": "boolean"},
                },
                "required": ["test_file"],
            },
        ),
        ToolDef(
            name="generate_code",
            description="Generate code from a specification",
            parameters={
                "type": "object",
                "properties": {
                    "language": {"type": "string"},
                    "spec": {"type": "string"},
                },
                "required": ["language", "spec"],
            },
        ),
    ]

    result = chat_with_tools(
        client,
        "I need to find documentation about Python async context managers",
        tools,
    )

    print(f"  Selected tool: {result.tool_name}")
    print(f"  Arguments:     {result.arguments}")
    print(f"  Cost:          ${result.raw_response.cost_usd:.4f}")
    print()


def demo_error_handling():
    """Demonstrate error handling for invalid JSON and unknown tools."""
    print("=== Error Handling Demo ===\n")

    client = LLMClient(provider="openai", model="gpt-4-turbo")

    # This should work
    try:
        result = chat_json(client, "Return {\"status\": \"ok\"} as JSON")
        print(f"  Valid JSON: {result}")
    except LLMJSONError as e:
        print(f"  JSON error: {e}")

    # Unknown tool
    try:
        tools = [ToolDef(name="known_tool", description="A known tool")]
        result = chat_with_tools(client, "Call the unknown_tool", tools)
    except ToolNotFoundError as e:
        print(f"  ToolNotFoundError: {e}")
    except LLMJSONError as e:
        print(f"  LLMJSONError (LLM didn't return valid tool call): {e}")
    print()


def main():
    demo_json_output()
    demo_tool_calling()
    demo_error_handling()


if __name__ == "__main__":
    main()
