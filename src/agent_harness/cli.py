"""Command line interface for the OWASP Agent Security Regression Harness."""

from __future__ import annotations

import argparse
import glob
import re
import sys
from pathlib import Path

from agent_harness.adapters import DEFAULT_HTTP_TIMEOUT_SECONDS, AdapterError
from agent_harness.junit import result_to_junit_xml
from agent_harness.runner import (
    dry_run_scenario,
    run_scenario_live,
    run_scenario_with_langchain_target,
    run_scenario_with_mcp_host_target,
    run_scenario_with_mcp_target,
    run_scenario_with_openai_agent,
    run_scenario_with_python_target,
    run_scenario_with_trace,
)
from agent_harness.sarif import result_to_sarif
from agent_harness.scenario import ScenarioValidationError, load_scenario
from agent_harness.trace import TraceValidationError, load_trace

VERSION = "0.1.0"
HEADER_NAME_RE = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


def parse_target_headers(raw_headers: list[str] | None) -> dict[str, str]:
    """Parse NAME=VALUE HTTP header arguments for live target requests."""
    parsed: dict[str, str] = {}
    for raw_header in raw_headers or []:
        if "=" not in raw_header:
            raise ValueError("header must use NAME=VALUE format")

        name, value = raw_header.split("=", 1)
        name = name.strip()

        if not name:
            raise ValueError("header name must not be empty")
        if not HEADER_NAME_RE.fullmatch(name):
            raise ValueError(f"invalid header name: {name!r}")
        if "\r" in value or "\n" in value:
            raise ValueError(f"header {name!r} must not contain newlines")

        parsed[name] = value

    return parsed


