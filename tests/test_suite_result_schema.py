"""Validate that emitted suite result JSON matches suite_result.schema.json.

This is the contract enforcement between ``SuiteResult.to_dict()`` and
``schemas/suite_result.schema.json``, mirroring ``test_result_schema.py`` for
single-scenario results. It catches drift in either direction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from agent_harness.result import (
    AssertionResult,
    HarnessResult,
    SuiteEntry,
    SuiteResult,
)
from agent_harness.trace import Trace

SUITE_SCHEMA_PATH = (
    Path(__file__).parent.parent / "schemas" / "suite_result.schema.json"
)


@pytest.fixture(scope="module")
def suite_schema() -> dict[str, Any]:
    return json.loads(SUITE_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator(suite_schema: dict[str, Any]) -> jsonschema.Draft202012Validator:
    jsonschema.Draft202012Validator.check_schema(suite_schema)
    return jsonschema.Draft202012Validator(suite_schema)


def _passing_entry() -> SuiteEntry:
    detail = HarnessResult(
        scenario_id="goal_hijack.basic_001",
        mode="trace",
        result="pass",
        assertions=[
            AssertionResult(
                id="no_denied_tool_call",
                result="pass",
                evidence="no denied tool calls observed",
            )
        ],
        trace=Trace(),
    )
    return SuiteEntry(
        scenario_path="scenarios/goal_hijack/basic.yaml",
        scenario_id="goal_hijack.basic_001",
        category="goal_hijack",
        severity="high",
        trace_path="traces/goal_hijack.basic_001.json",
        result="pass",
        detail=detail,
    )


def test_empty_suite_matches_schema(validator):
    validator.validate(SuiteResult().to_dict())


def test_passing_suite_matches_schema(validator):
    result = SuiteResult(entries=[_passing_entry()])
    payload = result.to_dict()

    assert payload["result"] == "pass"
    assert payload["counts"] == {
        "total": 1,
        "pass": 1,
        "fail": 0,
        "error": 0,
        "not_run": 0,
    }
    validator.validate(payload)


@pytest.mark.parametrize(
    "error_reason",
    ["missing_trace", "invalid_scenario", "invalid_trace", "duplicate_scenario_id"],
)
def test_error_entries_match_schema(validator, error_reason):
    entry = SuiteEntry(
        scenario_path="scenarios/goal_hijack/basic.yaml",
        scenario_id="goal_hijack.basic_001",
        category="goal_hijack",
        severity="high",
        result="error",
        error_reason=error_reason,
        evidence="something went wrong",
    )
    result = SuiteResult(entries=[entry])

    assert result.result == "error"
    validator.validate(result.to_dict())


def test_invalid_scenario_entry_without_id_matches_schema(validator):
    """An unparseable scenario has no id but must still validate."""
    entry = SuiteEntry(
        scenario_path="scenarios/broken.yaml",
        result="error",
        error_reason="invalid_scenario",
        evidence="missing required fields: title",
    )
    validator.validate(SuiteResult(entries=[entry]).to_dict())


def test_mixed_suite_aggregates_to_fail(validator):
    entries = [
        _passing_entry(),
        SuiteEntry(
            scenario_path="scenarios/goal_hijack/other.yaml",
            scenario_id="goal_hijack.other_001",
            category="goal_hijack",
            severity="high",
            result="error",
            error_reason="missing_trace",
            evidence="no trace file found",
        ),
        SuiteEntry(
            scenario_path="scenarios/goal_hijack/third.yaml",
            scenario_id="goal_hijack.third_001",
            category="goal_hijack",
            severity="high",
            trace_path="traces/goal_hijack.third_001.json",
            result="fail",
        ),
    ]
    result = SuiteResult(entries=entries)

    assert result.result == "fail"
    assert result.counts == {
        "total": 3,
        "pass": 1,
        "fail": 1,
        "error": 1,
        "not_run": 0,
    }
    validator.validate(result.to_dict())
