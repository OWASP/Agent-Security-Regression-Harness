"""Example Python callable target for local harness execution."""

from __future__ import annotations

from typing import Any

from agent_harness.recorder import TraceRecorder


NON_CALLABLE = "not callable"


def run_agent(payload: dict[str, Any]) -> dict[str, Any]:
    """Run a toy agent and return trace-shaped JSON."""
    scenario_input = payload.get("input", {}) or {}
    user_message = scenario_input.get("user_message", "") or ""

    recorder = TraceRecorder()
    recorder.add_message("user", user_message)
    recorder.add_message("assistant", "Here is the summary.")
    recorder.add_event("goal", "summarize_document")

    return recorder.to_dict()