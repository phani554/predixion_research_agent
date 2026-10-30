"""Command-line interface for the research agent."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from research_agent.agent import run_research
from research_agent.config import Settings
from research_agent.render import to_markdown


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments for the research agent CLI."""
    parser = argparse.ArgumentParser(
        prog="research_agent",
        description="Run deep, citation-backed research investigations.",
    )
    parser.add_argument("question", type=str, help="Research question to investigate")
    parser.add_argument("--json", action="store_true", help="Output the FinalAnswer as JSON")
    parser.add_argument("-v", "--verbose", action="store_true", help="Include metrics and execution details")
    parser.add_argument("--no-cache", action="store_true", help="Bypass cached tool responses")
    parser.add_argument("--fault", type=str, default=None, help="Inject fault for testing and evals")
    parser.add_argument("--out", type=str, default=None, help="Path to save the complete run result JSON")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: executes research, writes run artifact to disk, and prints output."""
    args = parse_args(argv)
    settings = Settings.from_env()

    result = run_research(args.question, settings=settings)

    # Persist the full RunResult to disk
    out_path = Path(args.out) if args.out else Path("outputs") / f"{result.run_id}.json"
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    except OSError as err:
        print(f"Warning: Failed to save run artifact to {out_path}: {err}", file=sys.stderr)

    # Format output according to requested format
    if args.json:
        print(result.answer.model_dump_json(indent=2))
    else:
        print(to_markdown(result, verbose=args.verbose))

    # Exit code: 0 for answered/partial, 2 otherwise
    return 0 if result.answer.status in ("answered", "partial") else 2


if __name__ == "__main__":
    sys.exit(main())

