# Analysis Brief: MCP Server Integration Templates & Quickstart Examples

**Date:** 2026-07-24
**Author:** Analyst profile (task t_4a693e43)
**Status:** Complete
**Repo:** `ai-vibe-coding-kit` at `/home/zoltan/ai-vibe-coding-kit`

---

## 1. Current State Assessment

### 1.1 Existing MCP Infrastructure (What We Already Have)

The `ai-vibe-coding-kit` repo already ships a functional MCP server integration. Key assets:

| Asset | Location | Capabilities |
|-------|----------|-------------|
| `MCPServer` class | `src/ai_vibe_coding/mcp_server.py` | Wraps FastMCP with LLMClient + ToolDef integration. Supports stdio and HTTP/SSE transport. |
| `MCPServerConfig` | `src/ai_vibe_coding/mcp_server.py` | Dataclass: name, instructions, transport, host, port |
| `CostTracker` (MCP-specific) | `src/ai_vibe_coding/mcp_server.py` | Thread-safe per-tool cost tracking with `get_summary()`, `reset()` |
| `LLMClient.to_mcp_server()` | `src/ai_vibe_coding/mcp_server.py` | Convenience monkey-patch on LLMClient — creates MCPServer from client + ToolDef list |
| Example server | `examples/mcp_server_example.py` | Demo server with weather, web_search, run_python tools |
| Test suite | `tests/test_mcp_server.py` | 276 lines, 57 test cases covering CostTracker, MCPServerConfig, _make_typed_tool_fn, MCPServer creation, MCP tool integration |
| `mcp` dependency | `pyproject.toml` | `mcp>=1.0.0` already listed with FastAPI, uvicorn |
| `ToolDef` system | `src/ai_vibe_coding/structured.py` | Complete tool definition system with parameters JSON Schema, `chat_with_tools()` executor |

### 1.2 Gap Analysis (What's Missing for Quickstart)

| Capability | Status | Notes |
|------------|--------|-------|
| **Real tool implementations** (filesystem, web, code exec) | ❌ Missing | Example tools are stubs — no actual filesystem/network operations |
| **Self-contained standalone MCP server** | ⚠️ Partial | Existing server requires `LLMClient` + ToolDef; need a version that works as a standalone MCP server without LLM routing |
| **Cursor MCP config template** (`.cursor/mcp.json`) | ❌ Missing | No per-project MCP configuration for Cursor IDE |
| **Claude Desktop config template** (`claude_desktop_config.json`) | ❌ Missing | No copy-pasteable config for Claude Desktop users |
| **README "Getting Started with MCP"** | ❌ Missing | README has LLM wrapper, benchmarks, CI/CD — no MCP section |
| **docs/mcp-guide.md** | ❌ Missing | No dedicated MCP documentation page |
| **Tests for standalone tools** | ❌ Missing | Tools in example are untested; no test for filesystem/web/code_exec implementations |
| **Tool-level error handling** | ❌ Missing | No graceful errors for missing files, network failures, invalid code |
| **Streamable HTTP transport** | ⚠️ Partial | `transport="sse"` exists but not `streamable-http` |
| **Multi-server composition example** | ❌ Missing | No example showing how to compose multiple MCP servers |

### 1.3 Key Risks

| Risk | Context | Mitigation |
|------|---------|------------|
| **`mcp` SDK version churn** | SDK at v1.x, v2 in development with breaking changes | Pin `mcp>=1.27,<2` per official recommendation until stable v2 |
| **Security: code execution** | `run_python` tool executes arbitrary code | Use sandboxed subprocess with resource limits/timeout |
| **Security: filesystem paths** | Filesystem tools must not escape project root | Validate paths against allowed base directory |
| **API key exposure in config files** | JSON configs may contain env var references | Use `${env:VAR_NAME}` syntax in templates; document .gitignore |
| **Cross-platform path separators** | Windows vs Unix | Document with `${workspaceFolder}` variable and platform notes |

---

## 2. Clustered Options

### Option A: Extend Existing MCPServer with Real Tools + Config Templates (RECOMMENDED)

