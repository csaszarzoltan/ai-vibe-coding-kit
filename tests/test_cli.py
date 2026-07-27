"""Pre-development tests for cli.py (Task P1.1-P1.3).

Interface tests verify the CLI module structure and subcommand registration
— these must PASS immediately with the stub implementation.

Behavioral tests define the expected CLI behaviour that the developer must
make green by implementing the stubs — these must FAIL with NotImplementedError.

pytest markers:
    @pytest.mark.unit — no external dependencies, no subprocess calls
"""

from __future__ import annotations

import pytest

from ai_vibe_coding import cli

# ──────────────────────────────────────────────────────────────
# Interface smoke tests (should PASS — verify API surface exists)
# ──────────────────────────────────────────────────────────────


class TestCLIInterface:
    """Verify CLI module has expected structure."""

    def test_cli_main_exists(self):
        """main() should be a callable function from ai_vibe_coding.cli."""
        assert callable(cli.main)

    def test_cli_module_imports(self):
        """cli module should be importable without error."""
        import ai_vibe_coding.cli  # noqa: F811

        assert hasattr(ai_vibe_coding.cli, "main")

    def test_cli_main_accepts_no_args(self):
        """main() should accept being called with no arguments."""
        # We only test that the function exists and is callable
        # (will raise NotImplementedError when called)
        pass


# ──────────────────────────────────────────────────────────────
# Behavioral pre-state tests (should FAIL — NotImplementedError)
# These define the contract the developer must satisfy.
# ──────────────────────────────────────────────────────────────


class TestCLIRun:
    """Behavioral tests for 'ai-vibe-bench run' — fail until implemented."""

    @pytest.mark.unit
    def test_cli_run_with_args(self):
        """Running with --providers and --tasks should produce output."""
        import sys

        # Simulate CLI invocation
        saved_argv = sys.argv
        try:
            sys.argv = [
                "ai-vibe-bench",
                "run",
                "--providers", "openai,gpt-4",
                "--tasks", "qa-1",
            ]
            cli.main()
        finally:
            sys.argv = saved_argv

    @pytest.mark.unit
    def test_cli_run_invalid_provider_format(self):
        """Invalid --providers format should exit non-zero."""
        import sys

        saved_argv = sys.argv
        try:
            sys.argv = [
                "ai-vibe-bench",
                "run",
                "--providers", "invalid_format_no_comma",
                "--tasks", "qa-1",
            ]
            with pytest.raises(SystemExit) as exc:
                cli.main()
            assert exc.value.code != 0
        finally:
            sys.argv = saved_argv

    @pytest.mark.unit
    def test_cli_run_missing_task_file(self):
        """Missing --task-file path should exit non-zero."""
        import sys

        saved_argv = sys.argv
        try:
            sys.argv = [
                "ai-vibe-bench",
                "run",
                "--providers", "openai,gpt-4",
                "--tasks", "qa-1",
                "--task-file", "/nonexistent/path/tasks.json",
            ]
            with pytest.raises(SystemExit) as exc:
                cli.main()
            assert exc.value.code != 0
        finally:
            sys.argv = saved_argv


class TestCLIListTasks:
    """Behavioral tests for 'ai-vibe-bench list-tasks' — fail until implemented."""

    @pytest.mark.unit
    def test_cli_list_tasks_subcommand(self):
        """list-tasks subcommand should list tasks from a task file."""
        import sys

        saved_argv = sys.argv
        try:
            sys.argv = [
                "ai-vibe-bench",
                "list-tasks",
                "--task-file", "/nonexistent/tasks.json",
            ]
            cli.main()
        finally:
            sys.argv = saved_argv

    @pytest.mark.unit
    def test_cli_list_tasks_without_file(self):
        """list-tasks without --task-file should still work (use default)."""
        import sys

        saved_argv = sys.argv
        try:
            sys.argv = [
                "ai-vibe-bench",
                "list-tasks",
            ]
            cli.main()
        finally:
            sys.argv = saved_argv


class TestCLIListProviders:
    """Behavioral tests for 'ai-vibe-bench list-providers' — fail until implemented."""

    @pytest.mark.unit
    def test_cli_list_providers_subcommand(self):
        """list-providers subcommand should list available providers."""
        import sys

        saved_argv = sys.argv
        try:
            sys.argv = [
                "ai-vibe-bench",
                "list-providers",
            ]
            cli.main()
        finally:
            sys.argv = saved_argv
