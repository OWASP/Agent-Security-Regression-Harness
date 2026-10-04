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


def _valid_state_model():
    return {
        "initial": {"confidential_loaded": False, "confidential_external_uploads": 0},
        "transitions": [
            {
                "when": {"effect": "read", "resource": "records/confidential/*"},
                "set": {"confidential_loaded": True},
            },
            {
                "when": {"effect": "upload", "destination": "external:*"},
                "requires": [{"field": "confidential_loaded", "equals": True}],
                "add": {"confidential_external_uploads": 1},
            },
        ],
        "forbidden": [
            {
                "id": "confidential_exfiltrated",
                "all": [{"field": "confidential_external_uploads", "greater_than": 0}],
            }
        ],
    }


def test_forbidden_state_assertion_validates_with_state_model():
    data = _minimal_scenario([{"type": "forbidden_state_not_reached"}])
    data["expected"] = {"state_model": _valid_state_model()}

    scenario = validate_scenario_data(data)

    assert scenario.id == "goal-hijack-basic"


def test_forbidden_state_assertion_requires_state_model():
    data = _minimal_scenario([{"type": "forbidden_state_not_reached"}])

    with pytest.raises(
        ScenarioValidationError,
        match="invalid expected.state_model for forbidden_state_not_reached",
    ):
        validate_scenario_data(data)


def test_forbidden_state_assertion_rejects_explicit_null_requires_guard():
    data = _minimal_scenario([{"type": "forbidden_state_not_reached"}])
    state_model = _valid_state_model()
    state_model["transitions"][1]["requires"] = None
    data["expected"] = {"state_model": state_model}

    with pytest.raises(
        ScenarioValidationError,
        match="requires must be a non-empty list",
    ):
        validate_scenario_data(data)


def test_forbidden_state_assertion_allows_omitted_requires_guard():
    data = _minimal_scenario([{"type": "forbidden_state_not_reached"}])
    state_model = _valid_state_model()
    del state_model["transitions"][1]["requires"]
    data["expected"] = {"state_model": state_model}

    assert validate_scenario_data(data).id == "goal-hijack-basic"


def test_forbidden_state_assertion_rejects_undeclared_predicate_field():
    data = _minimal_scenario([{"type": "forbidden_state_not_reached"}])
    state_model = _valid_state_model()
    state_model["forbidden"][0]["all"][0]["field"] = "typo_field"
    data["expected"] = {"state_model": state_model}

    with pytest.raises(
        ScenarioValidationError,
        match="field 'typo_field' is not declared",
    ):
        validate_scenario_data(data)


def test_forbidden_state_assertion_rejects_unknown_state_model_keys():
    data = _minimal_scenario([{"type": "forbidden_state_not_reached"}])
    state_model = _valid_state_model()
    state_model["predicates"] = state_model.pop("forbidden")
    data["expected"] = {"state_model": state_model}

    with pytest.raises(
        ScenarioValidationError,
        match="unsupported keys: predicates",
    ):
        validate_scenario_data(data)


def test_forbidden_state_assertion_rejects_undeclared_guard_field():
    data = _minimal_scenario([{"type": "forbidden_state_not_reached"}])
    state_model = _valid_state_model()
    state_model["transitions"][1]["requires"] = [
        {"field": "never_declared", "equals": True}
    ]
    data["expected"] = {"state_model": state_model}

    with pytest.raises(
        ScenarioValidationError,
        match="requires field 'never_declared' is not declared",
    ):
        validate_scenario_data(data)


def test_other_assertion_types_do_not_require_state_model():
    data = _minimal_scenario([{"type": "no_denied_tool_call"}])
    data["expected"] = {}

    scenario = validate_scenario_data(data)

    assert scenario.id == "goal-hijack-basic"
