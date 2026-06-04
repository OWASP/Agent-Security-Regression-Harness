"""Scenario runner."""

from __future__ import annotations

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
from agent_harness.result import AssertionResult, HarnessResult, aggregate_assertion_results
from agent_harness.scenario import Scenario
from agent_harness.trace import Trace


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
) -> HarnessResult:
    """Run a scenario against a live HTTP target."""
    trace = run_http_target(scenario, target_url, timeout=timeout)
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

    target_callable = load_python_callable(mcp_host_target)
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
