"""Tests for MCP server export functionality."""

import pytest

from ai_vibe_coding.mcp_server import (
    CostTracker,
    MCPServer,
    MCPServerConfig,
    _make_typed_tool_fn,
)
from ai_vibe_coding.structured import ToolDef


class TestCostTracker:
    """Test the CostTracker class."""

    def test_record_call(self):
        """Test recording a tool call."""
        tracker = CostTracker()
        tracker.record_call("search", 0.001, 100, 50.0)
        
        summary = tracker.get_summary()
        assert summary["total_calls"] == 1
        assert summary["total_cost_usd"] == 0.001
        assert summary["total_tokens"] == 100
        assert "search" in summary["per_tool"]
        assert summary["per_tool"]["search"]["calls"] == 1

    def test_multiple_calls(self):
        """Test recording multiple calls."""
        tracker = CostTracker()
        tracker.record_call("search", 0.001, 100, 50.0)
        tracker.record_call("search", 0.002, 200, 75.0)
        tracker.record_call("code_exec", 0.005, 500, 100.0)
        
        summary = tracker.get_summary()
        assert summary["total_calls"] == 3
        assert summary["total_cost_usd"] == 0.008
        assert summary["total_tokens"] == 800

    def test_reset(self):
        """Test resetting the tracker."""
        tracker = CostTracker()
        tracker.record_call("search", 0.001, 100, 50.0)
        tracker.reset()
        
        summary = tracker.get_summary()
        assert summary["total_calls"] == 0
        assert summary["total_cost_usd"] == 0.0


class TestMCPServerConfig:
    """Test MCPServerConfig defaults."""

    def test_defaults(self):
        """Test default config values."""
        config = MCPServerConfig()
        assert config.name == "ai-vibe-coding-assistant"
        assert config.transport == "stdio"
        assert config.host == "127.0.0.1"
        assert config.port == 8000

    def test_custom_config(self):
        """Test custom config values."""
        config = MCPServerConfig(
            name="test-server",
            transport="http",
            host="0.0.0.0",
            port=9000,
        )
        assert config.name == "test-server"
        assert config.transport == "http"
        assert config.host == "0.0.0.0"
        assert config.port == 9000


class TestMakeTypedToolFn:
    """Test dynamic function generation."""

    def test_simple_function(self):
        """Test generating a simple typed function."""
        async def handler(x: int, y: int) -> str:
            return str(x + y)
        
        fn = _make_typed_tool_fn(
            "add",
            "Add two numbers",
            {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["x", "y"],
            },
            handler,
        )
        
        # Verify function was created
        assert callable(fn)
        assert fn.__name__ == "add"
        assert fn.__doc__ == "Add two numbers"

    def test_function_with_optional(self):
        """Test generating a function with optional parameters."""
        async def handler(x: int, y: int = 10) -> str:
            return str(x + y)
        
        fn = _make_typed_tool_fn(
            "add",
            "Add two numbers",
            {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["x"],
            },
            handler,
        )
        
        assert callable(fn)


class TestMCPServer:
    """Test MCPServer class."""

    def test_create_server(self):
        """Test creating an MCPServer instance."""
        from ai_vibe_coding import LLMClient
        
        client = LLMClient(provider="openai", api_key="test-key")
        tools = [
            ToolDef(name="search", description="Search the web", parameters={}),
            ToolDef(name="code_exec", description="Execute code", parameters={}),
        ]
        
        server = MCPServer(client=client, tools=tools)
        assert len(server.tools) == 2
        assert server.config.name == "ai-vibe-coding-assistant"

    def test_create_mcp_server(self):
        """Test creating the internal FastMCP server."""
        from ai_vibe_coding import LLMClient
        
        client = LLMClient(provider="openai", api_key="test-key")
        tools = [
            ToolDef(
                name="add",
                description="Add two numbers",
                parameters={
                    "type": "object",
                    "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
                    "required": ["x", "y"],
                },
            ),
        ]
        
        server = MCPServer(client=client, tools=tools)
        mcp = server._create_mcp_server()
        
        assert mcp is not None

    def test_to_mcp_server_method(self):
        """Test LLMClient.to_mcp_server() method."""
        from ai_vibe_coding import LLMClient, ToolDef
        
        client = LLMClient(provider="openai", api_key="test-key")
        tools = [
            ToolDef(name="search", description="Search the web", parameters={}),
        ]
        
        server = client.to_mcp_server(tools, name="test-server")
        assert isinstance(server, MCPServer)
        assert server.config.name == "test-server"

    def test_cost_summary(self):
        """Test cost summary retrieval."""
        from ai_vibe_coding import LLMClient
        
        client = LLMClient(provider="openai", api_key="test-key")
        server = MCPServer(client=client, tools=[])
        
        # Manually record some costs
        server._cost_tracker.record_call("test", 0.001, 100, 50.0)
        
        summary = server.get_cost_summary()
        assert summary["total_calls"] == 1
        assert summary["total_cost_usd"] == 0.001

    def test_reset_costs(self):
        """Test cost reset."""
        from ai_vibe_coding import LLMClient
        
        client = LLMClient(provider="openai", api_key="test-key")
        server = MCPServer(client=client, tools=[])
        
        server._cost_tracker.record_call("test", 0.001, 100, 50.0)
        server.reset_costs()
        
        summary = server.get_cost_summary()
        assert summary["total_calls"] == 0


class TestMCPToolIntegration:
    """Test integration with MCP SDK."""

    @pytest.mark.asyncio
    async def test_tool_registration(self):
        """Test that tools are registered correctly with MCP."""
        from ai_vibe_coding import LLMClient
        
        client = LLMClient(provider="openai", api_key="test-key")
        tools = [
            ToolDef(
                name="add",
                description="Add two numbers",
                parameters={
                    "type": "object",
                    "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
                    "required": ["x", "y"],
                },
            ),
        ]
        
        server = MCPServer(client=client, tools=tools)
        mcp = server._create_mcp_server()
        
        mcp_tools = await mcp.list_tools()
        assert len(mcp_tools) == 1
        assert mcp_tools[0].name == "add"
        assert mcp_tools[0].description == "Add two numbers"

    @pytest.mark.asyncio
    async def test_multiple_tools(self):
        """Test registering multiple tools."""
        from ai_vibe_coding import LLMClient
        
        client = LLMClient(provider="openai", api_key="test-key")
        tools = [
            ToolDef(
                name="add",
                description="Add two numbers",
                parameters={
                    "type": "object",
                    "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
                    "required": ["x", "y"],
                },
            ),
            ToolDef(
                name="multiply",
                description="Multiply two numbers",
                parameters={
                    "type": "object",
                    "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
                    "required": ["x", "y"],
                },
            ),
        ]
        
        server = MCPServer(client=client, tools=tools)
        mcp = server._create_mcp_server()
        
        mcp_tools = await mcp.list_tools()
        assert len(mcp_tools) == 2
        tool_names = [t.name for t in mcp_tools]
        assert "add" in tool_names
        assert "multiply" in tool_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
