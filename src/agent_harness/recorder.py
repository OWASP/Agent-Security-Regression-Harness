"""Helpers for recording execution traces."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from agent_harness.trace import Trace


class TraceRecorder:
    """Incrementally build a Trace object."""

    def __init__(self) -> None:
        """Create an empty trace recorder."""
        self._messages: list[dict[str, Any]] = []
        self._tool_calls: list[dict[str, Any]] = []
        self._events: list[dict[str, Any]] = []

    def add_message(self, role: str, content: str) -> None:
        """Record a conversation message."""
        if not isinstance(role, str) or not role.strip():
            raise ValueError("role must be a non-empty string")

        if not isinstance(content, str):
            raise ValueError("content must be a string")

        self._messages.append({"role": role.strip(), "content": content})

    def add_tool_call(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> None:
        """Record a tool call."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("tool name must be a non-empty string")

        if arguments is None:
            arguments = {}

        if not isinstance(arguments, dict):
            raise ValueError("tool call arguments must be an object")

        self._tool_calls.append(
            {
                "name": name.strip(),
                "arguments": deepcopy(arguments),
            }
        )

    def add_event(
        self,
        event_type: str,
        event_id: str | None = None,
        **fields: Any,
    ) -> None:
        """Record a structured trace event."""
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError("event type must be a non-empty string")

        event: dict[str, Any] = {"type": event_type.strip()}

        if event_id is not None:
            if not isinstance(event_id, str) or not event_id.strip():
                raise ValueError("event id must be a non-empty string")
            event["id"] = event_id.strip()

        event.update(deepcopy(fields))
        self._events.append(event)

    def to_trace(self) -> Trace:
        """Convert the recorded data into a Trace."""
        return Trace(
            messages=deepcopy(self._messages),
            tool_calls=deepcopy(self._tool_calls),
            events=deepcopy(self._events),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the recorded data into a JSON-serializable dictionary."""
        return self.to_trace().to_dict()