# MCP Server Guide

Connect AI editors (Cursor, Claude Desktop, Windsurf, and any MCP-compatible
client) to a local toolbox of 6 tools — file read/write, directory listing,
DuckDuckGo web search, sandboxed Python execution, and simulated weather data.

No API keys required. The server runs locally via stdio (the standard MCP
transport) and does not make outbound calls except for web search.

## Quick Start — MCP in 5 Minutes

### 1. Install the `mcp` package

```bash
pip install mcp
```

This installs the Python MCP SDK (`mcp[fastmcp]`) which provides the `FastMCP`
decorator API used by the server.

> **Already installed?** The project's `requirements.txt` lists `mcp>=1.0.0`
> as an optional dependency. Run `pip install -e ".[dev]"` from the repo root
> to install everything at once.

### 2. Run the MCP server

```bash
cd ai-vibe-coding-kit
python examples/standalone_mcp_server.py
```

The server starts and listens on **stdin/stdout** (stdio transport). It prints
nothing to the terminal — MCP clients communicate with it over the process's
standard streams. Press Ctrl+C to stop.

> **Verify the server started correctly** by running it with a quick smoke test
> in another terminal:
> ```bash
> python -c "
> import sys; sys.path.insert(0, '.')
> from examples.standalone_mcp_server import get_weather
> print(get_weather('Zurich'))
> "
> ```
> Expected output includes a simulated weather report for Zurich.

For interactive testing during development, use the MCP Inspector:

```bash
mcp dev examples/standalone_mcp_server.py
```

This opens a web UI at `http://localhost:5173` where you can call each tool
and inspect its input/output schema.

### 3. Configure Cursor AI Editor

