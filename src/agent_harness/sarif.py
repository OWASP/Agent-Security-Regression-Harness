"""SARIF v2.1.0 output generation for code scanning integration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_harness.result import HarnessResult

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"

SEVERITY_MAP = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "none",
}

RESULT_LEVEL_MAP = {
    "pass": "none",
    "fail": "error",
    "error": "error",
    "not_run": "note",
}


def build_sarif(result: HarnessResult, scenario_id: str) -> dict[str, Any]:
    """Convert a HarnessResult to SARIF v2.1.0 format."""
    rules: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    rule_ids_seen: set[str] = set()

    for assertion in result.assertions:
        if assertion.id not in rule_ids_seen:
            rules.append(_build_rule(assertion.id))
            rule_ids_seen.add(assertion.id)

        level = RESULT_LEVEL_MAP.get(assertion.result, "none")
        sarif_result: dict[str, Any] = {
            "ruleId": assertion.id,
            "level": level,
            "message": {"text": assertion.evidence},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": scenario_id},
                        "region": {"startLine": 1},
                    }
                }
            ],
        }

        if assertion.result == "fail":
            sarif_result["properties"] = {"result": assertion.result}

        results.append(sarif_result)

    tool = {
        "driver": {
            "name": "agent-harness",
            "semanticVersion": "0.1.0",
            "rules": rules,
        }
    }

    run = {
        "tool": tool,
        "results": results if results else [
            {
                "ruleId": "no_assertions",
                "level": "note",
                "message": {"text": "No assertions were evaluated"},
            }
        ],
    }

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [run],
    }


def _build_rule(rule_id: str) -> dict[str, Any]:
    """Build a SARIF rule definition."""
    return {
        "id": rule_id,
        "shortDescription": {"text": f"Security assertion: {rule_id}"},
        "helpUri": f"https://github.com/OWASP/Agent-Security-Regression-Harness/blob/main/README.md#{rule_id}",
    }


def write_sarif(result: HarnessResult, scenario_id: str, path: str | Path) -> None:
    """Write SARIF output to a file."""
    sarif = build_sarif(result, scenario_id)
    Path(path).write_text(json.dumps(sarif, indent=2) + "\n")