Build on the existing `mcp_server.py` library module. Add three real tool implementations (filesystem, web search, code execution) as a standalone example server that can be copied and tweaked. Create `.cursor/mcp.json` and `claude_desktop_config.json` templates that point to it.

**Trade-offs:**
+ Reuses existing `MCPServer`, `CostTracker`, `ToolDef` infrastructure
+ Consistent architecture — no parallel tool system
+ `LLMClient.to_mcp_server()` works for programmatic users
+ Templates can be generated/documented from same source
- Existing tools route through `chat_with_tools()` (LLM-based execution) — standalone tools should execute directly
- Example server currently tied to LLM provider; standalone server should work without an LLM key

### Option B: New Standalone FastMCP Server (Separate File)

Create a completely new example at `examples/standalone_mcp_server.py` that uses raw `@mcp.tool()` decorators (not the MCPServer wrapper class). This is the "standard" MCP pattern that most tutorials show.

**Trade-offs:**
+ Most idiomatic FastMCP pattern — no LLM routing layer
+ Works without any API key — pure tool execution
+ Cleaner, shorter code (10-15 lines per tool)
+ Easier to understand for MCP newcomers
- Duplicates functionality that already exists in `mcp_server.py`
- Two diverging MCP server implementations to maintain
- Loses the cost tracking, provider routing, and LLM-mediation features

### Option C: Hybrid — Standalone Example + Updated Library

Build a standalone FastMCP demo server using raw `@mcp.tool()` decorators (Option B approach) as the quickstart example. Simultaneously update `mcp_server.py` to support both "LLM-routed" and "direct execution" modes.

**Trade-offs:**
+ Best learning curve: newcomers use the simple standalone server
+ Library keeps LLM-mediation for advanced users
+ Direct execution mode fills the gap in existing MCPServer
- Higher implementation effort
- Risk of feature drift between the two patterns

**Decision:** Option C — Hybrid. The quickstart example should be a clean, self-contained FastMCP server using `@mcp.tool()` decorators (no LLM routing). This is what users expect from MCP documentation and tutorials. The existing `mcp_server.py` library class remains for users who want LLM-mediation + cost tracking on top of their tools. The two serve different audiences: standalone server is for "I want MCP tools now", the library class is for "I want AI vibe coding with cost tracking".

---

## 3. Chosen Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **MCP framework** | `mcp>=1.27,<2` / FastMCP (included in `mcp` package) | Already a dependency; FastMCP decorators are the standard Python API for MCP |
| **MCP config format** | JSON (`.cursor/mcp.json`, `claude_desktop_config.json`) | Standard across Cursor, Claude Desktop, Windsurf, Codex |
| **Filesystem operations** | `pathlib` + `os` (stdlib) | Zero dependencies; path validation via `Path.resolve()` |
| **Web search** | `httpx` (existing dep) or `requests` (stdlib alternative) | `httpx` already listed; DuckDuckGo Lite HTML scraping (no API key) |
| **Code execution** | `subprocess` + `tempfile` (stdlib) | Sandboxed in temp dir with `timeout` and resource limits |
| **Standalone server** | Separate `examples/standalone_mcp_server.py` | Clean FastMCP decorators, no LLM dependency |
| **Config templates** | Static JSON files in repo root | Copy-pasteable; documented with inline comments |
| **Testing** | Existing pytest pattern | Interface tests + behavioral tests; mock filesystem/web/code calls |

**What we do NOT add as new dependencies:**
- No new Python packages beyond what's already in `pyproject.toml`
- No external search APIs requiring keys (DuckDuckGo works unauthenticated)
- No sandbox library for code execution (stdlib subprocess is sufficient with limits)
- No separate MCP server hosting framework (FastMCP handles transports)

---

## 4. Architecture Overview

