"""OpenAI Agents SDK adapter."""

from __future__ import annotations

import importlib
import json
from typing import Any

from agent_harness.adapters import AdapterError, build_target_payload
from agent_harness.scenario import Scenario
from agent_harness.trace import Trace, TraceValidationError


OPENAI_AGENTS_INSTALL_MESSAGE = (
    "OpenAI Agents SDK adapter dependencies are not installed. "
    'Install them with: python -m pip install "'
    'owasp-agent-security-regression-harness[openai-agents]"'
)


def build_openai_agents_input(scenario: Scenario) -> str:
    """Build the user input string passed to the OpenAI Agents SDK runner."""
    payload = build_target_payload(scenario)

    try:
        return json.dumps(payload, indent=2, sort_keys=True)
    except TypeError as exc:
        raise AdapterError(f"Scenario input is not JSON serializable: {exc}") from exc


def _load_default_runner() -> Any:
    """Load the OpenAI Agents SDK Runner lazily."""
    try:
        agents_module = importlib.import_module("agents")  # type: ignore[import-not-found]
    except ImportError as exc:
        raise AdapterError(OPENAI_AGENTS_INSTALL_MESSAGE) from exc

    return agents_module.Runner


def _field(value: Any, name: str, default: Any = None) -> Any:
    """Read a field from either an object or a dictionary."""
    if isinstance(value, dict):
        return value.get(name, default)

    return getattr(value, name, default)


def _parse_tool_arguments(arguments: Any) -> dict[str, Any]:
    """Normalize tool arguments into a dictionary."""
    if arguments is None:
        return {}

    if isinstance(arguments, dict):
        return arguments

    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            return {"raw": arguments}

        if isinstance(parsed, dict):
            return parsed

        return {"raw": parsed}

    return {"raw": arguments}


def _extract_tool_call(item: Any) -> dict[str, Any] | None:
    """Extract a harness tool call from an OpenAI Agents SDK run item."""
    item_type = str(_field(item, "type", "") or "")
    class_name = type(item).__name__

    if "Output" in class_name or item_type.endswith("_output"):
        return None

    raw_item = _field(item, "raw_item", item)
    function = _field(raw_item, "function", {})

    name = (
        _field(item, "tool_name")
        or _field(item, "name")
        or _field(raw_item, "name")
        or _field(function, "name")
    )

    if not name:
        return None

    arguments = (
        _field(item, "tool_arguments")
        or _field(item, "arguments")
        or _field(raw_item, "arguments")
        or _field(function, "arguments")
    )

    return {
        "name": str(name),
        "arguments": _parse_tool_arguments(arguments),
    }


def _trace_from_openai_agents_result(
    scenario: Scenario,
    runner_input: str,
    result: Any,
) -> Trace:
    """Convert an OpenAI Agents SDK run result into a harness Trace."""
    final_output = _field(result, "final_output", "")

    if final_output is None:
        assistant_content = ""
    elif isinstance(final_output, str):
        assistant_content = final_output
    else:
        assistant_content = str(final_output)

    tool_calls = []

    for item in _field(result, "new_items", []) or []:
        tool_call = _extract_tool_call(item)
        if tool_call is not None:
            tool_calls.append(tool_call)

    trace_data = {
        "messages": [
            {
                "role": "user",
                "content": runner_input,
            },
            {
                "role": "assistant",
                "content": assistant_content,
            },
        ],
        "tool_calls": tool_calls,
        "events": [
            {
                "type": "adapter",
                "id": "openai_agents",
            },
            {
                "type": "scenario",
                "id": scenario.id,
            },
        ],
    }

    try:
        return Trace.from_dict(trace_data)
    except TraceValidationError as exc:
        raise AdapterError(f"OpenAI Agents SDK returned invalid trace: {exc}") from exc


def run_openai_agents_target(
    scenario: Scenario,
    agent: Any,
    *,
    runner: Any | None = None,
    max_turns: int | None = None,
) -> Trace:
    """Run a scenario against an OpenAI Agents SDK Agent and return its trace."""
    selected_runner = runner if runner is not None else _load_default_runner()
    run_sync = getattr(selected_runner, "run_sync", None)

    if not callable(run_sync):
        raise AdapterError("OpenAI Agents SDK runner must provide run_sync")

    runner_input = build_openai_agents_input(scenario)
    runner_kwargs: dict[str, Any] = {}

    if max_turns is not None:
        runner_kwargs["max_turns"] = max_turns

    try:
        result = run_sync(agent, runner_input, **runner_kwargs)
    except Exception as exc:
        raise AdapterError(f"OpenAI Agents SDK runner failed: {exc}") from exc

    return _trace_from_openai_agents_result(scenario, runner_input, result)
