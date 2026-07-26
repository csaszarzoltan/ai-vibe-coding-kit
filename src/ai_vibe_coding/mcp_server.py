"""MCP Server export for LLMClient + Tool Registry.

Exposes LLMClient with attached ToolDef set as an MCP server via stdio/HTTP transport.
Allows AI coding assistants (Claude Code, Codex, Cursor, Windsurf) to call
our LLM + tool registry as an MCP server.

Public API:
    MCPServer          — wrapper around FastMCP with LLMClient + ToolDef integration
    LLMClient.to_mcp_server() — convenience method on LLMClient
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ai_vibe_coding.llm_wrapper import LLMClient
from ai_vibe_coding.structured import ToolDef, chat_with_tools


@dataclass
class MCPServerConfig:
    """Configuration for MCP server export."""

    name: str = "ai-vibe-coding-assistant"
    instructions: str | None = None
    transport: str = "stdio"  # "stdio" or "http"
    host: str = "127.0.0.1"
    port: int = 8000


@dataclass
class MCPToolCallCost:
    """Track cost for a single MCP tool call."""

    tool_name: str
    call_count: int = 0
    total_cost: float = 0.0
    total_tokens: int = 0
    total_latency_ms: float = 0.0


def _make_typed_tool_fn(
    name: str,
    description: str,
    params_schema: dict[str, Any],
    handler: Callable[..., Any],
) -> Callable[..., Any]:
    """Create a typed async function from a JSON Schema.

    This generates a function with proper type annotations that FastMCP can
    introspect to generate the correct inputSchema for MCP.
    """
    props = params_schema.get("properties", {})
    required = set(params_schema.get("required", []))

    # Build function parameters with type annotations
    param_parts = []
    for pname, pinfo in props.items():
        ptype = pinfo.get("type", "string")
        type_map = {
            "integer": "int",
            "number": "float",
            "string": "str",
            "boolean": "bool",
            "object": "dict",
            "array": "list",
        }
        py_type = type_map.get(ptype, "Any")

        if pname in required:
            param_parts.append(f"{pname}: {py_type}")
        else:
            param_parts.append(f"{pname}: {py_type} = None")

    param_str = ", ".join(param_parts)

    # Create function source - it calls the handler with the arguments
    fn_source = f"""
async def {name}({param_str}) -> str:
    '''{description}'''
    args = {{k: v for k, v in locals().items() if k != 'handler' and v is not None}}
    return await handler(**args)
"""

    namespace: dict[str, Any] = {"handler": handler, "__builtins__": __builtins__}
    exec(fn_source, namespace)
    return namespace[name]


class MCPServer:
    """MCP Server wrapper exposing LLMClient + ToolDef as MCP tools.

    Each registered ToolDef becomes an MCP tool. When an MCP client calls a tool,
    we route through chat_with_tools() to let the LLM decide which tool to call
    and with what arguments, then execute it and return the result.

    Cost tracking accumulates per-tool-call costs for observability.
    """

    def __init__(
        self,
        client: LLMClient,
        tools: list[ToolDef],
        config: MCPServerConfig | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self.client = client
        self.tools = tools
        self.config = config or MCPServerConfig()
        self.system_prompt = system_prompt
        self._mcp_server = None
        self._cost_tracker = CostTracker()
        self._lock = threading.Lock()

    def _create_mcp_server(self):
        """Create and configure the FastMCP server with our tools."""
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP(
            name=self.config.name,
            instructions=self.config.instructions or self._default_instructions(),
            host=self.config.host,
            port=self.config.port,
        )

        # Register each ToolDef as an MCP tool
        for tool_def in self.tools:
            self._register_mcp_tool(mcp, tool_def)

        return mcp

    def _default_instructions(self) -> str:
        tool_names = ", ".join(t.name for t in self.tools)
        return (
            f"AI assistant with access to tools: {tool_names}. "
            f"Provider: {self.client.provider_name}, Model: {self.client.client.model}. "
            "Call tools by name with appropriate arguments."
        )

    def _register_mcp_tool(self, mcp: FastMCP, tool_def: ToolDef) -> None:
        """Register a ToolDef as an MCP tool that executes the actual tool logic.

        We create a typed wrapper function that:
        1. Has proper type annotations so FastMCP generates the correct schema
        2. Routes through chat_with_tools to let the LLM decide which tool to call
        3. Returns the tool's result as a string
        """

        async def handler(**kwargs: Any) -> str:
            result = await self._handle_tool_call(tool_def.name, kwargs)
            # MCP tools must return strings
            if isinstance(result, str):
                return result
            return json.dumps(result)

        # Create a typed function with the right signature from the ToolDef schema
        typed_fn = _make_typed_tool_fn(
            tool_def.name,
            tool_def.description or f"Call {tool_def.name}",
            tool_def.parameters,
            handler,
        )

        # Register with FastMCP
        mcp.add_tool(typed_fn, name=tool_def.name, description=tool_def.description)

    async def _handle_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Handle an MCP tool call by routing through chat_with_tools."""
        start_time = time.monotonic()

        # Build prompt that instructs LLM to call the specific tool
        tool_def = next((t for t in self.tools if t.name == tool_name), None)
        if not tool_def:
            raise ValueError(f"Unknown tool: {tool_name}")

        # Create prompt that asks LLM to call the specific tool with given args
        prompt = (
            f"Call the tool '{tool_name}' with these arguments: {json.dumps(arguments)}. "
            "Return only the tool result."
        )

        # Call through chat_with_tools (runs in thread executor)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: chat_with_tools(
                client=self.client,
                prompt=prompt,
                tools=self.tools,
                system_prompt=self.system_prompt,
            ),
        )

        # Track cost
        latency_ms = (time.monotonic() - start_time) * 1000
        with self._lock:
            self._cost_tracker.record_call(
                tool_name=tool_name,
                cost=result.raw_response.cost_usd,
                tokens=result.raw_response.tokens_used,
                latency_ms=latency_ms,
            )

        return result.arguments  # Return the tool's output

    def run_stdio(self) -> None:
        """Run the MCP server over stdio (blocks)."""
        if self._mcp_server is None:
            self._mcp_server = self._create_mcp_server()
        self._mcp_server.run(transport="stdio")

    async def run_stdio_async(self) -> None:
        """Run the MCP server over stdio asynchronously (blocks)."""
        if self._mcp_server is None:
            self._mcp_server = self._create_mcp_server()
        await self._mcp_server.run_stdio_async()

    def run_http(self, host: str | None = None, port: int | None = None) -> None:
        """Run the MCP server over HTTP/SSE (blocks)."""
        if self._mcp_server is None:
            self._mcp_server = self._create_mcp_server()
        self._mcp_server.run(transport="sse")

    def get_cost_summary(self) -> dict[str, Any]:
        """Get accumulated cost tracking summary."""
        with self._lock:
            return self._cost_tracker.get_summary()

    def reset_costs(self) -> None:
        """Reset cost tracking."""
        with self._lock:
            self._cost_tracker.reset()


