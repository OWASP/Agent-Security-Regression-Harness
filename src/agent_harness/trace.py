"""Execution trace models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Trace:
    """Execution trace captured during a scenario run."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert the trace to a JSON-serializable dictionary."""
        return {
            "messages": self.messages,
            "tool_calls": self.tool_calls,
            "events": self.events,
        }