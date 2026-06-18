"""SARIF 2.1.0 output for harness results."""

from __future__ import annotations

import json
from typing import Any

from agent_harness.result import HarnessResult

_TOOL_NAME = "agent-harness"
_TOOL_VERSION = "0.1.0"
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