class CostTracker:
    """Thread-safe cost tracker for MCP tool calls."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: dict[str, MCPToolCallCost] = {}
        self._total_cost = 0.0
        self._total_tokens = 0
        self._total_calls = 0

    def record_call(
        self,
        tool_name: str,
        cost: float,
        tokens: int,
        latency_ms: float,
    ) -> None:
        with self._lock:
            if tool_name not in self._calls:
                self._calls[tool_name] = MCPToolCallCost(tool_name=tool_name)
            tc = self._calls[tool_name]
            tc.call_count += 1
            tc.total_cost += cost
            tc.total_tokens += tokens
            tc.total_latency_ms += latency_ms
            self._total_cost += cost
            self._total_tokens += tokens
            self._total_calls += 1

    def get_summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_cost_usd": round(self._total_cost, 6),
                "total_tokens": self._total_tokens,
                "total_calls": self._total_calls,
                "per_tool": {
                    name: {
                        "calls": tc.call_count,
                        "cost_usd": round(tc.total_cost, 6),
                        "tokens": tc.total_tokens,
                        "avg_latency_ms": round(
                            tc.total_latency_ms / tc.call_count, 2
                        )
                        if tc.call_count > 0
                        else 0,
                    }
                    for name, tc in self._calls.items()
                },
            }

    def reset(self) -> None:
        with self._lock:
            self._calls.clear()
            self._total_cost = 0.0
            self._total_tokens = 0
            self._total_calls = 0


# Extension method on LLMClient
def to_mcp_server(
    self: LLMClient,
    tools: list[ToolDef],
    *,
    name: str = "ai-vibe-coding-assistant",
    instructions: str | None = None,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8000,
    system_prompt: str | None = None,
) -> MCPServer:
    """Create an MCP server exposing this LLMClient + tools.

    Args:
        tools: List of ToolDef to expose as MCP tools
        name: Server name for MCP identification
        instructions: Optional instructions for MCP clients
        transport: "stdio" or "http"
        host: HTTP host (if transport="http")
        port: HTTP port (if transport="http")
        system_prompt: Optional system prompt for all tool calls

    Returns:
        MCPServer instance ready to run with .run_stdio() or .run_http()

    Example:
        client = LLMClient(provider="openai")
        tools = [
            ToolDef(name="search", description="Search the web", parameters={...}),
            ToolDef(name="code_exec", description="Execute Python", parameters={...}),
        ]
        server = client.to_mcp_server(tools, transport="stdio")
        server.run_stdio()  # blocks, speaks MCP over stdin/stdout
    """
    config = MCPServerConfig(
        name=name,
        instructions=instructions,
        transport=transport,
        host=host,
        port=port,
    )
    return MCPServer(
        client=self,
        tools=tools,
        config=config,
        system_prompt=system_prompt,
    )


# Monkey-patch the method onto LLMClient
LLMClient.to_mcp_server = to_mcp_server


__all__ = [
    "MCPServer",
    "MCPServerConfig",
    "MCPToolCallCost",
    "CostTracker",
    "to_mcp_server",
]
