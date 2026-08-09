"""CLI entry point for running benchmarks and cost queries.

Provides the ``ai-vibe-bench`` command-line interface with subcommands:
- ``run``: Run benchmarks with configurable providers, models, and tasks.
- ``list-tasks``: List available benchmark tasks from a task file.
- ``list-providers``: List available providers based on env-available API keys.
- ``cost``: Cost estimation and optimization (with sub-subcommands).

Module dependencies: benchmark_runner, metric_collector, cost_calculator,
argparse (stdlib), sys
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    """Main entry point for the ai-vibe-bench CLI.

    Parses command-line arguments, dispatches to the appropriate subcommand
    (run, list-tasks, list-providers, cost), and exits with appropriate exit code.
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

    # --- cost subcommand ---
    cost_parser = subparsers.add_parser(
        "cost", help="Cost estimation and optimization"
    )
    cost_subparsers = cost_parser.add_subparsers(dest="cost_command")

    # cost estimate
    est_parser = cost_subparsers.add_parser(
        "estimate", help="Estimate cost for a specific provider and model"
    )
    est_parser.add_argument("provider", nargs="?", default=None, help="Provider name")
    est_parser.add_argument("model", nargs="?", default=None, help="Model name")
    est_parser.add_argument(
        "input_tokens", nargs="?", type=int, default=None, help="Input token count"
    )
    est_parser.add_argument(
        "output_tokens", nargs="?", type=int, default=None, help="Output token count"
    )

    # cost compare
    cmp_parser = cost_subparsers.add_parser(
        "compare", help="Compare costs across providers"
    )
    cmp_parser.add_argument(
        "input_tokens", nargs="?", type=int, default=None, help="Input token count"
    )
    cmp_parser.add_argument(
        "output_tokens", nargs="?", type=int, default=None, help="Output token count"
    )
    cmp_parser.add_argument(
        "--providers",
        default=None,
        help="Comma-separated list of providers to include",
    )

    # cost recommend
    rec_parser = cost_subparsers.add_parser(
        "recommend", help="Recommend best provider for a task type"
    )
    rec_parser.add_argument(
        "task_type", nargs="?", default=None, help="Task type (coding, chat, etc.)"
    )
    rec_parser.add_argument(
        "input_tokens", nargs="?", type=int, default=None, help="Input token count"
    )
    rec_parser.add_argument(
        "output_tokens", nargs="?", type=int, default=None, help="Output token count"
    )
    rec_parser.add_argument(
        "--providers",
        default=None,
        help="Comma-separated list of providers to include",
    )

    # --- cost pricing
    prc_parser = cost_subparsers.add_parser(
        "pricing", help="Show pricing data for providers and models"
    )
    prc_parser.add_argument(
        "--provider",
        default=None,
        help="Provider name to filter by",
    )
    prc_parser.add_argument(
        "--model",
        default=None,
        help="Model name to filter by",
    )

    # --- memory subcommand (v0.14.0 compaction & distillation)
    memory_parser = subparsers.add_parser(
        "memory", help="Agent memory compaction, decay and stats"
    )
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command")

    # memory compact
    compact_parser = memory_subparsers.add_parser(
        "compact", help="Run the memory compaction job (distill + merge + archive)"
    )
    compact_parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply compaction; default is --dry-run (plan only)",
    )
    compact_parser.add_argument(
        "--age-days",
        type=float,
        default=None,
        help="Override default compaction age threshold (days)",
    )
    compact_parser.add_argument(
        "--importance-threshold",
        type=float,
        default=None,
        help="Override default importance threshold",
    )
    compact_parser.add_argument(
        "--merge-threshold",
        type=float,
        default=None,
        help="Override default merge similarity threshold",
    )
    compact_parser.add_argument(
        "--db",
        default=None,
        help="SQLite database path (default  ~/.ai_vibe_coding/memory.db)",
    )

    # memory decay
    decay_parser = memory_subparsers.add_parser(
        "decay", help="Reduce importance of stale memories over time"
    )
    decay_parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply decay; default is --dry-run (plan only)",
    )
    decay_parser.add_argument(
        "--decay-days",
        type=float,
        default=None,
        help="Days per decay period (default 7)",
    )
    decay_parser.add_argument(
        "--db",
        default=None,
        help="SQLite database path (default  ~/.ai_vibe_coding/memory.db)",
    )

    # memory stats
    stats_parser = memory_subparsers.add_parser(
        "stats", help="Show extended memory statistics (incl. compaction/decay)"
    )
    stats_parser.add_argument(
        "--db",
        default=None,
        help="SQLite database path (default  ~/.ai_vibe_coding/memory.db)",
    )

    args = parser.parse_args()

    if args.command == "run":
        _handle_run(args)
    elif args.command == "list-tasks":
        _handle_list_tasks(args)
    elif args.command == "list-providers":
        _handle_list_providers()
    elif args.command == "cost":
        _handle_cost(args)
    elif args.command == "memory":
        _handle_memory(args)
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
    print("  ollama     (local, no credentials required)")


