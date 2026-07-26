"""Tests for standalone MCP server tools and config templates.

Convention (pre-tester):
    - Interface tests: MUST PASS immediately (module structure, imports, docstrings)
    - Behavioral tests: MUST FAIL with NotImplementedError (stub functions)
    - Config tests: Validate JSON structure, no hardcoded secrets, placeholder paths

Run:
    pytest tests/test_mcp_tools.py -v
    pytest tests/test_mcp_tools.py -v -k TestInterface   (fast smoke)
    pytest tests/test_mcp_tools.py -v -k TestBehavioral  (check NotImplementedError)
    pytest tests/test_mcp_tools.py -v -k TestConfigFiles  (config validation)
"""

import json
import sys
from pathlib import Path

import pytest

# Ensure repo root is on sys.path so `import examples.standalone_mcp_server` works
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ===================================================================
# Interface tests — must PASS immediately
# ===================================================================

class TestInterface:
    """Standalone module structure — imports, function existence, docstrings."""

    def test_mcp_module_imports(self):
        """Import examples.standalone_mcp_server succeeds."""
        import examples.standalone_mcp_server  # noqa: F401

    def test_read_file_tool_exists(self):
        """standalone_mcp_server.read_file is callable."""
        from examples import standalone_mcp_server
        assert callable(standalone_mcp_server.read_file)

    def test_write_file_tool_exists(self):
        """standalone_mcp_server.write_file is callable."""
        from examples import standalone_mcp_server
        assert callable(standalone_mcp_server.write_file)

    def test_list_directory_tool_exists(self):
        """standalone_mcp_server.list_directory is callable."""
        from examples import standalone_mcp_server
        assert callable(standalone_mcp_server.list_directory)

    def test_search_web_tool_exists(self):
        """standalone_mcp_server.search_web is callable."""
        from examples import standalone_mcp_server
        assert callable(standalone_mcp_server.search_web)

    def test_execute_python_tool_exists(self):
        """standalone_mcp_server.execute_python is callable."""
        from examples import standalone_mcp_server
        assert callable(standalone_mcp_server.execute_python)

    def test_get_weather_tool_exists(self):
        """standalone_mcp_server.get_weather is callable."""
        from examples import standalone_mcp_server
        assert callable(standalone_mcp_server.get_weather)

    def test_all_tools_have_docstrings(self):
        """Each tool function has a non-empty docstring with Args section."""
        from examples import standalone_mcp_server
        tool_names = [
            "read_file", "write_file", "list_directory",
            "search_web", "execute_python", "get_weather",
        ]
        for name in tool_names:
            func = getattr(standalone_mcp_server, name, None)
            assert func is not None, f"{name} not found in module"
            doc = func.__doc__
            assert doc, f"{name} is missing a docstring"
            assert len(doc.strip()) > 0, f"{name} docstring is empty"
            assert "Args:" in doc, f"{name} docstring missing Args: section"

    def test_mcp_instance_exists(self):
        """standalone_mcp_server.mcp is a FastMCP instance."""
        from mcp.server.fastmcp import FastMCP

        from examples import standalone_mcp_server
        assert isinstance(standalone_mcp_server.mcp, FastMCP)

    def test_config_files_exist(self):
        """Both config files exist and parse as valid JSON."""
        cursor_cfg = _REPO_ROOT / ".cursor" / "mcp.json"
        claude_cfg = _REPO_ROOT / "claude_desktop_config.json"
        assert cursor_cfg.is_file(), f"Missing: {cursor_cfg}"
        assert claude_cfg.is_file(), f"Missing: {claude_cfg}"
        # Valid JSON
        for path in (cursor_cfg, claude_cfg):
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            assert isinstance(data, dict), f"{path} should be a JSON object"

    @pytest.mark.asyncio
    async def test_mcp_tool_names(self):
        """MCP server lists 6 tools with expected names (registration check)."""
        from examples import standalone_mcp_server
        tools = await standalone_mcp_server.mcp.list_tools()
        names = [t.name for t in tools]
        expected = [
            "read_file",
            "write_file",
            "list_directory",
            "search_web",
            "execute_python",
            "get_weather",
        ]
        for exp in expected:
            assert exp in names, f"Missing tool: {exp}"
        assert len(tools) == len(expected)


# ===================================================================
# Behavioral tests — must FAIL with NotImplementedError initially
# ===================================================================

