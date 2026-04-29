"""Command line interface for the OWASP Agent Security Regression Harness."""

from __future__ import annotations

import argparse


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

    subparsers.add_parser(
        "validate",
        help="Validate a scenario file. Not implemented yet.",
    )

    subparsers.add_parser(
        "run",
        help="Run a scenario file. Not implemented yet.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "version":
        print(f"agent-harness {VERSION}")
        return 0

    if args.command in {"validate", "run"}:
        parser.error(f"'{args.command}' is not implemented yet")

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())