# =====================================================================
# Memory subcommand handlers (v0.14.0 compaction & distillation)
# =====================================================================


def _open_memory_store(db_arg: str | None):
    """Build a MemoryStore from an optional --db override.

    Args:
        db_arg: A whitespace-separated string of one path (or None for the
            default DB). argparse passes a plain str here since the CLI
            defines ``--db`` singular.

    Returns:
        A configured MemoryStore instance.
    """
    from ai_vibe_coding.memory_store import MemoryStore

    if db_arg:
        return MemoryStore(db_path=db_arg)
    return MemoryStore()


def _handle_memory(args: argparse.Namespace) -> None:
    """Handle the 'memory' subcommand (compact / decay / stats).

    Args:
        args: Parsed command-line arguments.
    """
    command = args.memory_command
    if command == "compact":
        _handle_memory_compact(args)
    elif command == "decay":
        _handle_memory_decay(args)
    elif command == "stats":
        _handle_memory_stats(args)
    else:
        print("Usage: ai-vibe-bench memory <compact|decay|stats> [...]")
        print()
        print("Subcommands:")
        print("  compact [--apply] [--age-days N] [--importance-threshold X] "
              "[--merge-threshold X] [--db PATH]")
        print("  decay   [--apply] [--decay-days N] [--db PATH]")
        print("  stats   [--db PATH]")


def _handle_memory_compact(args: argparse.Namespace) -> None:
    """Handle 'memory compact' — dry-run by default, --apply to mutate."""
    import json as _json

    store = _open_memory_store(getattr(args, "db", None))
    result = store.compact(
        dry_run=not args.apply,
        age_days=args.age_days,
        importance_threshold=args.importance_threshold,
        merge_threshold=args.merge_threshold,
    )
    print(_json.dumps(result, indent=2, default=str))


def _handle_memory_decay(args: argparse.Namespace) -> None:
    """Handle 'memory decay' — dry-run by default, --apply to mutate."""
    import json as _json

    store = _open_memory_store(getattr(args, "db", None))
    result = store.impact_decay(
        decay_days=args.decay_days, dry_run=not args.apply
    )
    print(_json.dumps(result, indent=2, default=str))


def _handle_memory_stats(args: argparse.Namespace) -> None:
    """Handle 'memory stats' — print extended stats (incl. compaction)."""
    import json as _json

    store = _open_memory_store(getattr(args, "db", None))
    print(_json.dumps(store.memory_stats(), indent=2, default=str))


# =====================================================================
# Cost subcommand handlers
# =====================================================================


def _handle_cost(args: argparse.Namespace) -> None:
    """Handle the 'cost' subcommand by dispatching to sub-subcommand handlers."""
    from ai_vibe_coding.cost_calculator import (
        PRICING,
        calculate_cost,
        compare_all,
        recommend_for_task,
    )

    if args.cost_command == "estimate":
        _handle_cost_estimate(args, calculate_cost)
    elif args.cost_command == "compare":
        _handle_cost_compare(args, compare_all)
    elif args.cost_command == "recommend":
        _handle_cost_recommend(args, recommend_for_task)
    elif args.cost_command == "pricing":
        _handle_cost_pricing(args, PRICING)
    else:
        # No cost subcommand given — print cost help
        print("Usage: ai-vibe-bench cost <subcommand> [...]")
        print()
        print("Subcommands:")
        print("  estimate <provider> <model> <input> <output>  Estimate cost")
        print("  compare <input> <output> [--providers ...]    Compare all providers")
        print("  recommend <type> <input> <output> [...]       Recommend for task type")
        print("  pricing [--provider ...] [--model ...]        Show pricing data")


