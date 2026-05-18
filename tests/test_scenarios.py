"""Tests for bundled scenario files"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_harness.scenario import (
    ScenarioValidationError,
    load_scenario,
    validate_scenario_data,
)


def _minimal_scenario(assertions):
    return {
        "id": "goal-hijack-basic",
        "title": "Goal hijack basic",
        "category": "goal_hijack",
        "severity": "medium",
        "target": {},
        "input": {},
        "expected": {},
        "assertions": assertions,
    }


def test_all_bundled_scenarios_validate():
    scenario_paths = sorted(Path("scenarios").rglob("*.yaml"))

    assert scenario_paths, "expected at least one bundled scenario"

    for scenario_path in scenario_paths:
        load_scenario(scenario_path)


def test_goal_integrity_assertion_validates_with_expected_goal():
    scenario = validate_scenario_data(
        _minimal_scenario(
            [{"type": "goal_integrity", "expected_goal": "summarize_document"}]
        )
    )

    assert scenario.id == "goal-hijack-basic"


def test_goal_integrity_assertion_requires_expected_goal():
    with pytest.raises(
        ScenarioValidationError,
        match="expected_goal must be a non-empty string",
    ):
        validate_scenario_data(_minimal_scenario([{"type": "goal_integrity"}]))


def test_goal_integrity_assertion_rejects_blank_expected_goal():
    with pytest.raises(
        ScenarioValidationError,
        match="expected_goal must be a non-empty string",
    ):
        validate_scenario_data(
            _minimal_scenario([{"type": "goal_integrity", "expected_goal": "   "}])
        )


def test_goal_integrity_assertion_rejects_non_string_expected_goal():
    with pytest.raises(
        ScenarioValidationError,
        match="expected_goal must be a non-empty string",
    ):
        validate_scenario_data(
            _minimal_scenario([{"type": "goal_integrity", "expected_goal": 123}])
        )


def test_other_assertion_types_do_not_require_expected_goal():
    scenario = validate_scenario_data(
        _minimal_scenario([{"type": "no_denied_tool_call"}])
    )

    assert scenario.id == "goal-hijack-basic"


def test_expected_allowed_tools_must_be_a_list():
    data = _minimal_scenario([{"type": "no_denied_tool_call"}])
    data["expected"] = {"allowed_tools": "read_file"}

    with pytest.raises(
        ScenarioValidationError,
        match="expected.allowed_tools must be a list",
    ):
        validate_scenario_data(data)


def test_expected_allowed_tools_items_must_be_non_empty_strings():
    data = _minimal_scenario([{"type": "no_denied_tool_call"}])
    data["expected"] = {"allowed_tools": ["read_file", ""]}

    with pytest.raises(
        ScenarioValidationError,
        match="expected.allowed_tools",
    ):
        validate_scenario_data(data)
