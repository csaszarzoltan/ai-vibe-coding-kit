"""Tests for MCP configuration templates.

Interface tests: validate that .cursor/mcp.json and claude_desktop_config.json
exist in the repo root, are valid JSON, and have the expected structure.

Behavioural tests: check for correct values (command, args, env).
Always pass since config files are static templates.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


# ── Interface tests (pass immediately) ──────────────────────────────────────


class TestCursorMCPConfig:
    """Tests for .cursor/mcp.json."""

    CONFIG_PATH = REPO_ROOT / ".cursor" / "mcp.json"

    def test_cursor_mcp_json_exists(self):
        """.cursor/mcp.json file exists."""
        assert self.CONFIG_PATH.exists(), f"{self.CONFIG_PATH} does not exist"

    def test_cursor_mcp_json_valid(self):
        """.cursor/mcp.json parses as valid JSON."""
        raw = self.CONFIG_PATH.read_text()
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_cursor_mcp_json_structure(self):
        """.cursor/mcp.json contains mcpServers.ai-vibe-coding with required keys."""
        raw = self.CONFIG_PATH.read_text()
        data = json.loads(raw)
        assert "mcpServers" in data
        server = data["mcpServers"].get("ai-vibe-coding")
        assert server is not None, "Missing 'ai-vibe-coding' server entry"
        assert "command" in server
        assert "args" in server
        assert isinstance(server["args"], list)
        assert "env" in server

    def test_cursor_mcp_json_command(self):
        """Command is 'python'."""
        raw = self.CONFIG_PATH.read_text()
        data = json.loads(raw)
        server = data["mcpServers"]["ai-vibe-coding"]
        assert server["command"] == "python"

    def test_cursor_mcp_json_args(self):
        """Args reference standalone_mcp_server.py with workspaceFolder variable."""
        raw = self.CONFIG_PATH.read_text()
        data = json.loads(raw)
        args = data["mcpServers"]["ai-vibe-coding"]["args"]
        assert any("standalone_mcp_server.py" in arg for arg in args)
        assert any("${workspaceFolder}" in arg for arg in args)

    def test_cursor_mcp_json_allowed_base_dir(self):
        """env.ALLOWED_BASE_DIR is set to ${workspaceFolder}."""
        raw = self.CONFIG_PATH.read_text()
        data = json.loads(raw)
        env = data["mcpServers"]["ai-vibe-coding"]["env"]
        assert "ALLOWED_BASE_DIR" in env
        assert "${workspaceFolder}" in env["ALLOWED_BASE_DIR"]

    def test_cursor_mcp_json_no_secrets(self):
        raw = self.CONFIG_PATH.read_text().lower()
        secrets = ["sk-", "api_key", "apikey", "secret", "token"]
        for s in secrets:
            assert s not in raw, (
                f"Secret '{s}' found in {self.CONFIG_PATH.name}"
            )


class TestClaudeDesktopConfig:
    """Tests for claude_desktop_config.json."""

    CONFIG_PATH = REPO_ROOT / "claude_desktop_config.json"

    def test_claude_desktop_config_exists(self):
        """claude_desktop_config.json file exists."""
        assert self.CONFIG_PATH.exists(), f"{self.CONFIG_PATH} does not exist"

    def test_claude_desktop_config_valid(self):
        """claude_desktop_config.json parses as valid JSON."""
        raw = self.CONFIG_PATH.read_text()
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_claude_desktop_config_structure(self):
        """Contains mcpServers key with command, args, env."""
        raw = self.CONFIG_PATH.read_text()
        data = json.loads(raw)
        assert "mcpServers" in data
        server = data["mcpServers"].get("ai-vibe-coding")
        assert server is not None, "Missing 'ai-vibe-coding' server entry"
        assert "command" in server
        assert "args" in server
        assert isinstance(server["args"], list)
        assert "env" in server

    def test_claude_desktop_config_command(self):
        """Command is 'python'."""
        raw = self.CONFIG_PATH.read_text()
        data = json.loads(raw)
        server = data["mcpServers"]["ai-vibe-coding"]
        assert server["command"] == "python"

    def test_claude_desktop_config_args(self):
        """Args reference standalone_mcp_server.py."""
        raw = self.CONFIG_PATH.read_text()
        data = json.loads(raw)
        args = data["mcpServers"]["ai-vibe-coding"]["args"]
        assert any("standalone_mcp_server.py" in arg for arg in args)

    def test_claude_desktop_config_placeholder_path(self):
        """Args contain /ABSOLUTE/PATH/TO/ placeholder for users to replace."""
        raw = self.CONFIG_PATH.read_text()
        data = json.loads(raw)
        args_str = " ".join(data["mcpServers"]["ai-vibe-coding"]["args"])
        assert "/ABSOLUTE/PATH/TO/" in args_str, (
            "Config should use /ABSOLUTE/PATH/TO/ placeholder"
        )

    def test_claude_desktop_config_allowed_base_dir(self):
        """env.ALLOWED_BASE_DIR uses placeholder path."""
        raw = self.CONFIG_PATH.read_text()
        data = json.loads(raw)
        env = data["mcpServers"]["ai-vibe-coding"]["env"]
        assert "ALLOWED_BASE_DIR" in env
        assert "/ABSOLUTE/PATH/TO/" in env["ALLOWED_BASE_DIR"]

    def test_claude_desktop_config_no_secrets(self):
        raw = self.CONFIG_PATH.read_text().lower()
        secrets = ["sk-", "api_key", "apikey", "secret", "token"]
        for s in secrets:
            assert s not in raw, (
                f"Secret '{s}' found in {self.CONFIG_PATH.name}"
            )
