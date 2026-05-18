"""Execution trace models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class TraceValidationError(ValueError):
    """Raised when a trace file is invalid"""


def _validate_object_items(field_name: str, items: list[Any]) -> None:
    """Validate that every trace list item is an object."""
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise TraceValidationError(f"{field_name}[{index}] must be an object")


@dataclass(frozen=True)
class Trace:
    """Execution trace captured during a scenario run."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Any) -> Trace: 
        """Create a trace from parsed JSON data."""
        if not isinstance(data, dict):
            raise TraceValidationError("trace must be a JSON object")
        
        messages = data.get("messages", [])
        tool_calls = data.get("tool_calls", [])
        events = data.get("events", [])
        
        if not isinstance(messages, list):
            raise TraceValidationError("messages must be a list")
        
        if not isinstance(tool_calls, list):
            raise TraceValidationError("tool_calls must be a list")
        
        if not isinstance(events, list):
            raise TraceValidationError("events must be a list")

        _validate_object_items("messages", messages)
        _validate_object_items("tool_calls", tool_calls)
        _validate_object_items("events", events)
        
        return cls(messages=messages, tool_calls=tool_calls, events=events)    
        

    def to_dict(self) -> dict[str, Any]:
        """Convert the trace to a JSON-serializable dictionary."""
        return {
            "messages": self.messages,
            "tool_calls": self.tool_calls,
            "events": self.events,
        }

def load_trace(path: str | Path) -> Trace:
    """Load a trace JSON file."""
    trace_path = Path(path)
    
    if not trace_path.exists():
        raise TraceValidationError(f"trace file does not exist: {trace_path}")
    
    try:
        data = json.loads(trace_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TraceValidationError(f"invalid JSON: {exc}") from exc
    
    return Trace.from_dict(data)