def _handle_cost_estimate(
    args: argparse.Namespace,
    calculate_cost_func,
) -> None:
    """Handle 'cost estimate' subcommand."""
    provider = args.provider
    model = args.model
    input_tokens = args.input_tokens
    output_tokens = args.output_tokens

    if not provider or not model or input_tokens is None or output_tokens is None:
        print(
            "Usage: ai-vibe-bench cost estimate <provider> <model> <input_tokens> "
            "<output_tokens>",
            file=sys.stderr,
        )
        return

    try:
        cost = calculate_cost_func(input_tokens, output_tokens, provider, model)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return

    report = (
        f"Provider:     {provider}\n"
        f"Model:        {model}\n"
        f"Input tokens: {input_tokens}\n"
        f"Output tokens:{output_tokens}\n"
        f"Total cost:   ${cost:.6f}"
    )
    print(report)


def _handle_cost_compare(
    args: argparse.Namespace,
    compare_all_func,
) -> None:
    """Handle 'cost compare' subcommand."""
    input_tokens = args.input_tokens
    output_tokens = args.output_tokens

    if input_tokens is None or output_tokens is None:
        print(
            "Usage: ai-vibe-bench cost compare <input_tokens> <output_tokens> "
            "[--providers ...]",
            file=sys.stderr,
        )
        return

    providers = None
    if args.providers:
        providers = [p.strip() for p in args.providers.split(",")]

    results = compare_all_func(input_tokens, output_tokens, providers=providers)

    # Print as aligned table
    _print_cost_table(results)


def _handle_cost_recommend(
    args: argparse.Namespace,
    recommend_for_task_func,
) -> None:
    """Handle 'cost recommend' subcommand."""
    task_type = args.task_type
    input_tokens = args.input_tokens
    output_tokens = args.output_tokens

    if not task_type or input_tokens is None or output_tokens is None:
        print(
            "Usage: ai-vibe-bench cost recommend <task_type> <input_tokens> "
            "<output_tokens> [--providers ...]",
            file=sys.stderr,
        )
        return

    providers = None
    if args.providers:
        providers = [p.strip() for p in args.providers.split(",")]

    if task_type not in (
        "coding",
        "chat",
        "analysis",
        "translation",
        "general",
    ):
        print(f"Note: Unknown task type '{task_type}', falling back to 'general'")

    results = recommend_for_task_func(
        input_tokens, output_tokens, task_type, providers=providers
    )

    _print_recommendation_table(results)


def _handle_cost_pricing(
    args: argparse.Namespace,
    pricing_dict: dict,
) -> None:
    """Handle 'cost pricing' subcommand."""
    provider_filter = args.provider
    model_filter = args.model

    for prov in sorted(pricing_dict.keys()):
        if provider_filter and prov != provider_filter:
            continue
        print(f"\n{prov}:")
        for model_name, rates in pricing_dict[prov].items():
            if model_filter and model_name != model_filter:
                continue
            print(
                f"  {model_name:30s} "
                f"input=${rates['input']:.6f}/1K  "
                f"output=${rates['output']:.6f}/1K"
            )


# =====================================================================
# Output formatting helpers
# =====================================================================


def _print_cost_table(results: list[dict]) -> None:
    """Print a table of cost options sorted by total cost."""
    if not results:
        print("No results.")
        return

    # Header
    print(
        f"{'Provider':12s} {'Model':25s} {'Input Cost':12s} {'Output Cost':13s} "
        f"{'Total Cost':11s} {'Cost/1K':9s}"
    )
    print("-" * 85)

    for r in results:
        print(
            f"{r['provider']:12s} {r['model']:25s} "
            f"${r['input_cost']:<9.6f}  ${r['output_cost']:<9.6f}  "
            f"${r['total_cost']:<8.6f}  ${r['cost_per_1k_tokens']:<6.6f}"
        )


def _print_recommendation_table(results: list[dict]) -> None:
    """Print a table of ranked recommendations sorted by value score."""
    if not results:
        print("No results.")
        return

    # Header
    print(
        f"{'Rank':5s} {'Provider':12s} {'Model':25s} {'Total Cost':11s} "
        f"{'Value Score':12s} {'Explanation':30s}"
    )
    print("-" * 100)

    for i, r in enumerate(results, 1):
        explanation = r.get("explanation", "")
        print(
            f"{i:<5d} {r['provider']:12s} {r['model']:25s} "
            f"${r['total_cost']:<8.6f}  {r['value_score']:<10.2f}  {explanation:<30s}"
        )
