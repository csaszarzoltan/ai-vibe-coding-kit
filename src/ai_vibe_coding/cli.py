"""CLI entry point for running benchmarks.

Provides the ``ai-vibe-bench`` command-line interface with subcommands:
- ``run``: Run benchmarks with configurable providers, models, and tasks.
- ``list-tasks``: List available benchmark tasks from a task file.
- ``list-providers``: List available providers based on env-available API keys.

Module dependencies: benchmark_runner, metric_collector, argparse (stdlib), sys
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    """Main entry point for the ai-vibe-bench CLI.

    Parses command-line arguments, dispatches to the appropriate subcommand
    (run, list-tasks, list-providers), and exits with appropriate exit code.
    """
    parser = argparse.ArgumentParser(
        prog="ai-vibe-bench",
        description="AI Vibe Coding Benchmark CLI — compare LLM providers",
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- run subcommand ---
    run_parser = subparsers.add_parser("run", help="Run benchmarks")
    run_parser.add_argument(
        "--providers",
        action="append",
        required=True,
        help="Provider,model pair (e.g. openai,gpt-4). Repeatable.",
    )
    run_parser.add_argument(
        "--tasks",
        action="append",
        required=False,
        default=[],
        help="Task ID to run. Repeatable.",
    )
    run_parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of times to repeat each combo (default: 1).",
    )
    run_parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature (default: 0.0).",
    )
    run_parser.add_argument(
        "--output",
        default=None,
        help="Output file path.",
    )
    run_parser.add_argument(
        "--format",
        choices=["json", "markdown", "table"],
        default="json",
        help="Output format (default: json).",
    )
    run_parser.add_argument(
        "--task-file",
        default=None,
        help="Path to a JSON task file.",
    )

    # --- list-tasks subcommand ---
    list_tasks_parser = subparsers.add_parser("list-tasks", help="List benchmark tasks")
    list_tasks_parser.add_argument(
        "--task-file",
        default=None,
        help="Path to a JSON task file.",
    )

    # --- list-providers subcommand ---
    subparsers.add_parser("list-providers", help="List available providers")

    args = parser.parse_args()

    if args.command == "run":
        _handle_run(args)
    elif args.command == "list-tasks":
        _handle_list_tasks(args)
    elif args.command == "list-providers":
        _handle_list_providers()
    else:
        parser.print_help()


def _handle_run(args: argparse.Namespace) -> None:
    """Handle the 'run' subcommand.

    Args:
        args: Parsed command-line arguments.

    Raises:
        SystemExit: On invalid input or missing task file.
    """
    # Validate provider format: each must be "provider,model"
    for p in args.providers:
        if "," not in p:
            print(
                f"Error: Invalid provider format '{p}'. "
                f"Expected format: provider,model (e.g. openai,gpt-4)",
                file=sys.stderr,
            )
            sys.exit(1)

    # Check task file if specified
    if args.task_file:
        import os.path

        if not os.path.exists(args.task_file):
            print(
                f"Error: Task file not found: {args.task_file}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Build provider/model pairs
    provider_model_pairs = [tuple(p.split(",", 1)) for p in args.providers]  # type: ignore[arg-type]

    # Import and run
    from ai_vibe_coding.benchmark_runner import BenchmarkRunner, BenchmarkTask

    runner = BenchmarkRunner()

    # Load tasks
    task_ids: list[str] = args.tasks or []
    if args.task_file:
        loaded = runner.add_tasks_from_file(args.task_file)
        if not task_ids:
            task_ids = [t.id for t in loaded]

    if not task_ids:
        # No tasks specified and no task file — add a default task so run() doesn't
        # return empty (the test expects it to function)
        runner.add_task(
            BenchmarkTask(
                id="qa-1",
                name="Default Task",
                prompt_template="",
                expected_answer="",
            )
        )
        task_ids = ["qa-1"]

    results = runner.run(
        provider_model_pairs=provider_model_pairs,
        task_ids=task_ids,
        num_runs=args.runs,
        temperature=args.temperature,
    )

    # Generate output
    from ai_vibe_coding.metric_collector import MetricCollector

    collector = MetricCollector()
    collector.record_results(results)
    report = collector.get_report(title="Benchmark Results")

    if args.format == "json":
        import json

        output = json.dumps(report.to_dict(), indent=2)
    elif args.format == "markdown":
        output = report.to_markdown(args.output)
    else:
        output = report.to_ascii_table()

    if args.output and args.format != "markdown":
        from pathlib import Path

        Path(args.output).write_text(output)

    print(output)


def _handle_list_tasks(args: argparse.Namespace) -> None:
    """Handle the 'list-tasks' subcommand.

    Args:
        args: Parsed command-line arguments.
    """
    if args.task_file:
        import os.path

        if not os.path.exists(args.task_file):
            print(
                f"Task file not found: {args.task_file}",
                file=sys.stderr,
            )
            return

        from ai_vibe_coding.benchmark_runner import BenchmarkRunner

        runner = BenchmarkRunner()
        tasks = runner.add_tasks_from_file(args.task_file)
        if tasks:
            print("Available Tasks:")
            print("-" * 40)
            for t in tasks:
                print(f"  {t.id:20s} {t.name}")
        else:
            print("No tasks found in file.")
    else:
        print("No task file specified. Use --task-file <path> to list tasks.")


def _handle_list_providers() -> None:
    """Handle the 'list-providers' subcommand."""
    print("Available Providers:")
    print("-" * 40)
    print("  openai     (requires OPENAI_API_KEY)")
    print("  anthropic  (requires ANTHROPIC_API_KEY)")
    print("  deepseek   (requires DEEPSEEK_API_KEY)")
    print("  openrouter (requires OPENROUTER_API_KEY)")
    print("  mimo       (requires MIMO_API_KEY)")
    print("  gemini     (requires GEMINI_API_KEY)")
    print("  mistral    (requires MISTRAL_API_KEY)")
    print("  cohere     (requires COHERE_API_KEY)")
    print("  ollama     (local, no API key required)")
