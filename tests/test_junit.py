"""Tests for JUnit XML result output."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from agent_harness.junit import result_to_junit_xml
from agent_harness.result import AssertionResult, HarnessResult


def test_result_to_junit_xml_maps_assertion_statuses():
    result = HarnessResult(
        scenario_id="scenario.example",
        mode="trace",
        result="fail",
        assertions=[
            AssertionResult("passes", "pass", "ok"),
            AssertionResult("fails", "fail", "bad tool call"),
            AssertionResult("errors", "error", "adapter broke"),
            AssertionResult("skips", "not_run", "not implemented"),
        ],
    )

    testsuite = ET.fromstring(result_to_junit_xml(result))

    assert testsuite.attrib["tests"] == "4"
    assert testsuite.attrib["failures"] == "1"
    assert testsuite.attrib["errors"] == "1"
    assert testsuite.attrib["skipped"] == "1"

    testcases = {case.attrib["name"]: case for case in testsuite.findall("testcase")}
    assert testcases["passes"].find("failure") is None
    assert testcases["passes"].find("error") is None
    assert testcases["passes"].find("skipped") is None
    assert testcases["fails"].find("failure").text == "bad tool call"
    assert testcases["errors"].find("error").text == "adapter broke"
    assert testcases["skips"].find("skipped").text == "not implemented"
