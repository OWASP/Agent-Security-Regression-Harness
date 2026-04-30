"""Command line interface for the OWASP Agent Security Regression Harness."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_harness.runner import dry_run_scenario, run_scenario_with_trace
from agent_harness.scenario import ScenarioValidationError, load_scenario
from agent_harness.trace import TraceValidationError, load_trace


VERSION = "0.0.1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-harness",
        description=(
            "Run executable security regression scenarios against "
            "agentic applications and MCP-integrated systems."
        ),
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "version",
        help="Print the harness version.",
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a scenario file.",
    )
    validate_parser.add_argument(
        "scenario_file",
        help="Path to the scenario YAML file.",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="Run a scenario file.",
    )
    run_parser.add_argument(
        "scenario_file",
        help="Path to the scenario YAML file.",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the scenario and emit result JSON without executing a target.",
    )
    run_parser.add_argument(
        "--out",
        help="Optional path to write result JSON.",
    )
    run_parser.add_argument(
        "--trace-file",
        help="Evaluate assertions against an existing trace JSON file.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "version":
        print(f"agent-harness {VERSION}")
        return 0

    if args.command == "validate":
        try:
            scenario = load_scenario(args.scenario_file)
        except ScenarioValidationError as exc:
            print(f"invalid: {exc}", file=sys.stderr)
            return 1

        print(f"valid: {scenario.id}")
        return 0

    if args.command == "run":
        if args.dry_run and args.trace_file:
            parser.error("'run' accepts either --dry-run or --trace-file, not both")
        
        if not args.dry_run and not args.trace_file:
            parser.error("'run' currently requires --dry-run or --trace-file")

        try:
            scenario = load_scenario(args.scenario_file)
        except ScenarioValidationError as exc:
            print(f"invalid: {exc}", file=sys.stderr)
            return 1

        if args.dry_run:
            result = dry_run_scenario(scenario)
        else:
            try:
                trace = load_trace(args.trace_file)
            except TraceValidationError as exc:
                print(f"invalid trace: {exc}", file=sys.stderr)
                return 1

            result = run_scenario_with_trace(scenario, trace)
        
        result_json = result.to_json()
        if args.out:
            Path(args.out).write_text(result_json + "\n", encoding="utf-8")
        else:
            print(result_json)

        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())