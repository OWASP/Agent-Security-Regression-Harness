"""JUnit XML rendering for harness results."""

from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, tostring

from agent_harness.result import AssertionResult, HarnessResult


def result_to_junit_xml(result: HarnessResult) -> str:
    """Render a harness result as a single JUnit testsuite."""
    failures = sum(1 for assertion in result.assertions if assertion.result == "fail")
    errors = sum(1 for assertion in result.assertions if assertion.result == "error")
    skipped = sum(1 for assertion in result.assertions if assertion.result == "not_run")

    testsuite = Element(
        "testsuite",
        {
            "name": result.scenario_id,
            "tests": str(len(result.assertions)),
            "failures": str(failures),
            "errors": str(errors),
            "skipped": str(skipped),
        },
    )

    for assertion in result.assertions:
        testcase = SubElement(
            testsuite,
            "testcase",
            {
                "classname": result.scenario_id,
                "name": assertion.id,
            },
        )
        _append_assertion_status(testcase, assertion)

    return tostring(testsuite, encoding="unicode") + "\n"


def _append_assertion_status(testcase: Element, assertion: AssertionResult) -> None:
    evidence = assertion.evidence or assertion.result
    if assertion.result == "fail":
        failure = SubElement(testcase, "failure", {"message": "assertion failed"})
        failure.text = evidence
    elif assertion.result == "error":
        error = SubElement(testcase, "error", {"message": "assertion error"})
        error.text = evidence
    elif assertion.result == "not_run":
        skipped = SubElement(testcase, "skipped", {"message": "assertion not run"})
        skipped.text = evidence
