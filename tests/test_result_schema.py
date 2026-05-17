"""Validate that emitted harness result JSON matches result.schema.json.

These tests are the contract enforcement between ``HarnessResult.to_dict()``
and ``schemas/result.schema.json``. They catch schema drift in either
direction: if the dataclass changes shape, or if someone edits the schema
to be more permissive than the dataclass actually is.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from agent_harness.result import AssertionResult, HarnessResult
from agent_harness.trace import Trace

RESULT_SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "result.schema.json"


@pytest.fixture(scope="module")
def result_schema() -> dict[str, Any]:
    return json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator(result_schema: dict[str, Any]) -> jsonschema.Draft202012Validator:
    jsonschema.Draft202012Validator.check_schema(result_schema)
    return jsonschema.Draft202012Validator(result_schema)


# ---------------------------------------------------------------------------
# Positive cases: every (mode, result) combination produced by the harness
# should validate.
# ---------------------------------------------------------------------------


def test_dry_run_not_run_matches_schema(validator):
    result = HarnessResult(
        scenario_id="goal_hijack.basic_001",
        mode="dry_run",
        result="not_run",
        assertions=[AssertionResult(id="no_denied_tool_call", result="not_run")],
        trace=Trace(),
    )
    validator.validate(result.to_dict())


def test_trace_pass_matches_schema(validator):
    result = HarnessResult(
        scenario_id="goal_hijack.basic_001",
        mode="trace",
        result="pass",
        assertions=[
            AssertionResult(
                id="no_denied_tool_call",
                result="pass",
                evidence="no denied tool calls observed",
            ),
        ],
        trace=Trace(messages=[{"role": "assistant", "content": "ok"}]),
    )
    validator.validate(result.to_dict())


def test_trace_fail_matches_schema(validator):
    result = HarnessResult(
        scenario_id="goal_hijack.basic_001",
        mode="trace",
        result="fail",
        assertions=[
            AssertionResult(
                id="no_denied_tool_call",
                result="fail",
                evidence="denied tool call observed: send_email",
            ),
        ],
        trace=Trace(tool_calls=[{"name": "send_email"}]),
    )
    validator.validate(result.to_dict())


def test_live_pass_matches_schema(validator):
    result = HarnessResult(
        scenario_id="goal_hijack.basic_001",
        mode="live",
        result="pass",
        assertions=[
            AssertionResult(id="goal_integrity", result="pass", evidence="ok"),
        ],
        trace=Trace(
            messages=[{"role": "user", "content": "hi"}],
            tool_calls=[],
            events=[{"type": "goal", "id": "summarize_document"}],
        ),
    )
    validator.validate(result.to_dict())


def test_error_result_matches_schema(validator):
    result = HarnessResult(
        scenario_id="some.scenario",
        mode="trace",
        result="error",
        assertions=[
            AssertionResult(
                id="unknown_type",
                result="error",
                evidence="unsupported assertion type: unknown_type",
            ),
        ],
        trace=Trace(),
    )
    validator.validate(result.to_dict())


def test_assertion_without_evidence_matches_schema(validator):
    result = HarnessResult(
        scenario_id="some.scenario",
        mode="dry_run",
        result="not_run",
        assertions=[AssertionResult(id="no_denied_tool_call", result="not_run")],
        trace=Trace(),
    )
    data = result.to_dict()
    assert "evidence" not in data["assertions"][0]
    validator.validate(data)


def test_empty_assertions_list_matches_schema(validator):
    result = HarnessResult(
        scenario_id="some.scenario",
        mode="dry_run",
        result="not_run",
        assertions=[],
        trace=Trace(),
    )
    validator.validate(result.to_dict())


# ---------------------------------------------------------------------------
# Negative cases: the schema should actually reject malformed shapes.
# Without these the positive tests would still pass if someone accidentally
# loosened additionalProperties or dropped an enum.
# ---------------------------------------------------------------------------


def _base_valid_result() -> dict[str, Any]:
    return {
        "scenario_id": "x.y",
        "mode": "trace",
        "result": "pass",
        "assertions": [],
        "trace": {"messages": [], "tool_calls": [], "events": []},
    }


def test_schema_rejects_invalid_mode(validator):
    invalid = _base_valid_result() | {"mode": "totally_invalid"}
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid)


def test_schema_rejects_invalid_top_level_result(validator):
    invalid = _base_valid_result() | {"result": "maybe"}
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid)


def test_schema_rejects_invalid_assertion_result(validator):
    invalid = _base_valid_result() | {
        "assertions": [{"id": "x", "result": "maybe"}],
    }
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid)


def test_schema_rejects_extra_top_level_field(validator):
    invalid = _base_valid_result() | {"rogue_field": True}
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid)


def test_schema_rejects_extra_assertion_field(validator):
    invalid = _base_valid_result() | {
        "assertions": [{"id": "x", "result": "pass", "rogue": True}],
    }
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid)


def test_schema_rejects_extra_trace_field(validator):
    invalid = _base_valid_result() | {
        "trace": {
            "messages": [],
            "tool_calls": [],
            "events": [],
            "rogue": True,
        },
    }
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid)


def test_schema_rejects_missing_top_level_field(validator):
    invalid = _base_valid_result()
    del invalid["scenario_id"]
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid)


def test_schema_rejects_missing_trace_field(validator):
    invalid = _base_valid_result() | {
        "trace": {"messages": [], "tool_calls": []},  # events missing
    }
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid)
