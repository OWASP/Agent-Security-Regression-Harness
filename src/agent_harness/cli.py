"""Command line interface for the OWASP Agent Security Regression Harness."""

from __future__ import annotations

import argparse
import sys

from agent_harness.scenario import ScenarioValidationError, load_scenario


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
        help="Run a scenario file. Not implemented yet.",
    )
    run_parser.add_argument(
        "scenario_file",
        help="Path to the scenario YAML file.",
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
        parser.error("'run' is not implemented yet")

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())