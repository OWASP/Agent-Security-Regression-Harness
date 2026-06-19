"""Result models for harness execution."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from agent_harness.trace import Trace

ResultStatus = Literal["pass", "fail", "error", "not_run"]
RunMode = Literal["dry_run", "trace", "live"]


@dataclass(frozen=True)
class AssertionResult:
    """Result of one assertion evaluation."""

    id: str
    result: ResultStatus
    evidence: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the assertion result to a JSON-serializable dictionary."""
        data: dict[str, Any] = {
            "id": self.id,
            "result": self.result,
        }

        if self.evidence is not None:
            data["evidence"] = self.evidence

        return data


@dataclass(frozen=True)
class HarnessResult:
    """Top-level result produced by a harness run."""

    scenario_id: str
    mode: RunMode
    result: ResultStatus
    assertions: list[AssertionResult] = field(default_factory=list)
    trace: Trace = field(default_factory=Trace)

    def to_dict(self) -> dict[str, Any]:
        """Convert the harness result to a JSON-serializable dictionary."""
        return {
            "scenario_id": self.scenario_id,
            "mode": self.mode,
            "result": self.result,
            "assertions": [assertion.to_dict() for assertion in self.assertions],
            "trace": self.trace.to_dict(),
        }

    def to_json(self) -> str:
        """Convert the harness result to formatted JSON."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)
    

def aggregate_assertion_results(assertions: list[AssertionResult]) -> ResultStatus:
    """Aggregate assertion results into one top-level result."""

    if not assertions:
        return "not_run"

    statuses = [assertion.result for assertion in assertions]

    if "fail" in statuses:
        return "fail"

    if "error" in statuses:
        return "error"

    if all(status == "pass" for status in statuses):
        return "pass"

    return "not_run"


SuiteErrorReason = Literal[
    "missing_trace",
    "invalid_scenario",
    "invalid_trace",
    "duplicate_scenario_id",
]


@dataclass(frozen=True)
class SuiteEntry:
    """One scenario's outcome within a suite run.

    Carries enough provenance (scenario path, trace path, severity, category)
    to make the aggregate summary a self-contained audit record. ``detail``
    holds the full :class:`HarnessResult` for scenarios that actually ran;
    ``error_reason`` records why a scenario could not run.
    """

    scenario_path: str
    result: ResultStatus
    scenario_id: str | None = None
    category: str | None = None
    severity: str | None = None
    trace_path: str | None = None
    error_reason: SuiteErrorReason | None = None
    evidence: str | None = None
    detail: HarnessResult | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the suite entry to a JSON-serializable dictionary."""
        data: dict[str, Any] = {
            "scenario_path": self.scenario_path,
            "result": self.result,
        }

        for key in ("scenario_id", "category", "severity", "trace_path"):
            value = getattr(self, key)
            if value is not None:
                data[key] = value

        if self.error_reason is not None:
            data["error_reason"] = self.error_reason
        if self.evidence is not None:
            data["evidence"] = self.evidence
        if self.detail is not None:
            data["detail"] = self.detail.to_dict()

        return data


@dataclass(frozen=True)
class SuiteResult:
    """Aggregate result produced by running a suite of scenarios."""

    entries: list[SuiteEntry] = field(default_factory=list)

    @property
    def result(self) -> ResultStatus:
        """Overall suite status using the fail > error > pass > not_run order."""
        return aggregate_suite_results([entry.result for entry in self.entries])

    @property
    def counts(self) -> dict[str, int]:
        """Per-status tallies, so coverage gaps stay visible in the summary."""
        counts = {
            "total": len(self.entries),
            "pass": 0,
            "fail": 0,
            "error": 0,
            "not_run": 0,
        }
        for entry in self.entries:
            counts[entry.result] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        """Convert the suite result to a JSON-serializable dictionary."""
        return {
            "result": self.result,
            "counts": self.counts,
            "scenarios": [entry.to_dict() for entry in self.entries],
        }

    def to_json(self) -> str:
        """Convert the suite result to formatted JSON."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def aggregate_suite_results(statuses: list[ResultStatus]) -> ResultStatus:
    """Aggregate per-scenario statuses into one suite-level result.

    Mirrors :func:`aggregate_assertion_results`: a single ``fail`` fails the
    suite, an ``error`` (missing trace, invalid input, duplicate id) surfaces
    as ``error`` so it still gates CI under ``--exit-on-fail`` without being
    mistaken for an ordinary assertion failure.
    """
    if not statuses:
        return "not_run"

    if "fail" in statuses:
        return "fail"

    if "error" in statuses:
        return "error"

    if all(status == "pass" for status in statuses):
        return "pass"

    return "not_run"


