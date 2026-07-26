#!/usr/bin/env python3
"""Example MCP server using ai-vibe-coding-kit.

This server exposes:
- The configured LLM provider + model
- A set of ToolDef tools as MCP tools
- Cost tracking per tool call

Usage:
    # Run directly:
    python examples/mcp_server_example.py

    # Run with mcp dev inspector:
    mcp dev examples/mcp_server_example.py

    # Install in Claude Desktop:
    mcp install examples/mcp_server_example.py
"""

from ai_vibe_coding import LLMClient, ToolDef

# Define some example tools
tools = [
    ToolDef(
        name="get_weather",
        description="Get current weather for a city",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "unit": {"type": "string", "description": "Temperature unit", "default": "celsius"},
            },
            "required": ["city"],
        },
    ),
    ToolDef(
        name="search_web",
        description="Search the web for information",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Maximum results to return", "default": 5},
            },
            "required": ["query"],
        },
    ),
    ToolDef(
        name="run_python",
        description="Execute Python code and return the result",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
            },
            "required": ["code"],
        },
    ),
]

# Create LLM client (using environment variables for API key)
client = LLMClient(provider="openai", model="gpt-4")

# Create MCP server
server = client.to_mcp_server(
    tools,
    name="ai-vibe-coding-demo",
    instructions="Demo MCP server with weather, web search, and Python execution tools.",
)

if __name__ == "__main__":
    import sys
    
    # Default to stdio transport for mcp dev compatibility
    print("Starting AI Vibe Coding MCP Server...", file=sys.stderr)
    print(f"Provider: {client.provider_name}", file=sys.stderr)
    print(f"Tools: {[t.name for t in tools]}", file=sys.stderr)
    
    server.run_stdio()