def _discover_scenario_files(patterns: list[str]) -> list[Path]:
    """Return unique scenario files matched by files, directories, or globs."""
    scenario_files: list[Path] = []
    seen: set[Path] = set()

    for pattern in patterns:
        path = Path(pattern)
        if path.is_dir():
            matches = sorted(
                matched
                for suffix in ("*.yaml", "*.yml")
                for matched in path.rglob(suffix)
                if matched.is_file()
            )
        else:
            glob_matches = sorted(Path(match) for match in glob.glob(pattern, recursive=True))
            matches = glob_matches if glob_matches else [path]

        for match in matches:
            normalized = match.resolve()
            if normalized in seen or not match.is_file():
                continue
            seen.add(normalized)
            scenario_files.append(match)

    return scenario_files


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
        help="Validate scenario files, directories, or glob patterns.",
    )
    validate_parser.add_argument(
        "scenario_paths",
        nargs="+",
        help="Scenario YAML file, directory, or glob pattern to validate.",
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
        "--junit-out",
        help="Optional path to write assertion results as JUnit XML.",
    )
    run_parser.add_argument(
        "--trace-file",
        help="Evaluate assertions against an existing trace JSON file.",
    )
    run_parser.add_argument(
        "--live",
        action="store_true",
        help="Run the scenario against a live HTTP target.",
    )
    run_parser.add_argument(
        "--target-url",
        help="HTTP URL for the live target.",
    )
    run_parser.add_argument(
        "--target-timeout",
        type=int,
        help=(
            "Timeout in seconds for live HTTP target requests "
            f"(default: {DEFAULT_HTTP_TIMEOUT_SECONDS})."
        ),
    )
    run_parser.add_argument(
        "--target-header",
        action="append",
        metavar="NAME=VALUE",
        help=(
            "Optional HTTP header for live target requests. Repeat for multiple "
            "headers. Header values are sent to the target only and are not "
            "stored in scenario files or result JSON."
        ),
    )
    run_parser.add_argument(
        "--python-target",
        help=(
            "Run the scenario against a local Python callable target in "
            "module:function format."
        ),
    )
    run_parser.add_argument(
        "--openai-agent",
        help=(
            "Run the scenario against an OpenAI Agents SDK Agent loaded from "
            "a module:object import path."
        ),
    )
    run_parser.add_argument(
        "--mcp-target",
        help=(
            "Run the scenario against a local MCP-integrated workflow callable "
            "in module:function format."
        ),
    )
    run_parser.add_argument(
        "--mcp-host-target",
        help=(
            "Run the scenario against a local callable MCP host target in "
            "module:function format."
        ),
    )
    run_parser.add_argument(
        "--mcp-runtime-config",
        help="Path to the MCP runtime config YAML used with --mcp-host-target.",
    )
    run_parser.add_argument(
        "--langchain-target",
        help=(
            "Run the scenario against a LangChain/LangGraph target loaded from "
            "a module:object import path."
        ),
    )
    run_parser.add_argument(
        "--langchain-goal-event",
        help="Optional goal event id recorded in the LangChain/LangGraph trace.",
    )
    run_parser.add_argument(
        "--openai-agent-max-turns",
        type=int,
        help="Optional max_turns value passed to the OpenAI Agents SDK runner.",
    )
    run_parser.add_argument(
        "--sarif-out",
        help="Optional path to write assertion results as SARIF 2.1.0.",
    )
    run_parser.add_argument(
        "--exit-on-fail",
        action="store_true",
        help=(
            "Exit with code 1 if the overall result is 'fail' or 'error'. "
            "Useful for gating CI on assertion failures. Without this flag, "
            "'agent-harness run' always exits 0 on successful runs regardless "
            "of assertion outcomes."
        ),
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "version":
        print(f"agent-harness {VERSION}")
        return 0

    if args.command == "validate":
        scenario_files = _discover_scenario_files(args.scenario_paths)
        if not scenario_files:
            print("invalid: no scenario files matched", file=sys.stderr)
            return 1

        valid_count = 0
        invalid_count = 0

        for scenario_file in scenario_files:
            try:
                scenario = load_scenario(scenario_file)
            except ScenarioValidationError as exc:
                invalid_count += 1
                print(f"invalid: {scenario_file}: {exc}", file=sys.stderr)
                continue

            valid_count += 1
            print(f"valid: {scenario_file}: {scenario.id}")

        print(f"summary: {valid_count} valid, {invalid_count} invalid")
        return 1 if invalid_count else 0


    if args.command == "run":
        selected_modes = [
            args.dry_run,
            args.trace_file is not None,
            args.live,
            args.python_target is not None,
            args.openai_agent is not None,
            args.mcp_target is not None,
            args.mcp_host_target is not None,
            args.langchain_target is not None,
        ]

        if sum(bool(mode) for mode in selected_modes) != 1:
            parser.error(
                "'run' requires exactly one of --dry-run, --trace-file, "
                "--live, --python-target, --openai-agent, --mcp-target, "
                "--mcp-host-target, or --langchain-target"
            )

        if args.live and not args.target_url:
            parser.error("'run --live' requires --target-url")

        if args.target_url and not args.live:
            parser.error("--target-url can only be used with --live")

        if args.target_timeout is not None and not args.live:
            parser.error("--target-timeout can only be used with --live")

        if args.target_header is not None and not args.live:
            parser.error("--target-header can only be used with --live")

        if args.target_timeout is not None and args.target_timeout <= 0:
            parser.error("--target-timeout must be greater than zero")

        if args.mcp_host_target and not args.mcp_runtime_config:
            parser.error("--mcp-runtime-config is required when using --mcp-host-target")

        if args.mcp_runtime_config and not args.mcp_host_target:
            parser.error("--mcp-runtime-config only applies to --mcp-host-target")

        try:
            target_headers = parse_target_headers(args.target_header)
        except ValueError as exc:
            parser.error(f"--target-header {exc}")

        if args.openai_agent_max_turns is not None and args.openai_agent is None:
            parser.error("--openai-agent-max-turns can only be used with --openai-agent")

        if args.langchain_goal_event is not None and args.langchain_target is None:
            parser.error("--langchain-goal-event can only be used with --langchain-target")

        if (
            args.langchain_goal_event is not None
            and not args.langchain_goal_event.strip()
        ):
            parser.error("--langchain-goal-event must be a non-empty string")

        if (
            args.openai_agent_max_turns is not None
            and args.openai_agent_max_turns <= 0
        ):
            parser.error("--openai-agent-max-turns must be greater than zero")

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
                timeout = (
                    args.target_timeout
                    if args.target_timeout is not None
                    else DEFAULT_HTTP_TIMEOUT_SECONDS
                )
                result = run_scenario_live(
                    scenario,
                    args.target_url,
                    timeout=timeout,
                    headers=target_headers,
                )
            except AdapterError as exc:
                print(f"adapter error: {exc}", file=sys.stderr)
                return 1
        elif args.python_target:
            try:
                result = run_scenario_with_python_target(
                    scenario,
                    args.python_target,
                )
            except AdapterError as exc:
                print(f"adapter error: {exc}", file=sys.stderr)
                return 1
        elif args.openai_agent:
            try:
                result = run_scenario_with_openai_agent(
                    scenario,
                    args.openai_agent,
                    max_turns=args.openai_agent_max_turns,
                )
            except AdapterError as exc:
                print(f"adapter error: {exc}", file=sys.stderr)
                return 1
        elif args.mcp_target:
            try:
                result = run_scenario_with_mcp_target(
                    scenario,
                    args.mcp_target,
                )
            except AdapterError as exc:
                print(f"adapter error: {exc}", file=sys.stderr)
                return 1
        elif args.mcp_host_target:
            try:
                assert args.mcp_runtime_config is not None
                result = run_scenario_with_mcp_host_target(
                    scenario,
                    args.mcp_host_target,
                    args.mcp_runtime_config,
                )
            except AdapterError as exc:
                print(f"adapter error: {exc}", file=sys.stderr)
                return 1
        elif args.langchain_target:
            try:
                result = run_scenario_with_langchain_target(
                    scenario,
                    args.langchain_target,
                    goal_event_id=args.langchain_goal_event,
                )
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

        if args.junit_out:
            Path(args.junit_out).write_text(result_to_junit_xml(result), encoding="utf-8")

        if args.sarif_out:
            Path(args.sarif_out).write_text(result_to_sarif(result), encoding="utf-8")

        if args.exit_on_fail and result.result in {"fail", "error"}:
            return 1

        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
