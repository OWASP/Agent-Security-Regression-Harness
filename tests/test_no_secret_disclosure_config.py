"""Validation of no_secret_disclosure scenario configuration."""

from __future__ import annotations

from typing import Any

import pytest

from agent_harness.scenario import (
    ScenarioValidationError,
    parse_no_secret_disclosure_config,
    validate_scenario_data,
)


def _scenario(expected: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "sensitive_data_disclosure.config_001",
        "title": "Config test",
        "category": "sensitive_data_disclosure",
        "severity": "high",
        "target": {"adapter": "http_agent"},
        "input": {},
        "expected": expected,
        "assertions": [{"type": "no_secret_disclosure"}],
    }


def test_scenario_without_secret_configuration_stays_valid():
    scenario = validate_scenario_data(_scenario({"denied_tools": ["shell"]}))

    assert scenario.id == "sensitive_data_disclosure.config_001"


def test_all_configuration_sources_are_merged():
    config = parse_no_secret_disclosure_config(
        {
            "secrets": ["plain-secret", {"name": "api_key", "value": "sk-1"}],
            "forbidden_outputs": ["forbidden-1"],
            "no_secret_disclosure": {
                "secrets": [{"name": "extra", "value": "sk-2"}],
                "patterns": [{"name": "sk_style", "pattern": "sk-[0-9]+"}, "AKIA[A-Z]+"],
                "check_events": False,
            },
        }
    )

    assert [rule.label for rule in config.secrets] == [
        "expected.secrets[0]",
        "api_key",
        "expected.forbidden_outputs[0]",
        "extra",
    ]
    assert [rule.label for rule in config.patterns] == [
        "sk_style",
        "expected.no_secret_disclosure.patterns[1]",
    ]
    assert config.check_messages and config.check_tool_calls
    assert config.check_events is False


@pytest.mark.parametrize(
    ("expected", "message"),
    [
        ({"secrets": "sk-1"}, "expected.secrets must be a list"),
        ({"secrets": [""]}, r"expected.secrets\[0\] must be a non-empty string"),
        ({"secrets": [123]}, r"expected.secrets\[0\] must be a non-empty string"),
        ({"secrets": [None]}, r"expected.secrets\[0\] must be a non-empty string"),
        (
            {"secrets": [{"name": "a"}]},
            r"expected.secrets\[0\].value must be a non-empty string",
        ),
        (
            {"secrets": [{"name": "a", "value": ""}]},
            r"expected.secrets\[0\].value must be a non-empty string",
        ),
        (
            {"secrets": [{"name": "a", "value": 5}]},
            r"expected.secrets\[0\].value must be a non-empty string",
        ),
        (
            {"secrets": [{"name": "", "value": "x"}]},
            r"expected.secrets\[0\].name must be",
        ),
        (
            {"secrets": [{"name": "bad name\n", "value": "x"}]},
            r"expected.secrets\[0\].name must be",
        ),
        (
            {"secrets": [{"name": "a", "value": "x", "extra": 1}]},
            "unsupported keys: extra",
        ),
        (
            {"secrets": [{"name": "a", "value": "x"}, {"name": "a", "value": "y"}]},
            "duplicate secret name",
        ),
        (
            {"secrets": [{"name": "sk-123", "value": "sk-123"}]},
            "must not contain a configured secret value",
        ),
        ({"forbidden_outputs": "x"}, "expected.forbidden_outputs must be a list"),
        (
            {"forbidden_outputs": [{"name": "a", "value": "x"}]},
            r"expected.forbidden_outputs\[0\] must be a non-empty string",
        ),
        ({"no_secret_disclosure": []}, "must be an object"),
        (
            {"no_secret_disclosure": {"secret": ["typo"]}},
            "unsupported keys: secret",
        ),
        (
            {"no_secret_disclosure": {"check_tool_calls": "yes"}},
            "check_tool_calls must be a boolean",
        ),
        (
            {
                "no_secret_disclosure": {
                    "check_messages": False,
                    "check_tool_calls": False,
                    "check_events": False,
                }
            },
            "must enable at least one",
        ),
        (
            {"no_secret_disclosure": {"patterns": "sk-.*"}},
            "patterns must be a list",
        ),
        (
            {"no_secret_disclosure": {"patterns": ["("]}},
            "not a valid regular expression",
        ),
        (
            {"no_secret_disclosure": {"patterns": [".*"]}},
            "must not match the empty string",
        ),
        (
            {"no_secret_disclosure": {"patterns": ["x?"]}},
            "must not match the empty string",
        ),
        (
            {"no_secret_disclosure": {"patterns": [{"name": "p"}]}},
            r"patterns\[0\].pattern must be a non-empty string",
        ),
    ],
)
def test_invalid_configuration_is_rejected_by_scenario_validation(
    expected: dict[str, Any], message: str
):
    with pytest.raises(ScenarioValidationError, match=message):
        validate_scenario_data(_scenario(expected))


def test_configuration_is_only_validated_when_assertion_is_used():
    data = _scenario({"secrets": "not-a-list"})
    data["assertions"] = [{"type": "no_denied_tool_call"}]

    validate_scenario_data(data)


def test_validation_errors_never_echo_secret_values():
    with pytest.raises(ScenarioValidationError) as excinfo:
        validate_scenario_data(
            _scenario({"secrets": [{"name": "a", "value": "sk-live-SECRET", "x": 1}]})
        )

    assert "sk-live-SECRET" not in str(excinfo.value)


def test_bundled_credential_leak_scenario_passes_and_fails_as_designed():
    from pathlib import Path

    from agent_harness.runner import run_scenario_with_trace
    from agent_harness.scenario import load_scenario
    from agent_harness.trace import load_trace

    root = Path(__file__).parent.parent
    scenario = load_scenario(
        root / "scenarios/sensitive_data_disclosure/credential_leak_in_reply_001.yaml"
    )

    clean = run_scenario_with_trace(
        scenario,
        load_trace(
            root
            / "examples/traces/sensitive_data_disclosure"
            / "credential_leak_in_reply_001_pass.json"
        ),
    )
    leaked = run_scenario_with_trace(
        scenario, load_trace(root / "examples/traces/secret_disclosure_leak.json")
    )

    assert clean.result == "pass"
    assert leaked.result == "fail"
    leak_evidence = next(a.evidence for a in leaked.assertions if a.result == "fail")
    assert "internal_service_key" in (leak_evidence or "")
    assert "sk-test-NOT-A-REAL-KEY-0001" not in (leak_evidence or "")