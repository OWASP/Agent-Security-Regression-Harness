"""Scenario runner."""

from __future__ import annotations

from agent_harness.result import AssertionResult, HarnessResult, aggregate_assertion_results
from agent_harness.scenario import Scenario
from agent_harness.trace import Trace
from agent_harness.assertions import evaluate_assertions


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
