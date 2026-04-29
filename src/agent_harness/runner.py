"""Scenario runner."""

from __future__ import annotations

from agent_harness.result import AssertionResult, HarnessResult
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