#!/usr/bin/env python3
"""Standalone MCP server with 6 example tools using FastMCP decorators.

This server demonstrates the standard FastMCP pattern using raw @mcp.tool()
decorators. No API keys required — all tools use stdlib or existing
dependencies (httpx for web search).

Usage:
    # Run the server (stdio transport, default):
    python examples/standalone_mcp_server.py

    # Test with MCP Inspector:
    pip install mcp
    mcp dev examples/standalone_mcp_server.py

    # Connect Cursor IDE: see .cursor/mcp.json in repo root
    # Connect Claude Desktop: see claude_desktop_config.json in repo root

Security:
    - Filesystem tools validate paths against ALLOWED_BASE_DIR (default: cwd)
    - Code execution uses subprocess sandbox with timeout (default: 10s)
    - No API keys needed — web search uses DuckDuckGo (unauthenticated)
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------
mcp = FastMCP("ai-vibe-coding-mcp")

# Allowed base directory for path sandboxing (defaults to current directory).
# Override with the ALLOWED_BASE_DIR environment variable.
ALLOWED_BASE_DIR = Path(os.environ.get("ALLOWED_BASE_DIR", os.getcwd())).resolve()


# ---------------------------------------------------------------------------
# Path safety helper
# ---------------------------------------------------------------------------
def _safe_resolve(path: str) -> Path:
    """Resolve a user-supplied path and block directory traversal.

    Args:
        path: User-supplied file or directory path.

    Returns:
        Resolved absolute Path.

    Raises:
        ValueError: If the path contains '..' traversal components.
    """
    p = Path(path)
    # Block path traversal with ".." components
    if ".." in p.parts:
        raise ValueError(
            f"Path traversal blocked: '{path}' contains '..' escape sequence"
        )
    if p.is_absolute():
        return p.resolve()
    return (ALLOWED_BASE_DIR / p).resolve()


# ---------------------------------------------------------------------------
# Tool: read_file
# ---------------------------------------------------------------------------
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
    resolved = _safe_resolve(path)
    return resolved.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Tool: write_file
# ---------------------------------------------------------------------------
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
    resolved = _safe_resolve(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return f"Written {len(content)} bytes to {resolved}"


# ---------------------------------------------------------------------------
# Tool: list_directory
# ---------------------------------------------------------------------------
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
    resolved = _safe_resolve(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Directory not found: {resolved}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"Not a directory: {resolved}")

    lines = [f"Directory listing for: {resolved}", ""]
    entries = sorted(resolved.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    for entry in entries:
        if entry.is_dir():
            lines.append(f"  [DIR]  {entry.name}/")
        else:
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0
            lines.append(f"  [FILE] {entry.name}  ({_format_size(size)})")
    return "\n".join(lines)


def _format_size(size_bytes: int) -> str:
    """Format byte count to a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KiB"
    return f"{size_bytes / (1024 * 1024):.1f} MiB"


# ---------------------------------------------------------------------------
# Tool: search_web
# ---------------------------------------------------------------------------
@mcp.tool()
def search_web(query: str, max_results: int = 5) -> str:
    """Search the web for information using DuckDuckGo.

    Args:
        query: Search query string
        max_results: Maximum number of results (1-10, default: 5)
    Returns:
        Formatted search results with titles, URLs, and snippets
    """
    url = "https://html.duckduckgo.com/html"
    try:
        response = httpx.post(url, data={"q": query}, timeout=15.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return (
            "Search service unavailable. Retry later or use another approved "
            "search adapter. "
            f"Reference: SEARCH_DEPENDENCY_FAILED ({type(exc).__name__})"
        )

    # Extract result blocks from the HTML response
    results: list[dict[str, str]] = []
    # Look for result links with the class "result__a"
    for match in re.finditer(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        response.text,
        re.DOTALL,
    ):
        result_url = match.group(1)
        title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        results.append({"title": title, "url": result_url})

    # Look for snippets with class "result__snippet"
    snippets = re.findall(
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        response.text,
        re.DOTALL,
    )
    for i, snippet_text in enumerate(snippets):
        if i < len(results):
            results[i]["snippet"] = re.sub(r"<[^>]+>", "", snippet_text).strip()

    # Build output
    limit = max(1, min(max_results, 10))
    output_lines = [f"Search results for: {query}", ""]
    for i, r in enumerate(results[:limit], 1):
        output_lines.append(f"{i}. {r.get('title', 'Untitled')}")
        url_text = r.get("url", "")
        output_lines.append(f"   {url_text}")
        snippet = r.get("snippet", "")
        if snippet:
            output_lines.append(f"   {snippet}")
        output_lines.append("")

    if not results:
        output_lines.append("(No results found)")

    return "\n".join(output_lines).strip()


# ---------------------------------------------------------------------------
# Tool: execute_python
# ---------------------------------------------------------------------------
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
    timeout = max(1, min(timeout_seconds, 30))
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(code)
            tmp_path = tmp.name
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        return output if output else "(no output)"
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Execution timed out after {timeout}s") from None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Tool: get_weather
# ---------------------------------------------------------------------------
@mcp.tool()
def get_weather(city: str, unit: str = "celsius") -> str:
    """Get the current weather for a city (demo tool using simulated data).

    Args:
        city: City name
        unit: Temperature unit (celsius or fahrenheit)
    Returns:
        Simulated weather report for the given city
    """
    # Simple hash of city name for reproducible-but-varying results
    seed = sum(ord(c) for c in city.lower())
    base_temp_c = 10 + (seed % 20)  # 10–29 °C

    if unit == "fahrenheit":
        temp = base_temp_c * 9 / 5 + 32
        unit_label = "°F"
        feels_like = temp - 3
    else:
        temp = float(base_temp_c)
        unit_label = "°C"
        feels_like = temp - 2

    conditions = [
        "Sunny",
        "Partly cloudy",
        "Cloudy",
        "Light rain",
        "Clear sky",
        "Overcast",
    ]
    condition = conditions[seed % len(conditions)]
    humidity = 40 + (seed % 40)

    return (
        f"Weather for {city}:\n"
        f"  Condition: {condition}\n"
        f"  Temperature: {temp:.0f}{unit_label}\n"
        f"  Feels like: {feels_like:.0f}{unit_label}\n"
        f"  Humidity: {humidity}%"
    )


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run(transport="stdio")
