"""Scenario loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


VALID_CATEGORIES = {
    "goal_hijack",
    "prompt_injection",
    "context_injection",
    "unsafe_tool_execution",
    "unauthorized_outbound_action",
    "sensitive_data_disclosure",
    "privilege_escalation",
    "memory_isolation",
    "approval_bypass",
    "mcp_trust_boundary",
}

VALID_SEVERITIES = {"low", "medium", "high", "critical"}

REQUIRED_TOP_LEVEL_FIELDS = {
    "id",
    "title",
    "category",
    "severity",
    "target",
    "input",
    "expected",
    "assertions",
}


class ScenarioValidationError(ValueError):
    """Raised when a scenario file is invalid."""


@dataclass(frozen=True)
class Scenario:
    """Validated scenario metadata and raw content."""

    id: str
    title: str
    category: str
    severity: str
    raw: dict[str, Any]


def load_scenario(path: str | Path) -> Scenario:
    """Load and validate a scenario YAML file."""
    scenario_path = Path(path)

    if not scenario_path.exists():
        raise ScenarioValidationError(f"scenario file does not exist: {scenario_path}")

    if scenario_path.suffix.lower() not in {".yaml", ".yml"}:
        raise ScenarioValidationError("scenario file must use .yaml or .yml extension")

    try:
        data = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ScenarioValidationError(f"invalid YAML: {exc}") from exc

    return validate_scenario_data(data)


def validate_scenario_data(data: Any) -> Scenario:
    """Validate parsed scenario data."""
    if not isinstance(data, dict):
        raise ScenarioValidationError("scenario must be a YAML mapping/object")

    missing_fields = sorted(REQUIRED_TOP_LEVEL_FIELDS - set(data))
    if missing_fields:
        joined = ", ".join(missing_fields)
        raise ScenarioValidationError(f"missing required fields: {joined}")

    scenario_id = data["id"]
    title = data["title"]
    category = data["category"]
    severity = data["severity"]
    target = data["target"]
    scenario_input = data["input"]
    expected = data["expected"]
    assertions = data["assertions"]

    if not isinstance(scenario_id, str) or not scenario_id.strip():
        raise ScenarioValidationError("id must be a non-empty string")

    if not isinstance(title, str) or not title.strip():
        raise ScenarioValidationError("title must be a non-empty string")

    if category not in VALID_CATEGORIES:
        valid = ", ".join(sorted(VALID_CATEGORIES))
        raise ScenarioValidationError(f"category must be one of: {valid}")

    if severity not in VALID_SEVERITIES:
        valid = ", ".join(sorted(VALID_SEVERITIES))
        raise ScenarioValidationError(f"severity must be one of: {valid}")

    if not isinstance(target, dict):
        raise ScenarioValidationError("target must be an object")

    if not isinstance(scenario_input, dict):
        raise ScenarioValidationError("input must be an object")

    if not isinstance(expected, dict):
        raise ScenarioValidationError("expected must be an object")

    if not isinstance(assertions, list) or not assertions:
        raise ScenarioValidationError("assertions must be a non-empty list")

    for index, assertion in enumerate(assertions):
        if not isinstance(assertion, dict):
            raise ScenarioValidationError(f"assertions[{index}] must be an object")

        assertion_type = assertion.get("type")
        if not isinstance(assertion_type, str) or not assertion_type.strip():
            raise ScenarioValidationError(
                f"assertions[{index}].type must be a non-empty string"
            )

    return Scenario(
        id=scenario_id,
        title=title,
        category=category,
        severity=severity,
        raw=data,
    )