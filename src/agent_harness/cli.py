"""Command line interface for the OWASP Agent Security Regression Harness."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_harness.adapters import AdapterError
from agent_harness.runner import (
    dry_run_scenario, 
    run_scenario_live, 
    run_scenario_with_trace
)
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
    run_parser.add_argument(
        "--live",
        action="store_true",
        help="Run the scenario against a live target.",
    )
    run_parser.add_argument(
        "--target-url",
        help="HTTP URL for the live target.",
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
        selected_modes = [
            args.dry_run,
            args.trace_file is not None,
            args.live,
        ]

        if sum(bool(mode) for mode in selected_modes) != 1:
            parser.error("'run' requires exactly one of --dry-run, --trace-file, or --live"
            )

        if args.live and not args.target_url:
            parser.error("'run --live' requires --target-url")
        
        if args.target_url and not args.live:
            parser.error("--target-url can only be used with --live")

        try:
            scenario = load_scenario(args.scenario_file)
        except ScenarioValidationError as exc:
            print(f"invalid: {exc}", file=sys.stderr)
            return 1

        if args.dry_run:
            result = dry_run_scenario(scenario)
        elif args.live:
            try:
                assert args.target_url is not None
                result = run_scenario_live(scenario, args.target_url)
            except AdapterError as exc:
                print(f"adapter error: {exc}", file=sys.stderr)
                return 1

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