Add the following JSON to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "ai-vibe-coding": {
      "command": "python",
      "args": [
        "${workspaceFolder}/examples/standalone_mcp_server.py"
      ],
      "env": {
        "ALLOWED_BASE_DIR": "${workspaceFolder}",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Save the file, then **restart Cursor**. The editor auto-detects the MCP
server config on startup. You should see a green "MCP connected" indicator
in the bottom-right corner of the editor.

> **Path troubleshooting:** If Cursor reports "MCP server exited", verify
> that the `args` path resolves correctly. The `${workspaceFolder}` variable
> expands to the directory of the currently open project. For a monorepo
> setup, use an absolute path instead.

### 4. Configure Claude Desktop

Add the following to your `claude_desktop_config.json`
(location depends on your OS):

| OS      | Config Path |
|---------|------------|
| macOS   | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux   | `~/.config/Claude/claude_desktop_config.json` |

```json
{
  "mcpServers": {
    "ai-vibe-coding": {
      "command": "python",
      "args": [
        "/ABSOLUTE/PATH/TO/ai-vibe-coding-kit/examples/standalone_mcp_server.py"
      ],
      "env": {
        "ALLOWED_BASE_DIR": "/ABSOLUTE/PATH/TO/ai-vibe-coding-kit",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

**Important:** Replace `/ABSOLUTE/PATH/TO/ai-vibe-coding-kit` with the actual
absolute path to the cloned repository on your machine. Claude Desktop does
not support the `${workspaceFolder}` variable — it requires real paths.

Save the file and **restart Claude Desktop**. A hammer icon appears in the
input area when the MCP tools are connected.

### 5. Verify the Integration

Once Cursor or Claude Desktop connects, try these prompts to confirm the
tools are working:

> **read_file:** "Read the README.md file"
>
> **write_file:** "Write a hello.txt with 'Hello MCP world'"
>
> **list_directory:** "List the files in the examples directory"
>
> **search_web:** "Search the web for Python MCP SDK documentation"
>
> **execute_python:** "Run Python: print(sum(range(100)))"
>
> **get_weather:** "What's the weather in Budapest?"

If a tool responds with data, the integration is working. If you see "Tool
not found" or "Unknown tool", restart the editor — config changes require a
restart to take effect.

---

## Available Tools

All 6 tools are defined in `examples/standalone_mcp_server.py` using
FastMCP decorators (`@mcp.tool()`). No external API keys are needed.

### `read_file(path: str) -> str`

Read the contents of a file. Path is relative to the project root.

| Parameter | Type   | Description |
|-----------|--------|-------------|
| `path`    | string | Relative or absolute path to the file |

**Security:** Blocks path traversal (`..` escape sequences). Raises
`ValueError` if the path leaves the allowed base directory.

### `write_file(path: str, content: str) -> str`

Write content to a file. Creates parent directories if needed.

| Parameter | Type   | Description        |
|-----------|--------|--------------------|
| `path`    | string | Relative path      |
| `content` | string | Text content to write |

Returns a confirmation message with the absolute path and byte count.

### `list_directory(path: str = ".") -> str`

List files and directories in the specified path.

| Parameter | Type   | Description                          |
|-----------|--------|--------------------------------------|
| `path`    | string | Directory path (default: current dir) |

Returns a formatted listing with `[DIR]` and `[FILE]` prefixes and file sizes.

### `search_web(query: str, max_results: int = 5) -> str`

Search the web for information using DuckDuckGo (no API key needed).

| Parameter     | Type   | Description                    |
|---------------|--------|--------------------------------|
| `query`       | string | Search query                   |
| `max_results` | int    | Max results (1–10, default 5)  |

Returns ranked results with titles, URLs, and snippets.

### `execute_python(code: str, timeout_seconds: int = 10) -> str`

Execute Python code in a sandboxed subprocess with a timeout.

| Parameter        | Type   | Description                    |
|------------------|--------|--------------------------------|
| `code`           | string | Python code to execute         |
| `timeout_seconds`| int    | Max seconds (1–30, default 10) |

**Security:** Runs in a temporary directory. Stdout and stderr are captured.
Exceeding the timeout raises a `TimeoutError`.

### `get_weather(city: str, unit: str = "celsius") -> str`

Get the current weather for a city. This is a **demo tool** — it generates
deterministic simulated data based on the city name, not live weather data.

| Parameter | Type   | Description                           |
|-----------|--------|---------------------------------------|
| `city`    | string | City name                             |
| `unit`    | string | Temperature unit: `celsius` or `fahrenheit` |

Returns condition, temperature, feels-like, and humidity.

---

## Security Model

The standalone MCP server is designed for **local development** and follows
defense-in-depth principles:

| Layer | Mechanism |
|-------|-----------|
| **Path sandbox** | All filesystem tools validate paths against `ALLOWED_BASE_DIR` (default: the current working directory). Path traversal with `..` is explicitly blocked. |
| **Code sandbox** | `execute_python` runs in a temporary directory via `subprocess` with a configurable timeout (default 10s, max 30s). No network access. |
| **No secrets** | The server requires no API keys. Web search uses DuckDuckGo's public HTML endpoint (unauthenticated). |
| **Configuration** | Override `ALLOWED_BASE_DIR` via environment variable to restrict file access to a specific directory. |

---

## Server Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOWED_BASE_DIR` | Current working directory | Restricts filesystem tools to this path |
| `PYTHONUNBUFFERED` | — | Set `1` to disable stdout buffering (recommended for MCP) |

### Transport Modes

The server uses **stdio** transport by default. The `mcp.run()` call in
`standalone_mcp_server.py` accepts the `transport` parameter:

```python
if __name__ == "__main__":
    mcp.run(transport="stdio")       # default — for editors
    # mcp.run(transport="sse")       # HTTP/SSE — for remote clients
```

SSE (Server-Sent Events) mode enables connecting MCP clients over HTTP, but
is primarily useful for remote or containerized scenarios.

---

## Programmatic API

For Python scripts that want to use the MCP tools programmatically (without
an editor), import the functions directly:

```python
from examples.standalone_mcp_server import (
    read_file, write_file,
    list_directory, search_web,
    execute_python, get_weather,
)

# Read a file
content = read_file("README.md")
print(content[:200])

# Search the web
results = search_web("Python MCP protocol", max_results=3)
print(results)

# Execute Python in sandbox
output = execute_python("print('hello from sandbox')")
print(output)

# Demo weather
weather = get_weather("Budapest", unit="celsius")
print(weather)
```

### Library-based MCPServer (advanced)

The kit also provides a `MCPServer` class in `src/ai_vibe_coding/mcp_server.py`
that wraps an `LLMClient` instance and a list of `ToolDef` objects as an MCP
server. This is useful when you already have an `LLMClient` configured with
API keys and want to expose your own tool definitions:

```python
from ai_vibe_coding import LLMClient, ToolDef
from ai_vibe_coding.structured import chat_with_tools

# Create LLM client
client = LLMClient(provider="openai")

# Define tools
tools = [
    ToolDef(
        name="get_weather",
        description="Get current weather for a city",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    ),
]

# Convert to MCP server
server = client.to_mcp_server(tools, name="my-tools")
server.run_stdio()  # blocks, speaks MCP stdio protocol
```

See `examples/mcp_server_example.py` for a complete working example and
`src/ai_vibe_coding/mcp_server.py` for the full API reference.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "MCP server exited" in Cursor | Path resolution failure | Use an absolute path in `.cursor/mcp.json` or verify `${workspaceFolder}` resolves correctly |
| "Tool not found" | Config change without restart | Restart the editor after changing `.cursor/mcp.json` |
| "ModuleNotFoundError: No module named 'mcp'" | Missing dependency | `pip install mcp` |
| "Connection refused" | Server not running | Verify the process is running (`ps aux | grep standalone_mcp_server`) |
| "Path traversal blocked" | `..` in file path | Use a direct path within the allowed base directory |
| Files outside project | Wrong `ALLOWED_BASE_DIR` | Set `ALLOWED_BASE_DIR` to the root directory you want to allow |

---

## Verification Checklist

After setup, confirm everything works:

- [ ] `python -c "from examples.standalone_mcp_server import get_weather; print(get_weather('Test'))"` returns a weather report
- [ ] `.cursor/mcp.json` contains valid JSON with the correct path
- [ ] `claude_desktop_config.json` contains the absolute path (not `${workspaceFolder}`)
- [ ] Cursor or Claude Desktop shows the MCP tools as connected
- [ ] The `read_file` and `list_directory` tools work in the editor
- [ ] The `search_web` tool returns results in the editor