```
ai-vibe-coding-kit/
├── .cursor/
│   └── mcp.json                    # NEW: Cursor MCP config template (P0)
├── claude_desktop_config.json      # NEW: Claude Desktop config template (P0)
├── examples/
│   ├── mcp_server_example.py       # EXISTING: LLM-routed MCP server example (updated)
│   └── standalone_mcp_server.py    # NEW: Self-contained FastMCP tools demo (P0)
├── src/ai_vibe_coding/
│   └── mcp_server.py               # EXISTING: library class (minor updates)
├── tests/
│   ├── test_mcp_server.py          # EXISTING: 276 lines, 57 tests
│   └── test_mcp_tools.py           # NEW: tests for standalone tools (P0)
├── docs/
│   └── mcp-guide.md                # NEW: MCP reference documentation (P1)
└── README.md                       # EXISTING: add "Getting Started with MCP" section (P0)

```

### Component Relationships

```
User (Cursor / Claude Desktop)
  │
  ├── reads .cursor/mcp.json or claude_desktop_config.json
  │
  ▼
MCP client connects to server via stdio
  │
  ▼
standalone_mcp_server.py (FastMCP @mcp.tool decorators)
  │
  ├── @mcp.tool() read_file(path)     →  filesystem (pathlib)
  ├── @mcp.tool() write_file(path, content) → filesystem (pathlib)
  ├── @mcp.tool() list_directory(path)  → filesystem (pathlib)
  ├── @mcp.tool() search_web(query)    → web (httpx → DuckDuckGo)
  ├── @mcp.tool() execute_python(code) → subprocess sandbox
  └── @mcp.tool() get_weather(city)    → demo
```

---

## 5. Module Specifications

### 5.1 `examples/standalone_mcp_server.py` — Standalone FastMCP Demo (P0)

**Purpose:** A self-contained, copy-pasteable MCP server using raw `@mcp.tool()` decorators. Runs without any API keys. Introduces MCP concepts to newcomers. Used as the target for `.cursor/mcp.json` and `claude_desktop_config.json` config templates.

**Server name:** `ai-vibe-coding-mcp`

**Tools:**

```python
@mcp.tool()
def read_file(path: str) -> str:
    """Read the contents of a file. Path is relative to the project root.
    
    Args:
        path: Relative or absolute path to the file to read
    Returns:
        File contents as a string
    Raises:
        ValueError: If path escapes the allowed base directory
        FileNotFoundError: If file does not exist
    """


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write content to a file. Creates parent directories if needed.
    
    Args:
        path: Relative path from project root
        content: Text content to write
    Returns:
        Confirmation message with absolute path
    Raises:
        ValueError: If path escapes the allowed base directory
    """


@mcp.tool()
def list_directory(path: str = ".") -> str:
    """List files and directories in the specified path.
    
    Args:
        path: Directory path (default: current directory)
    Returns:
        Formatted directory listing with file sizes and types
    Raises:
        ValueError: If path escapes the allowed base directory
        FileNotFoundError: If directory does not exist
    """


@mcp.tool()
def search_web(query: str, max_results: int = 5) -> str:
    """Search the web for information using DuckDuckGo.
    
    Args:
        query: Search query string
        max_results: Maximum number of results (1-10, default: 5)
    Returns:
        Formatted search results with titles, URLs, and snippets
    """


@mcp.tool()
def execute_python(code: str, timeout_seconds: int = 10) -> str:
    """Execute Python code in a sandboxed environment and return output.
    
    Security: Runs in a temporary directory with 10-second timeout.
    Stdout and stderr are captured. No network access.
    
    Args:
        code: Python code to execute
        timeout_seconds: Max execution time (1-30, default: 10)
    Returns:
        Combined stdout and stderr output
    Raises:
        TimeoutError: If execution exceeds timeout
    """


@mcp.tool()
def get_weather(city: str, unit: str = "celsius") -> str:
    """Get the current weather for a city (demo tool using simulated data).
    
    Args:
        city: City name
        unit: Temperature unit (celsius or fahrenheit)
    Returns:
        Simulated weather report for the given city
    """
```

**Transport:** `stdio` (default) and `streamable-http`

**Dependencies:** `mcp>=1.27,<2`, `httpx` (for web search), stdlib

