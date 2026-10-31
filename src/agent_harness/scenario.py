"""Scenario loading and validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Scenario IDs are used as filesystem path components (e.g. the suite runner
# maps a scenario to ``<trace-dir>/<id>.json`` and writes ``<out-dir>/<id>.json``).
# Constrain them to a filename-safe charset so an ID can never traverse paths.
SCENARIO_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")

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


SECRET_NAME_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
NO_SECRET_DISCLOSURE_KEYS = {
    "secrets",
    "patterns",
    "check_messages",
    "check_tool_calls",
    "check_events",
}
NO_SECRET_DISCLOSURE_SURFACE_FLAGS = (
    "check_messages",
    "check_tool_calls",
    "check_events",
)


@dataclass(frozen=True)
class SecretRule:
    """One configured secret value or secret regex pattern.

    ``label`` is the redaction-safe identifier used in assertion evidence.
    Exactly one of ``value`` and ``pattern`` is set.
    """

    label: str
    value: str | None = None
    pattern: str | None = None
    named: bool = False


@dataclass(frozen=True)
class NoSecretDisclosureConfig:
    """Normalized ``no_secret_disclosure`` configuration for a scenario."""

    secrets: tuple[SecretRule, ...] = ()
    patterns: tuple[SecretRule, ...] = ()
    check_messages: bool = True
    check_tool_calls: bool = True
    check_events: bool = True

    @property
    def rule_count(self) -> int:
        return len(self.secrets) + len(self.patterns)


def _parse_secret_name(field_name: str, name: Any) -> str:
    if not isinstance(name, str) or not SECRET_NAME_RE.fullmatch(name):
        raise ScenarioValidationError(
            f"{field_name}.name must be 1-64 characters of letters, digits, "
            "'.', '_', ':' or '-'"
        )
    return name


def _parse_secret_entries(
    field_name: str,
    entries: Any,
    *,
    value_key: str,
    allow_named: bool,
) -> list[SecretRule]:
    if not isinstance(entries, list):
        raise ScenarioValidationError(f"{field_name} must be a list")

    rules: list[SecretRule] = []
    for index, entry in enumerate(entries):
        entry_name = f"{field_name}[{index}]"
        label = entry_name
        named = False
        raw_value: Any = entry

        if isinstance(entry, dict):
            if not allow_named:
                raise ScenarioValidationError(
                    f"{entry_name} must be a non-empty string"
                )
            unknown = sorted(set(entry) - {"name", value_key})
            if unknown:
                raise ScenarioValidationError(
                    f"{entry_name} has unsupported keys: {', '.join(map(str, unknown))}"
                )
            raw_value = entry.get(value_key)
            if "name" in entry:
                label = _parse_secret_name(entry_name, entry["name"])
                named = True

        if not isinstance(raw_value, str) or not raw_value:
            suffix = f".{value_key}" if isinstance(entry, dict) else ""
            raise ScenarioValidationError(
                f"{entry_name}{suffix} must be a non-empty string"
            )

        if value_key == "pattern":
            try:
                compiled = re.compile(raw_value)
            except re.error as exc:
                raise ScenarioValidationError(
                    f"{entry_name} is not a valid regular expression: {exc}"
                ) from exc
            if compiled.search("") is not None:
                raise ScenarioValidationError(
                    f"{entry_name} must not match the empty string"
                )
            rules.append(SecretRule(label=label, pattern=raw_value, named=named))
        else:
            rules.append(SecretRule(label=label, value=raw_value, named=named))

    return rules


def parse_no_secret_disclosure_config(
    expected: dict[str, Any],
) -> NoSecretDisclosureConfig:
    """Parse and validate no_secret_disclosure settings from ``expected``.

    Secrets may be configured as ``expected.secrets`` (strings or
    ``{name, value}`` objects), ``expected.forbidden_outputs`` (strings), and
    under ``expected.no_secret_disclosure`` (``secrets``, ``patterns`` and
    the ``check_*`` surface flags). All sources are merged. Returning a config
    with no rules is valid; the assertion then reports ``not_run``.
    """
    options = expected.get("no_secret_disclosure", {})
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise ScenarioValidationError("expected.no_secret_disclosure must be an object")

    unknown = sorted(set(options) - NO_SECRET_DISCLOSURE_KEYS)
    if unknown:
        raise ScenarioValidationError(
            "expected.no_secret_disclosure has unsupported keys: "
            + ", ".join(map(str, unknown))
        )

    flags: dict[str, bool] = {}
    for flag in NO_SECRET_DISCLOSURE_SURFACE_FLAGS:
        value = options.get(flag, True)
        if not isinstance(value, bool):
            raise ScenarioValidationError(
                f"expected.no_secret_disclosure.{flag} must be a boolean"
            )
        flags[flag] = value
    if not any(flags.values()):
        raise ScenarioValidationError(
            "expected.no_secret_disclosure must enable at least one of "
            "check_messages, check_tool_calls, check_events"
        )

    secrets: list[SecretRule] = []
    for field_name, key, source in (
        ("expected.secrets", "value", expected.get("secrets")),
        ("expected.forbidden_outputs", "value", expected.get("forbidden_outputs")),
        (
            "expected.no_secret_disclosure.secrets",
            "value",
            options.get("secrets"),
        ),
    ):
        if source is None:
            continue
        secrets.extend(
            _parse_secret_entries(
                field_name,
                source,
                value_key=key,
                allow_named=field_name != "expected.forbidden_outputs",
            )
        )

    patterns: list[SecretRule] = []
    if options.get("patterns") is not None:
        patterns = _parse_secret_entries(
            "expected.no_secret_disclosure.patterns",
            options["patterns"],
            value_key="pattern",
            allow_named=True,
        )

    seen_labels: set[str] = set()
    for rule in (*secrets, *patterns):
        if rule.label in seen_labels:
            raise ScenarioValidationError(
                f"duplicate secret name in no_secret_disclosure config: {rule.label}"
            )
        seen_labels.add(rule.label)

    for rule in (*secrets, *patterns):
        if rule.named and any(s.value and s.value in rule.label for s in secrets):
            raise ScenarioValidationError(
                "secret names must not contain a configured secret value"
            )

    return NoSecretDisclosureConfig(
        secrets=tuple(secrets),
        patterns=tuple(patterns),
        check_messages=flags["check_messages"],
        check_tool_calls=flags["check_tool_calls"],
        check_events=flags["check_events"],
    )


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

    if not SCENARIO_ID_RE.fullmatch(scenario_id):
        raise ScenarioValidationError(
            "id must contain only letters, digits, '.', '_', or '-'"
        )

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

    for tool_list_name in ("allowed_tools", "denied_tools"):
        tool_list = expected.get(tool_list_name)
        if tool_list is None:
            continue
        if not isinstance(tool_list, list):
            raise ScenarioValidationError(f"expected.{tool_list_name} must be a list")
        if not all(isinstance(tool, str) and tool.strip() for tool in tool_list):
            raise ScenarioValidationError(
                f"all items in expected.{tool_list_name} must be non-empty strings"
            )

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

        assertion_type = assertion_type.strip()
        if assertion_type == "no_secret_disclosure":
            parse_no_secret_disclosure_config(expected)
        if assertion_type == "memory_isolation":
            markers = (
                data.get("expected", {})
                .get("memory_isolation", {})
                .get("forbidden_markers")
            )
            if not isinstance(markers, list) or not markers:
                raise ScenarioValidationError(
                    "expected.memory_isolation.forbidden_markers must be a non-empty list"
                )
            if not all(isinstance(m, str) and m for m in markers):
                raise ScenarioValidationError(
                    "all items in expected.memory_isolation.forbidden_markers "
                    "must be non-empty strings"
                )
        if assertion_type == "goal_integrity":
            expected_goal = assertion.get("expected_goal")
            if not isinstance(expected_goal, str) or not expected_goal.strip():
                raise ScenarioValidationError(
                    f"assertions[{index}].expected_goal must be a non-empty string "
                    "for goal_integrity assertions"
                )

        if assertion_type == "approval_required":
            action = assertion.get("action")
            if not isinstance(action, str) or not action.strip():
                raise ScenarioValidationError(
                    f"assertions[{index}].action must be a non-empty string "
                    "for approval_required assertions"
                )

    return Scenario(
        id=scenario_id,
        title=title,
        category=category,
        severity=severity,
        raw=data,
    )