class TestBehavioral:
    """Tool functionality — stubs raise NotImplementedError until implemented."""

    # ------------------------------------------------------------------
    # read_file
    # ------------------------------------------------------------------

    def test_read_file_returns_content(self):
        """Reading a known file returns its content as a string."""
        from examples import standalone_mcp_server
        result = standalone_mcp_server.read_file("README.md")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_read_file_traversal_blocked(self):
        """Path traversal with '..' raises ValueError."""
        from examples import standalone_mcp_server
        with pytest.raises(ValueError, match="escape|traversal|base.dir|blocked"):
            standalone_mcp_server.read_file("../../etc/passwd")

    # ------------------------------------------------------------------
    # write_file
    # ------------------------------------------------------------------

    def test_write_file_creates_file(self):
        """Writing content creates a file with correct content."""
        from examples import standalone_mcp_server
        result = standalone_mcp_server.write_file(
            "/tmp/test_write_mcp.txt", "hello world"
        )
        assert isinstance(result, str)
        p = Path("/tmp/test_write_mcp.txt")
        assert p.exists(), "File was not created"
        assert p.read_text() == "hello world", "File content mismatch"

    def test_write_file_creates_parent_dirs(self):
        """Writing to a nested path creates parent directories."""
        from examples import standalone_mcp_server
        result = standalone_mcp_server.write_file(
            "/tmp/test_mcp_nested/a/b/c/file.txt", "nested"
        )
        assert isinstance(result, str)
        assert Path("/tmp/test_mcp_nested/a/b/c/file.txt").exists()

    def test_write_file_traversal_blocked(self):
        """Path traversal in write raises ValueError."""
        from examples import standalone_mcp_server
        with pytest.raises(ValueError, match="escape|traversal|base.dir|blocked"):
            standalone_mcp_server.write_file("../../etc/pwned", "evil")

    # ------------------------------------------------------------------
    # list_directory
    # ------------------------------------------------------------------

    def test_list_directory_default(self):
        """Default path returns a formatted listing string."""
        from examples import standalone_mcp_server
        result = standalone_mcp_server.list_directory()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_list_directory_invalid_path(self):
        """Non-existent directory raises FileNotFoundError."""
        from examples import standalone_mcp_server
        with pytest.raises(FileNotFoundError):
            standalone_mcp_server.list_directory(
                "/tmp/does_not_exist_xyz_999"
            )

    # ------------------------------------------------------------------
    # search_web
    # ------------------------------------------------------------------

    def test_search_web_returns_results(self):
        """Web search returns a non-empty result string."""
        from examples import standalone_mcp_server
        result = standalone_mcp_server.search_web("Python MCP FastMCP tutorial")
        assert isinstance(result, str)
        assert len(result) > 0

    # ------------------------------------------------------------------
    # execute_python
    # ------------------------------------------------------------------

    def test_execute_python_simple(self):
        """Simple code: print('hello') returns 'hello' in output."""
        from examples import standalone_mcp_server
        result = standalone_mcp_server.execute_python('print("hello")')
        assert isinstance(result, str)
        assert "hello" in result

    def test_execute_python_syntax_error(self):
        """Syntax error returns error message (does not crash)."""
        from examples import standalone_mcp_server
        result = standalone_mcp_server.execute_python("this is not valid python")
        assert isinstance(result, str)
        # Should contain error or traceback
        has_error = "error" in result.lower() or "traceback" in result.lower()
        assert has_error, "Expected error message for invalid syntax"

    def test_execute_python_timeout(self):
        """Infinite loop raises TimeoutError."""
        from examples import standalone_mcp_server
        with pytest.raises(TimeoutError):
            standalone_mcp_server.execute_python(
                "while True: pass", timeout_seconds=0.1
            )

    # ------------------------------------------------------------------
    # get_weather
    # ------------------------------------------------------------------

    def test_get_weather_returns_report(self):
        """Weather report contains the requested city name."""
        from examples import standalone_mcp_server
        result = standalone_mcp_server.get_weather("London")
        assert isinstance(result, str)
        assert "London" in result or "london" in result.lower()

    def test_get_weather_unit_handling(self):
        """Both celsius and fahrenheit units produce different output."""
        from examples import standalone_mcp_server
        celsius = standalone_mcp_server.get_weather("Paris", unit="celsius")
        fahrenheit = standalone_mcp_server.get_weather("Paris", unit="fahrenheit")
        assert isinstance(celsius, str)
        assert isinstance(fahrenheit, str)
        assert celsius != fahrenheit, "Different units should produce different output"


