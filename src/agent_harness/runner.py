"""Scenario runner."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, cast

from agent_harness.adapters import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    load_python_callable,
    load_python_object,
    run_http_target,
    run_python_callable_target,
)
from agent_harness.assertions import evaluate_assertions
from agent_harness.langchain_adapter import (
    load_langchain_target,
    run_langchain_target,
)
from agent_harness.mcp_adapter import run_mcp_target
from agent_harness.openai_agents_adapter import run_openai_agents_target
from agent_harness.result import (
    AssertionResult,
    HarnessResult,
    SuiteEntry,
    SuiteResult,
    aggregate_assertion_results,
)
from agent_harness.scenario import Scenario, ScenarioValidationError, load_scenario
from agent_harness.trace import Trace, TraceValidationError, load_trace

if TYPE_CHECKING:
    from agent_harness.mcp_host import MCPHostTarget


def dry_run_scenario(scenario: Scenario) -> HarnessResult:
    """Create a dry-run result for a validated scenario.

    Dry-run mode validates the scenario and emits the result shape without
    executing a target agent. Assertions are marked as not_run because no
    system behavior has been observed.
    """
    assertion_results = [
        AssertionResult(
            id=assertion["type"],
            result="not_run",
            evidence="dry-run mode does not execute assertions",
        )
        for assertion in scenario.raw["assertions"]
    ]

    return HarnessResult(
        scenario_id=scenario.id,
        mode="dry_run",
        result="not_run",
        assertions=assertion_results,
        trace=Trace(),
    )


def run_scenario_with_trace(scenario: Scenario, trace: Trace) -> HarnessResult:
    """Evaluate a scenario against an existing execution trace."""
    assertion_results = evaluate_assertions(scenario, trace)
    top_level_result = aggregate_assertion_results(assertion_results)

    return HarnessResult(
        scenario_id=scenario.id,
        mode="trace",
        result=top_level_result,
        assertions=assertion_results,
        trace=trace,
    )


def run_scenario_live(
    scenario: Scenario,
    target_url: str,
    *,
    timeout: int = DEFAULT_HTTP_TIMEOUT_SECONDS,
    headers: dict[str, str] | None = None,
) -> HarnessResult:
    """Run a scenario against a live HTTP target."""
    trace = run_http_target(scenario, target_url, timeout=timeout, headers=headers)
    assertion_results = evaluate_assertions(scenario, trace)
    top_level_result = aggregate_assertion_results(assertion_results)

    return HarnessResult(
        scenario_id=scenario.id,
        mode="live",
        result=top_level_result,
        assertions=assertion_results,
        trace=trace,
    )


def run_scenario_with_python_target(
    scenario: Scenario,
    python_target: str,
) -> HarnessResult:
    """Run a scenario against a local Python callable target."""
    target_callable = load_python_callable(python_target)
    trace = run_python_callable_target(scenario, target_callable)
    assertion_results = evaluate_assertions(scenario, trace)
    top_level_result = aggregate_assertion_results(assertion_results)

    return HarnessResult(
        scenario_id=scenario.id,
        mode="live",
        result=top_level_result,
        assertions=assertion_results,
        trace=trace,
    )


def run_scenario_with_openai_agent(
    scenario: Scenario,
    openai_agent: str,
    *,
    max_turns: int | None = None,
) -> HarnessResult:
    """Run a scenario against an OpenAI Agents SDK Agent target."""
    agent = load_python_object(openai_agent, "OpenAI Agents SDK target")
    trace = run_openai_agents_target(
        scenario,
        agent,
        max_turns=max_turns,
    )
    assertion_results = evaluate_assertions(scenario, trace)
    top_level_result = aggregate_assertion_results(assertion_results)

    return HarnessResult(
        scenario_id=scenario.id,
        mode="live",
        result=top_level_result,
        assertions=assertion_results,
        trace=trace,
    )


def run_scenario_with_mcp_target(
    scenario: Scenario,
    mcp_target: str,
) -> HarnessResult:
    """Run a scenario against a local MCP-integrated workflow target."""
    target_callable = load_python_callable(mcp_target)
    trace = run_mcp_target(scenario, target_callable)
    assertion_results = evaluate_assertions(scenario, trace)
    top_level_result = aggregate_assertion_results(assertion_results)

    return HarnessResult(
        scenario_id=scenario.id,
        mode="live",
        result=top_level_result,
        assertions=assertion_results,
        trace=trace,
    )


def run_scenario_with_mcp_host_target(
    scenario: Scenario,
    mcp_host_target: str,
    runtime_config_path: str,
) -> HarnessResult:
    """Run a scenario against a local target through the MCP stdio host."""
    from agent_harness import mcp_host, mcp_runtime

    target_callable = cast("MCPHostTarget", load_python_callable(mcp_host_target))
    runtime_config = mcp_runtime.load_mcp_runtime_config(runtime_config_path)
    execution = mcp_host.run_mcp_host_target(
        scenario,
        target_callable,
        runtime_config,
    )
    assertion_results = evaluate_assertions(scenario, execution.trace)
    top_level_result = aggregate_assertion_results(assertion_results)

    return HarnessResult(
        scenario_id=scenario.id,
        mode="live",
        result=top_level_result,
        assertions=assertion_results,
        trace=execution.trace,
    )


def run_scenario_with_langchain_target(
    scenario: Scenario,
    langchain_target: str,
    *,
    goal_event_id: str | None = None,
) -> HarnessResult:
    """Run a scenario against a LangChain/LangGraph target."""
    target = load_langchain_target(langchain_target)
    trace = run_langchain_target(
        scenario,
        target,
        goal_event_id=goal_event_id,
    )
    assertion_results = evaluate_assertions(scenario, trace)
    top_level_result = aggregate_assertion_results(assertion_results)

    return HarnessResult(
        scenario_id=scenario.id,
        mode="live",
        result=top_level_result,
        assertions=assertion_results,
        trace=trace,
    )


def _suite_error_result(scenario: Scenario, evidence: str) -> HarnessResult:
    """Build an ``error`` HarnessResult for a scenario that could not run."""
    return HarnessResult(
        scenario_id=scenario.id,
        mode="trace",
        result="error",
        assertions=[AssertionResult(id="suite", result="error", evidence=evidence)],
        trace=Trace(),
    )


def _resolve_within(base: Path, name: str) -> Path:
    """Join ``name`` onto ``base`` and confirm it stays inside ``base``.

    Defense in depth on top of scenario-id charset validation: even if an id
    somehow contained path separators, the suite must never read or write
    outside the configured directory.
    """
    candidate = (base / name).resolve()
    if not candidate.is_relative_to(base.resolve()):
        raise ValueError(f"resolved path escapes directory: {name!r}")
    return candidate


def run_suite(
    scenario_paths: Iterable[str | Path],
    trace_dir: str | Path,
) -> SuiteResult:
    """Run a directory of scenarios against trace files in ``trace_dir``.

    Each scenario is mapped to ``<trace_dir>/<scenario_id>.json``. A scenario
    that cannot run (invalid YAML, duplicate id, missing trace, or malformed
    trace) is recorded as a per-scenario ``error`` and the suite continues, so
    one broken input never hides the results of the others.
    """
    trace_dir_path = Path(trace_dir)
    entries: list[SuiteEntry] = []
    seen_ids: dict[str, str] = {}

    for scenario_path in scenario_paths:
        path_str = str(scenario_path)

        try:
            scenario = load_scenario(scenario_path)
        except ScenarioValidationError as exc:
            entries.append(
                SuiteEntry(
                    scenario_path=path_str,
                    result="error",
                    error_reason="invalid_scenario",
                    evidence=str(exc),
                )
            )
            continue

        if scenario.id in seen_ids:
            entries.append(
                SuiteEntry(
                    scenario_path=path_str,
                    scenario_id=scenario.id,
                    category=scenario.category,
                    severity=scenario.severity,
                    result="error",
                    error_reason="duplicate_scenario_id",
                    evidence=f"scenario id already used by {seen_ids[scenario.id]}",
                )
            )
            continue
        seen_ids[scenario.id] = path_str

        try:
            trace_path = _resolve_within(trace_dir_path, f"{scenario.id}.json")
        except ValueError as exc:
            entries.append(
                SuiteEntry(
                    scenario_path=path_str,
                    scenario_id=scenario.id,
                    category=scenario.category,
                    severity=scenario.severity,
                    result="error",
                    error_reason="invalid_scenario",
                    evidence=str(exc),
                    detail=_suite_error_result(scenario, str(exc)),
                )
            )
            continue

        if not trace_path.is_file():
            evidence = f"no trace file found at {trace_path}"
            entries.append(
                SuiteEntry(
                    scenario_path=path_str,
                    scenario_id=scenario.id,
                    category=scenario.category,
                    severity=scenario.severity,
                    trace_path=str(trace_path),
                    result="error",
                    error_reason="missing_trace",
                    evidence=evidence,
                    detail=_suite_error_result(scenario, evidence),
                )
            )
            continue

        try:
            trace = load_trace(trace_path)
        except TraceValidationError as exc:
            evidence = f"invalid trace: {exc}"
            entries.append(
                SuiteEntry(
                    scenario_path=path_str,
                    scenario_id=scenario.id,
                    category=scenario.category,
                    severity=scenario.severity,
                    trace_path=str(trace_path),
                    result="error",
                    error_reason="invalid_trace",
                    evidence=evidence,
                    detail=_suite_error_result(scenario, evidence),
                )
            )
            continue

        harness_result = run_scenario_with_trace(scenario, trace)
        entries.append(
            SuiteEntry(
                scenario_path=path_str,
                scenario_id=scenario.id,
                category=scenario.category,
                severity=scenario.severity,
                trace_path=str(trace_path),
                result=harness_result.result,
                detail=harness_result,
            )
        )

    return SuiteResult(entries=entries)
