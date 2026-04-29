"""Result models for harness execution."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from agent_harness.trace import Trace


ResultStatus = Literal["pass", "fail", "error", "not_run"]
RunMode = Literal["dry_run", "live"]


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