**Error behavior:**
- Path traversal attempts → `ValueError` with clear message
- File not found → `FileNotFoundError` (surfaced by MCP)
- Code execution timeout → `TimeoutError` after timeout_seconds
- Web search failure → fallback message with HTTP status info

### 5.2 `.cursor/mcp.json` — Cursor Config Template (P0)

**Purpose:** Per-project MCP configuration file for Cursor IDE. Points to the standalone MCP server. Uses `${workspaceFolder}` and `${env:VAR}` variable resolution.

**Location:** `.cursor/mcp.json` in repo root

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

**Documentation in file:** Comment explaining:
- How to enable (file is already in repo, Cursor picks it up automatically)
- How to add API keys for web search if needed
- How to switch to `uv run` or `pip install -e .` based execution

### 5.3 `claude_desktop_config.json` — Claude Desktop Config Template (P0)

**Purpose:** Copy-pasteable configuration for Claude Desktop MCP integration.

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

**Documentation in file:** Comment explaining:
- Config file location per OS (macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`)
- Must replace `/ABSOLUTE/PATH/TO/` with actual cloned path
- How to verify it works (Claude Desktop shows tools in chat)
- Re-launch Claude Desktop after adding config

### 5.4 README Section — "Getting Started with MCP in 5 Minutes" (P0)

**Purpose:** Quickstart guide for MCP integration, placed in the main README after the existing "Quick Start" section.

**Structure:**
1. **What is MCP?** — One-paragraph explanation tying MCP to the kit's existing tool calling
2. **Prerequisites** — `pip install -e ".[dev]"` already done
3. **Start the MCP server** — `python examples/standalone_mcp_server.py` (stdio mode)
4. **Test with MCP Inspector** — `pip install mcp` + `mcp dev examples/standalone_mcp_server.py`
5. **Connect Cursor IDE** — Copy `.cursor/mcp.json` steps, restart Cursor, see tools in @-mentions
6. **Connect Claude Desktop** — Copy `claude_desktop_config.json` steps, restart, see tools
7. **Available tools** — Table with read_file, write_file, list_directory, search_web, execute_python, get_weather
8. **Security notes** — Path sandboxing, code execution timeout, web search limitations
9. **Next steps** — Link to `docs/mcp-guide.md` when built

### 5.5 `src/ai_vibe_coding/mcp_server.py` — Library Updates (P1)

**Purpose:** Minor updates to the existing library class:

1. Add `direct_execution=True` mode to MCPServer — when enabled, tool handlers execute directly instead of routing through `chat_with_tools()`
2. Add `streamable-http` transport option alongside existing `stdio` and `sse`
3. Export `MCPServer` creation helpers that work without an LLM client

**Note:** These are P1 enhancements. The P0 quickstart uses the standalone server, not the library class.

---

## 6. Prioritized Task List

### P0 — Core templates & examples (must ship)

| # | Artifact | What | Acceptance Criteria | Notes |
|---|----------|------|-------------------|-------|
| **P0.1** | `examples/standalone_mcp_server.py` | Standalone FastMCP server with 6 tools | Imports cleanly. `mcp.run(transport="stdio")` starts without error. All 6 `@mcp.tool()` functions are callable. Path sandboxing works. | New file |
| **P0.2** | `tests/test_mcp_tools.py` | Tests for standalone tools | Each tool tested: (1) interface test — function exists and is async; (2) functional test — real call returns expected type; (3) error test — invalid input raises properly | New file |
| **P0.3** | `.cursor/mcp.json` | Cursor MCP config template | Valid JSON. References `standalone_mcp_server.py`. Uses `${workspaceFolder}`. Works when copied to `.cursor/mcp.json`. | New file |
| **P0.4** | `claude_desktop_config.json` | Claude Desktop config template | Valid JSON. References `standalone_mcp_server.py`. Has clear placeholders for absolute path. Contains explanatory comments. | New file |
| **P0.5** | README "Getting Started with MCP in 5 Minutes" | README section | Copy-pasteable commands work end-to-end. Links to both config files. Covers all 6 tools. Security notes included. | Edit README.md |

### P1 — Documentation & polish

| # | Artifact | What | Acceptance Criteria | Notes |
|---|----------|------|-------------------|-------|
| **P1.1** | `docs/mcp-guide.md` | MCP reference docs | Explains MCP concepts, tool reference, config file locations per OS, troubleshooting, security best practices | New file |
| **P1.2** | `examples/mcp_server_example.py` update | Update existing example | Align tool names with standalone server. Add filesystem tools. Document LLM-routed vs direct mode. | Edit existing |
| **P1.3** | `mcp_server.py` library updates | Add direct_execution mode + streamable-http | `MCPServer(direct_execution=True)` creates tools that run without LLM. `mcp.run(transport="streamable-http")` works. Backward compatible. | Edit existing |

### P2 — Extended capabilities (future)

| # | Artifact | What | Priority Notes |
|---|----------|------|----------------|
| **P2.1** | `.github/workflows/mcp-integration-test.yml` | CI test that starts MCP server and calls each tool | Verify the server stays running across releases |
| **P2.2** | Multi-server composition example | Show Cursor config with multiple MCP servers | Advanced use case |
| **P2.3** | MCP + LLMClient bridge example | Show how to use MCP tools with LLMClient chat_with_tools | Power user feature |
| **P2.4** | Dockerfile for MCP server standalone | Containerized MCP server for remote deployments | Cloud/codespace use |

---

## 7. Acceptance Criteria Per Task

### Acceptance Criteria for P0.1 (standalone_mcp_server.py)

1. **Module runs standalone** — `python examples/standalone_mcp_server.py` starts a stdio MCP server with no errors
2. **Imports cleanly** — `from examples.standalone_mcp_server import mcp` raises no ImportError
3. **`read_file(path)`** — Returns file contents as string. Traversing above base dir raises `ValueError`. Missing file raises `FileNotFoundError`.
4. **`write_file(path, content)`** — Creates file with content. Creates parent dirs automatically. Traversing above base dir raises `ValueError`.
5. **`list_directory(path)`** — Returns formatted listing. Default path is `.`. Traversing above base dir raises `ValueError`.
6. **`search_web(query, max_results)`** — Returns non-empty string with results. Handles network errors gracefully.
7. **`execute_python(code, timeout_seconds)`** — Returns execution output. 10-second default timeout. `print()` output captured. Syntax errors returned as error message. Network access blocked in subprocess.
8. **`get_weather(city, unit)`** — Returns a simulated weather report string. Both celsius and fahrenheit units accepted.
9. **No API keys required** — All tools work with zero configuration.
10. **`ALLOWED_BASE_DIR` env var** — Controls path sandboxing. Defaults to current working directory.
11. **ruff clean** — `ruff check examples/standalone_mcp_server.py` passes.

### Acceptance Criteria for P0.2 (test_mcp_tools.py)

1. **Interface tests pass immediately** — Each tool function exists, is async/awaitable, has docstring with Args.
2. **Functional tests pass** — `read_file` returns content, `write_file` creates files, `list_directory` returns listing, `search_web` returns results, `execute_python` runs code, `get_weather` returns weather.
3. **Error tests pass** — Path traversal raises ValueError, missing file raises FileNotFoundError, code syntax error returns error message.
4. **MCP protocol test** — FastMCP server starts, `list_tools()` returns 6 tools with correct names.
5. **ruff clean** — `ruff check tests/test_mcp_tools.py` passes.

### Acceptance Criteria for P0.3 (cursor/mcp.json)

1. **Valid JSON** — Parses with `json.load()`.
2. **Contains `mcpServers` key** — With `ai-vibe-coding` server entry.
3. **`command` is `python`** — Uses Python interpreter available in PATH.
4. **`args` references `standalone_mcp_server.py`** — Uses `${workspaceFolder}` variable.
5. **`env` contains `ALLOWED_BASE_DIR`** — Set to `${workspaceFolder}`.
6. **No hardcoded secrets** — No API keys in the JSON file.
7. **README section mentions this file** — Users know where to find it.

### Acceptance Criteria for P0.4 (claude_desktop_config.json)

1. **Valid JSON** — Parses with `json.load()`.
2. **Contains `mcpServers` key** — With `ai-vibe-coding` server entry.
3. **`command` is `python`** — Uses Python interpreter.
4. **`args` references `standalone_mcp_server.py`** — With `/ABSOLUTE/PATH/TO/` placeholder.
5. **`env` contains `ALLOWED_BASE_DIR`** — With `/ABSOLUTE/PATH/TO/` placeholder.
6. **Contains inline comments** — OS-specific config locations, path replacement instructions.
7. **No hardcoded secrets** — No API keys in the JSON file.

### Acceptance Criteria for P0.5 (README "Getting Started with MCP")

1. **Section exists in README.md** — After "Quick Start" section, before "Installation" or at bottom.
2. **Contains CLI commands** — Copy-pasteable bash commands to start the server.
3. **Contains MCP Inspector instructions** — How to verify the server works.
4. **Contains Cursor config instructions** — Steps to enable `.cursor/mcp.json`.
5. **Contains Claude Desktop instructions** — Steps to add `claude_desktop_config.json`.
6. **Contains tool reference table** — All 6 tools with descriptions.
7. **Contains security notes** — Path sandboxing, code execution limits.
8. **Links to config files** — Relative links to `.cursor/mcp.json` and `claude_desktop_config.json`.

---

## 8. Interface Contracts for Pre-Testing

For the pre-tester (child tasks), the following interface contracts define what must be tested:

### `test_mcp_tools.py` — Interface tests that must PASS immediately

These test that the standalone server module structure exists:

1. `test_mcp_module_imports` — `import examples.standalone_mcp_server` succeeds
2. `test_read_file_tool_exists` — `standalone_mcp_server.read_file` is callable
3. `test_write_file_tool_exists` — `standalone_mcp_server.write_file` is callable
4. `test_list_directory_tool_exists` — `standalone_mcp_server.list_directory` is callable
5. `test_search_web_tool_exists` — `standalone_mcp_server.search_web` is callable
6. `test_execute_python_tool_exists` — `standalone_mcp_server.execute_python` is callable
7. `test_get_weather_tool_exists` — `standalone_mcp_server.get_weather` is callable
8. `test_all_tools_have_docstrings` — Each tool function has a non-empty docstring
9. `test_mcp_instance_exists` — `standalone_mcp_server.mcp` is a FastMCP instance
10. `test_config_files_exist` — `.cursor/mcp.json` and `claude_desktop_config.json` exist and are valid JSON

### `test_mcp_tools.py` — Behavioral tests that must FAIL initially (stubs expected)

These test that the tools actually perform their functions:

1. `test_read_file_returns_content` — Reads a known file, returns its content
2. `test_read_file_traversal_blocked` — Path with `..` escapes raises ValueError
3. `test_write_file_creates_file` — Writes content, file exists with correct content
4. `test_write_file_creates_parent_dirs` — Writes to nested path, dirs created
5. `test_write_file_traversal_blocked` — Path with `..` escapes raises ValueError
6. `test_list_directory_default` — Returns listing for current directory
7. `test_list_directory_invalid_path` — Non-existent path raises FileNotFoundError
8. `test_search_web_returns_results` — Returns non-empty string with search terms
9. `test_execute_python_simple` — `print("hello")` returns "hello" in output
10. `test_execute_python_syntax_error` — Invalid Python returns error message
11. `test_execute_python_timeout` — Infinite loop raises TimeoutError or is terminated
12. `test_get_weather_returns_report` — Returns string with city name
13. `test_get_weather_unit_handling` — Both celsius and fahrenheit accepted
14. `test_mcp_server_list_tools` — FastMCP instance lists 6 tool names
15. `test_mcp_server_tool_names` — Tool names match expected: read_file, write_file, list_directory, search_web, execute_python, get_weather

### Config file tests (in `test_mcp_tools.py` or separate):

1. `test_cursor_mcp_json_valid` — `.cursor/mcp.json` parses as valid JSON
2. `test_cursor_mcp_json_structure` — Contains `mcpServers.ai-vibe-coding` with `command`, `args`, `env`
3. `test_cursor_mcp_json_no_secrets` — No API keys hardcoded
4. `test_claude_desktop_config_valid` — `claude_desktop_config.json` parses as valid JSON
5. `test_claude_desktop_config_structure` — Contains `mcpServers.ai-vibe-coding` with `command`, `args`, `env`
6. `test_claude_desktop_config_placeholder_path` — Args contain `/ABSOLUTE/PATH/TO/` placeholder

---

## 9. Stub File Requirements

For behavioral tests to fail with meaningful errors, the following stub implementations must exist in `examples/standalone_mcp_server.py`:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ai-vibe-coding-mcp")

@mcp.tool()
def read_file(path: str) -> str:
    raise NotImplementedError

@mcp.tool()
def write_file(path: str, content: str) -> str:
    raise NotImplementedError

@mcp.tool()
def list_directory(path: str = ".") -> str:
    raise NotImplementedError

@mcp.tool()
def search_web(query: str, max_results: int = 5) -> str:
    raise NotImplementedError

@mcp.tool()
def execute_python(code: str, timeout_seconds: int = 10) -> str:
    raise NotImplementedError

@mcp.tool()
def get_weather(city: str, unit: str = "celsius") -> str:
    raise NotImplementedError

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### Config file stub requirements:

**`.cursor/mcp.json`:**
```json
{
  "mcpServers": {
    "ai-vibe-coding": {
      "command": "python",
      "args": ["${workspaceFolder}/examples/standalone_mcp_server.py"],
      "env": {
        "ALLOWED_BASE_DIR": "${workspaceFolder}",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

**`claude_desktop_config.json`:**
```json
{
  "mcpServers": {
    "ai-vibe-coding": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/ai-vibe-coding-kit/examples/standalone_mcp_server.py"],
      "env": {
        "ALLOWED_BASE_DIR": "/ABSOLUTE/PATH/TO/ai-vibe-coding-kit",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

---

## 10. Dependencies Graph

```
t_4a693e43 (analyst — this task)
  └── t_XXXXXX (pre-tester): writes tests based on this analysis brief
       └── t_XXXXXX (developer): implements P0 items to pass pre-tests
            ├── t_XXXXXX (tech-lead): code review
            └── t_XXXXXX (tester): full validation
```

Implementation order:

```
standalone_mcp_server.py ← test_mcp_tools.py  ← .cursor/mcp.json
   (no deps)                 (tests the MCP       (points to server)
                              server tools)
                                    │
                          claude_desktop_config.json ← README "Getting Started" section
                           (points to server)          (references all above)
```

All P0 items can be implemented in parallel since the standalone server is independent of existing library code. The config files only need the server file path to exist.

---

## 11. Decision Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Standalone vs library server** | Both (Option C) | Standalone for quickstart newcomers; library for power users who want LLM-mediation + cost tracking |
| **Tool execution pattern** | Raw `@mcp.tool()` decorators | Standard FastMCP pattern; not LLM-routed — works without API keys |
| **Web search backend** | DuckDuckGo Lite HTML | Zero API keys, no registration, `httpx` already a dependency |
| **Code execution sandbox** | `subprocess` + `tempfile` | Stdlib-only; timeout enforced; network blocked via subprocess env |
| **Config file format** | JSON with `mcpServers` key | Standard across Cursor, Claude Desktop, Windsurf, Codex |
| **Cursor config location** | `.cursor/mcp.json` (per-project) | Auto-detected by Cursor; team shares via git |
| **Path sandboxing** | `ALLOWED_BASE_DIR` env var check in every file tool | Prevents path traversal; matches IDE workspace concept |
| **Transport default** | `stdio` | Simplest; works with all MCP clients; `transport="streamable-http"` documented as alternative |
| **MCP SDK version** | `mcp>=1.27,<2` | SDK v2 is in development; official recommendation to pin before stable |
| **README section placement** | After "Quick Start", before "Installation" | Natural progression: install → try basics → try MCP |

---

*End of analysis brief. Ready for pre-tester consumption.*
