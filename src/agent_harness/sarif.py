"""SARIF 2.1.0 output for harness results."""

from __future__ import annotations

import json
from typing import Any

from agent_harness import __version__
from agent_harness.result import HarnessResult, SuiteResult

_TOOL_NAME = "agent-harness"
_TOOL_VERSION = __version__
_TOOL_URI = "https://github.com/OWASP/Agent-Security-Regression-Harness"
_SCHEMA = "https://schemastore.azurewebsites.net/schemas/json/sarif-2.1.0-rtm.5.json"

_SARIF_LEVEL: dict[str, str] = {
    "fail": "error",
    "error": "warning",
    "pass": "none",
    "not_run": "none",
}


def result_to_sarif(result: HarnessResult) -> str:
    """Render a harness result as a SARIF 2.1.0 document.

    Only failed and errored assertions produce SARIF results. Passed and
    not-run assertions are omitted because SARIF results represent findings,
    not confirmations. Rule IDs are derived from assertion IDs and are stable
    across runs of the same scenario.
    """
    seen_rule_ids: set[str] = set()
    rules: list[dict[str, Any]] = []
    sarif_results: list[dict[str, Any]] = []

    for assertion in result.assertions:
        if assertion.result in {"pass", "not_run"}:
            continue

        rule_id = f"agent-harness/{assertion.id}"

        if rule_id not in seen_rule_ids:
            seen_rule_ids.add(rule_id)
            rules.append(
                {
                    "id": rule_id,
                    "name": assertion.id,
                    "shortDescription": {
                        "text": f"Security assertion: {assertion.id}",
                    },
                    "helpUri": _TOOL_URI,
                    "properties": {
                        "tags": ["security", "regression"],
                    },
                }
            )

        message_text = (
            f"Scenario '{result.scenario_id}' assertion '{assertion.id}'"
            f" {assertion.result}"
        )
        if assertion.evidence:
            message_text += f": {assertion.evidence}"

        sarif_results.append(
            {
                "ruleId": rule_id,
                "level": _SARIF_LEVEL[assertion.result],
                "message": {"text": message_text},
                "properties": {
                    "scenario_id": result.scenario_id,
                    "assertion_id": assertion.id,
                    "result": assertion.result,
                    "evidence": assertion.evidence,
                },
                "locations": [],
            }
        )

    sarif: dict[str, Any] = {
        "$schema": _SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": _TOOL_NAME,
                        "version": _TOOL_VERSION,
                        "informationUri": _TOOL_URI,
                        "rules": rules,
                    }
                },
                "results": sarif_results,
                "properties": {
                    "scenario_id": result.scenario_id,
                    "mode": result.mode,
                    "overall_result": result.result,
                },
            }
        ],
    }

    return json.dumps(sarif, indent=2) + "\n"


def suite_result_to_sarif(suite_result: SuiteResult) -> str:
    """Render an aggregate suite result as a SARIF 2.1.0 document."""
    seen_rule_ids: set[str] = set()
    rules: list[dict[str, Any]] = []
    sarif_results: list[dict[str, Any]] = []

    for entry in suite_result.entries:
        locations = (
            [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": entry.scenario_path.replace("\\", "/"),
                        }
                    }
                }
            ]
            if entry.scenario_path
            else []
        )

        if entry.detail is not None:
            for assertion in entry.detail.assertions:
                if assertion.result in {"pass", "not_run"}:
                    continue

                rule_id = f"agent-harness/{assertion.id}"
                if rule_id not in seen_rule_ids:
                    seen_rule_ids.add(rule_id)
                    rules.append(
                        {
                            "id": rule_id,
                            "name": assertion.id,
                            "shortDescription": {
                                "text": f"Security assertion: {assertion.id}",
                            },
                            "helpUri": _TOOL_URI,
                            "properties": {
                                "tags": ["security", "regression"],
                            },
                        }
                    )

                message_text = (
                    f"Scenario '{entry.detail.scenario_id}' assertion '{assertion.id}'"
                    f" {assertion.result}"
                )
                if assertion.evidence:
                    message_text += f": {assertion.evidence}"

                sarif_results.append(
                    {
                        "ruleId": rule_id,
                        "level": _SARIF_LEVEL[assertion.result],
                        "message": {"text": message_text},
                        "properties": {
                            "scenario_id": entry.detail.scenario_id,
                            "scenario_path": entry.scenario_path,
                            "assertion_id": assertion.id,
                            "result": assertion.result,
                            "evidence": assertion.evidence,
                        },
                        "locations": locations,
                    }
                )
            continue

        if entry.result in {"fail", "error"}:
            reason = entry.error_reason or "suite_error"
            rule_id = f"agent-harness/{reason}"
            if rule_id not in seen_rule_ids:
                seen_rule_ids.add(rule_id)
                rules.append(
                    {
                        "id": rule_id,
                        "name": reason,
                        "shortDescription": {
                            "text": f"Suite execution error: {reason}",
                        },
                        "helpUri": _TOOL_URI,
                        "properties": {
                            "tags": ["security", "regression"],
                        },
                    }
                )

            target_label = entry.scenario_id or entry.scenario_path
            message_text = f"Scenario '{target_label}' suite error ({reason})"
            if entry.evidence:
                message_text += f": {entry.evidence}"

            sarif_results.append(
                {
                    "ruleId": rule_id,
                    "level": _SARIF_LEVEL[entry.result],
                    "message": {"text": message_text},
                    "properties": {
                        "scenario_id": entry.scenario_id,
                        "scenario_path": entry.scenario_path,
                        "error_reason": reason,
                        "result": entry.result,
                        "evidence": entry.evidence,
                    },
                    "locations": locations,
                }
            )

    sarif: dict[str, Any] = {
        "$schema": _SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": _TOOL_NAME,
                        "version": _TOOL_VERSION,
                        "informationUri": _TOOL_URI,
                        "rules": rules,
                    }
                },
                "results": sarif_results,
                "properties": {
                    "mode": "suite",
                    "overall_result": suite_result.result,
                    "counts": suite_result.counts,
                },
            }
        ],
    }

    return json.dumps(sarif, indent=2) + "\n"
