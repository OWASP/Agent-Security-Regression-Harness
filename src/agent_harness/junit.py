"""JUnit XML rendering for harness results."""

from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, tostring

from agent_harness.result import AssertionResult, HarnessResult, SuiteResult


def _build_testsuite_element(result: HarnessResult) -> tuple[Element, int, int, int, int]:
    failures = sum(1 for assertion in result.assertions if assertion.result == "fail")
    errors = sum(1 for assertion in result.assertions if assertion.result == "error")
    skipped = sum(1 for assertion in result.assertions if assertion.result == "not_run")
    total = len(result.assertions)

    testsuite = Element(
        "testsuite",
        {
            "name": result.scenario_id,
            "tests": str(total),
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

    return testsuite, total, failures, errors, skipped


def result_to_junit_xml(result: HarnessResult) -> str:
    """Render a harness result as a single JUnit testsuite."""
    testsuite, _, _, _, _ = _build_testsuite_element(result)
    return tostring(testsuite, encoding="unicode") + "\n"


def suite_result_to_junit_xml(suite_result: SuiteResult) -> str:
    """Render an aggregate suite result as a JUnit <testsuites> document."""
    root = Element("testsuites")
    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0

    for entry in suite_result.entries:
        if entry.detail is not None:
            testsuite, tests, failures, errors, skipped = _build_testsuite_element(
                entry.detail
            )
            root.append(testsuite)
            total_tests += tests
            total_failures += failures
            total_errors += errors
            total_skipped += skipped
            continue

        suite_name = entry.scenario_id or entry.scenario_path
        reason = entry.error_reason or "suite_error"
        testsuite = SubElement(
            root,
            "testsuite",
            {
                "name": suite_name,
                "tests": "1",
                "failures": "0",
                "errors": "1",
                "skipped": "0",
            },
        )
        testcase = SubElement(
            testsuite,
            "testcase",
            {
                "classname": suite_name,
                "name": reason,
            },
        )
        err_elem = SubElement(testcase, "error", {"message": f"suite error: {reason}"})
        err_elem.text = entry.evidence or reason
        total_tests += 1
        total_errors += 1

    root.set("tests", str(total_tests))
    root.set("failures", str(total_failures))
    root.set("errors", str(total_errors))
    root.set("skipped", str(total_skipped))

    return tostring(root, encoding="unicode") + "\n"


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
