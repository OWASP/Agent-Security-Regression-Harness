"""Tests for SARIF output generation."""

from __future__ import annotations

import json
from pathlib import Path

from agent_harness.result import AssertionResult, HarnessResult
from agent_harness.sarif import build_sarif, write_sarif


def _make_result(
    assertions: list[AssertionResult] | None = None,
    overall: str = "pass",
) -> HarnessResult:
    if assertions is None:
        assertions = []
    return HarnessResult(
        scenario_id="test-scenario",
        result=overall,
        assertions=assertions,
    )


def test_sarif_version_and_schema():
    result = _make_result()
    sarif = build_sarif(result, "test-scenario")
    assert sarif["version"] == "2.1.0"
    assert "$schema" in sarif


def test_sarif_tool_driver():
    result = _make_result()
    sarif = build_sarif(result, "test-scenario")
    driver = sarif["runs"][0]["tool"]["driver"]
    assert driver["name"] == "agent-harness"
    assert "rules" in driver


def test_sarif_pass_assertion():
    assertions = [AssertionResult(id="no_denied_tool_call", result="pass", evidence="ok")]
    result = _make_result(assertions)
    sarif = build_sarif(result, "test-scenario")

    sarif_result = sarif["runs"][0]["results"][0]
    assert sarif_result["ruleId"] == "no_denied_tool_call"
    assert sarif_result["level"] == "none"


def test_sarif_fail_assertion():
    assertions = [AssertionResult(id="no_secret_disclosure", result="fail", evidence="leaked")]
    result = _make_result(assertions, overall="fail")
    sarif = build_sarif(result, "test-scenario")

    sarif_result = sarif["runs"][0]["results"][0]
    assert sarif_result["level"] == "error"
    assert sarif_result["message"]["text"] == "leaked"


def test_sarif_not_run_assertion():
    assertions = [AssertionResult(id="goal_integrity", result="not_run", evidence="no config")]
    result = _make_result(assertions)
    sarif = build_sarif(result, "test-scenario")

    sarif_result = sarif["runs"][0]["results"][0]
    assert sarif_result["level"] == "note"


def test_sarif_rules_deduplicated():
    assertions = [
        AssertionResult(id="no_denied_tool_call", result="pass", evidence="ok"),
        AssertionResult(id="no_denied_tool_call", result="fail", evidence="bad"),
    ]
    result = _make_result(assertions)
    sarif = build_sarif(result, "test-scenario")

    rules = sarif["runs"][0]["tool"]["driver"]["rules"]
    rule_ids = [r["id"] for r in rules]
    assert len(rule_ids) == len(set(rule_ids))


def test_sarif_empty_results():
    result = _make_result()
    sarif = build_sarif(result, "test-scenario")
    assert len(sarif["runs"][0]["results"]) == 1
    assert sarif["runs"][0]["results"][0]["ruleId"] == "no_assertions"


def test_write_sarif_creates_file(tmp_path: Path):
    result = _make_result()
    out_path = tmp_path / "output.sarif"
    write_sarif(result, "test-scenario", out_path)

    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert data["version"] == "2.1.0"
