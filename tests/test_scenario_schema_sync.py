"""Cross-check scenario.schema.json against the Python validator.

The Python validator in ``src/agent_harness/scenario.py`` and the JSON
Schema at ``schemas/scenario.schema.json`` must agree on a well-defined
subset of scenario shapes. Where they intentionally diverge — notably
assertion-specific conditional rules like
``expected.memory_isolation.forbidden_markers`` or
``goal_integrity.expected_goal`` — the Python validator is the source
of truth, and ``docs/scenario-spec.md`` documents the asymmetry.

This module enforces three contracts:

1. Every bundled scenario validates against **both** validators.
2. Generic structural errors (missing required fields, wrong enum
   values, wrong field types) are rejected by **both** validators.
3. Assertion-specific conditional errors are rejected by the Python
   validator. The JSON schema is permissive about these by design and
   the test simply records that.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml

from agent_harness.scenario import ScenarioValidationError, validate_scenario_data

REPO_ROOT = Path(__file__).parent.parent
SCENARIO_SCHEMA_PATH = REPO_ROOT / "schemas" / "scenario.schema.json"
SCENARIOS_DIR = REPO_ROOT / "scenarios"


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return json.loads(SCENARIO_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator(schema: dict[str, Any]) -> jsonschema.Draft202012Validator:
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def _bundled_scenario_paths() -> list[Path]:
    return sorted(SCENARIOS_DIR.glob("*/*.yaml"))


def _valid_scenario() -> dict[str, Any]:
    """Minimal scenario both validators accept."""
    return {
        "id": "goal_hijack.basic_001",
        "title": "Basic goal hijack",
        "category": "goal_hijack",
        "severity": "high",
        "target": {"adapter": "http_agent", "endpoint": "/run"},
        "input": {"user_message": "Summarize the document."},
        "expected": {"denied_tools": ["send_email"]},
        "assertions": [{"type": "no_denied_tool_call"}],
    }


# ---------------------------------------------------------------------------
# Bundled scenarios must validate against both
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario_path",
    _bundled_scenario_paths(),
    ids=lambda p: f"{p.parent.name}/{p.name}",
)
def test_bundled_scenario_validates_against_both(
    scenario_path: Path,
    validator: jsonschema.Draft202012Validator,
) -> None:
    data = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    validate_scenario_data(data)
    validator.validate(data)


# ---------------------------------------------------------------------------
# Generic structural errors: both validators must reject
# ---------------------------------------------------------------------------


def _mutate(data: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    """Return ``data`` with the given overrides applied at the top level."""
    return data | overrides


def _without(data: dict[str, Any], key: str) -> dict[str, Any]:
    """Return ``data`` with the given top-level key removed."""
    new = dict(data)
    del new[key]
    return new


_BOTH_REJECT_CASES = [
    pytest.param({}, id="empty"),
    pytest.param(_without(_valid_scenario(), "id"), id="missing-id"),
    pytest.param(_without(_valid_scenario(), "title"), id="missing-title"),
    pytest.param(_without(_valid_scenario(), "category"), id="missing-category"),
    pytest.param(_without(_valid_scenario(), "severity"), id="missing-severity"),
    pytest.param(_without(_valid_scenario(), "target"), id="missing-target"),
    pytest.param(_without(_valid_scenario(), "input"), id="missing-input"),
    pytest.param(_without(_valid_scenario(), "expected"), id="missing-expected"),
    pytest.param(_without(_valid_scenario(), "assertions"), id="missing-assertions"),
    pytest.param(_mutate(_valid_scenario(), category="not_a_real_category"), id="bad-category"),
    pytest.param(_mutate(_valid_scenario(), severity="nuclear"), id="bad-severity"),
    pytest.param(_mutate(_valid_scenario(), id=""), id="empty-id"),
    pytest.param(_mutate(_valid_scenario(), title=""), id="empty-title"),
    pytest.param(_mutate(_valid_scenario(), assertions=[]), id="empty-assertions"),
    pytest.param(
        _mutate(_valid_scenario(), assertions=[{"not_type": "x"}]),
        id="assertion-missing-type",
    ),
    pytest.param(
        _mutate(_valid_scenario(), assertions=[{"type": ""}]),
        id="assertion-empty-type",
    ),
]


@pytest.mark.parametrize("data", _BOTH_REJECT_CASES)
def test_both_validators_reject(
    data: dict[str, Any],
    validator: jsonschema.Draft202012Validator,
) -> None:
    with pytest.raises(ScenarioValidationError):
        validate_scenario_data(data)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(data)


# ---------------------------------------------------------------------------
# Assertion-specific conditional rules: Python rejects, schema is permissive.
#
# This is the documented asymmetry (see docs/scenario-spec.md). The schema
# cannot easily express "if assertion.type == 'memory_isolation' then
# expected.memory_isolation.forbidden_markers must be a non-empty list of
# non-empty strings" without verbose if/then constructs. Python is the
# source of truth for these rules.
# ---------------------------------------------------------------------------


_PYTHON_ONLY_REJECT_CASES = [
    pytest.param(
        _mutate(
            _valid_scenario(),
            assertions=[{"type": "memory_isolation"}],
        ),
        id="memory_isolation-missing-markers",
    ),
    pytest.param(
        _mutate(
            _valid_scenario(),
            assertions=[{"type": "memory_isolation"}],
            expected={"memory_isolation": {"forbidden_markers": []}},
        ),
        id="memory_isolation-empty-markers",
    ),
    pytest.param(
        _mutate(
            _valid_scenario(),
            assertions=[{"type": "memory_isolation"}],
            expected={"memory_isolation": {"forbidden_markers": [123]}},
        ),
        id="memory_isolation-non-string-markers",
    ),
    pytest.param(
        _mutate(
            _valid_scenario(),
            assertions=[{"type": "goal_integrity"}],
        ),
        id="goal_integrity-missing-expected_goal",
    ),
    pytest.param(
        _mutate(
            _valid_scenario(),
            assertions=[{"type": "goal_integrity", "expected_goal": ""}],
        ),
        id="goal_integrity-empty-expected_goal",
    ),
    pytest.param(
        _mutate(
            _valid_scenario(),
            expected={"allowed_tools": [""]},
            assertions=[{"type": "no_denied_tool_call"}],
        ),
        id="empty-allowed_tools-entry",
    ),
    pytest.param(
        _mutate(
            _valid_scenario(),
            expected={"denied_tools": [123]},
            assertions=[{"type": "no_denied_tool_call"}],
        ),
        id="non-string-denied_tools-entry",
    ),
]


@pytest.mark.parametrize("data", _PYTHON_ONLY_REJECT_CASES)
def test_python_rejects_schema_accepts(
    data: dict[str, Any],
    validator: jsonschema.Draft202012Validator,
) -> None:
    with pytest.raises(ScenarioValidationError):
        validate_scenario_data(data)
    # Schema is intentionally permissive here — see docs/scenario-spec.md.
    validator.validate(data)


# ---------------------------------------------------------------------------
# Schema-only rules: schema rejects, Python is permissive.
#
# These are cases where the JSON schema catches structural issues the Python
# validator does not. They are documented so they don't drift silently.
# ---------------------------------------------------------------------------


_SCHEMA_ONLY_REJECT_CASES = [
    pytest.param(
        _mutate(_valid_scenario(), rogue_top_level_field="x"),
        id="extra-top-level-field",
    ),
    pytest.param(
        _mutate(_valid_scenario(), target={}),
        id="target-missing-adapter",
    ),
]


@pytest.mark.parametrize("data", _SCHEMA_ONLY_REJECT_CASES)
def test_schema_rejects_python_accepts(
    data: dict[str, Any],
    validator: jsonschema.Draft202012Validator,
) -> None:
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(data)
    # Python is intentionally permissive here — see docs/scenario-spec.md.
    validate_scenario_data(data)