# ===================================================================
# Config file tests — JSON structure validation
# ===================================================================

class TestConfigFiles:
    """Validate .cursor/mcp.json and claude_desktop_config.json structure."""

    CURSOR_PATH = _REPO_ROOT / ".cursor" / "mcp.json"
    CLAUDE_PATH = _REPO_ROOT / "claude_desktop_config.json"

    # -- Cursor config (.cursor/mcp.json) --

    def test_cursor_mcp_json_valid(self):
        """.cursor/mcp.json parses as valid JSON."""
        raw = self.CURSOR_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_cursor_mcp_json_structure(self):
        """Contains mcpServers.ai-vibe-coding with command, args, env."""
        data = json.loads(self.CURSOR_PATH.read_text(encoding="utf-8"))
        assert "mcpServers" in data, "Missing mcpServers key"
        server = data["mcpServers"].get("ai-vibe-coding")
        assert server is not None, "Missing ai-vibe-coding server entry"
        assert server["command"] == "python", "command should be 'python'"
        assert isinstance(server.get("args"), list), "args should be a list"
        assert len(server["args"]) > 0, "args should not be empty"
        assert "standalone_mcp_server.py" in server["args"][0], (
            "Should reference standalone_mcp_server.py"
        )
        assert "${workspaceFolder}" in server["args"][0], (
            "Should use ${workspaceFolder} variable"
        )
        env = server.get("env", {})
        assert "ALLOWED_BASE_DIR" in env, "Missing ALLOWED_BASE_DIR env var"
        assert "PYTHONUNBUFFERED" in env, "Missing PYTHONUNBUFFERED env var"

    def test_cursor_mcp_json_no_secrets(self):
        """No hardcoded API keys or tokens in Cursor config."""
        content = self.CURSOR_PATH.read_text(encoding="utf-8").lower()
        secret_patterns = [
            "api_key", "apikey", "api-key",
            "token", "secret", "password",
        ]
        for pat in secret_patterns:
            assert pat not in content, (
                f"Potential secret found: '{pat}' in {self.CURSOR_PATH.name}"
            )

    # -- Claude Desktop config (claude_desktop_config.json) --

    def test_claude_desktop_config_valid(self):
        """claude_desktop_config.json parses as valid JSON."""
        raw = self.CLAUDE_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_claude_desktop_config_structure(self):
        """Contains mcpServers.ai-vibe-coding with command, args, env."""
        data = json.loads(self.CLAUDE_PATH.read_text(encoding="utf-8"))
        assert "mcpServers" in data, "Missing mcpServers key"
        server = data["mcpServers"].get("ai-vibe-coding")
        assert server is not None, "Missing ai-vibe-coding server entry"
        assert server["command"] == "python", "command should be 'python'"
        assert isinstance(server.get("args"), list), "args should be a list"
        assert len(server["args"]) > 0, "args should not be empty"
        assert "standalone_mcp_server.py" in server["args"][0], (
            "Should reference standalone_mcp_server.py"
        )
        env = server.get("env", {})
        assert "ALLOWED_BASE_DIR" in env, "Missing ALLOWED_BASE_DIR env var"
        assert "PYTHONUNBUFFERED" in env, "Missing PYTHONUNBUFFERED env var"

    def test_claude_desktop_config_placeholder_path(self):
        """Args contain /ABSOLUTE/PATH/TO/ placeholder for user to replace."""
        data = json.loads(self.CLAUDE_PATH.read_text(encoding="utf-8"))
        server = data["mcpServers"]["ai-vibe-coding"]
        args_str = " ".join(server["args"])
        assert "/ABSOLUTE/PATH/TO/" in args_str, (
            "Should contain /ABSOLUTE/PATH/TO/ placeholder"
        )
        env_str = str(server.get("env", {}))
        assert "/ABSOLUTE/PATH/TO/" in env_str, (
            "ALLOWED_BASE_DIR should use /ABSOLUTE/PATH/TO/ placeholder"
        )

    def test_claude_desktop_config_no_hardcoded_secrets(self):
        """No hardcoded API keys or tokens in Claude Desktop config."""
        content = self.CLAUDE_PATH.read_text(encoding="utf-8").lower()
        secret_patterns = [
            "api_key", "apikey", "api-key",
            "token", "secret", "password",
        ]
        for pat in secret_patterns:
            assert pat not in content, (
                f"Potential secret found: '{pat}' in {self.CLAUDE_PATH.name}"
            )
