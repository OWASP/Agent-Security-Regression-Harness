"""Target adapters for live scenario execution."""

from __future__ import annotations

from collections.abc import Callable
import importlib
import json
from typing import Any
from urllib import error, request

from agent_harness.scenario import Scenario
from agent_harness.trace import Trace, TraceValidationError


class AdapterError(RuntimeError):
    """Raised when a target adapter fails."""


def build_target_payload(scenario: Scenario) -> dict[str, Any]:
    """Build the payload sent to a target adapter."""
    return {
        "scenario_id": scenario.id,
        "input": scenario.raw["input"],
    }


def _trace_from_dict(trace_data: dict[str, Any], error_prefix: str) -> Trace:
    """Convert trace-shaped dictionary data into a Trace."""
    try:
        return Trace.from_dict(trace_data)
    except TraceValidationError as exc:
        raise AdapterError(f"{error_prefix}: {exc}") from exc


def load_python_callable(
    import_path: str,
) -> Callable[[dict[str, Any]], Trace | dict[str, Any]]:
    """Load a Python callable from a module:function import path."""
    if not isinstance(import_path, str) or not import_path.strip():
        raise AdapterError("Python target import path must be a non-empty string")

    if ":" not in import_path:
        raise AdapterError(
            "Python target must use 'module:function' format, "
            f"got {import_path!r}"
        )

    module_name, callable_name = import_path.split(":", 1)
    module_name = module_name.strip()
    callable_name = callable_name.strip()

    if not module_name or not callable_name:
        raise AdapterError(
            "Python target must use 'module:function' format with both parts present"
        )

    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        raise AdapterError(
            f"Could not import Python target module {module_name!r}"
        ) from exc

    target: Any = module

    try:
        for attr in callable_name.split("."):
            target = getattr(target, attr)
    except AttributeError as exc:
        raise AdapterError(
            f"Python target callable {callable_name!r} was not found "
            f"in module {module_name!r}"
        ) from exc

    if not callable(target):
        raise AdapterError(f"Python target {import_path!r} is not callable")

    return target


def run_http_target(scenario: Scenario, target_url: str) -> Trace:
    """Run a scenario against an HTTP target and return its trace."""
    body = build_target_payload(scenario)
    request_data = json.dumps(body).encode("utf-8")
    http_request = request.Request(
        target_url,
        data=request_data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=30) as response:
            response_text = response.read().decode("utf-8")
    except error.URLError as exc:
        raise AdapterError(f"HTTP target request failed: {exc}") from exc

    try:
        trace_data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"HTTP target returned invalid JSON: {exc}") from exc

    if not isinstance(trace_data, dict):
        raise AdapterError(
            f"HTTP target returned non-object JSON: got {type(trace_data).__name__}"
        )

    return _trace_from_dict(trace_data, "HTTP target returned invalid trace")


def run_python_callable_target(
    scenario: Scenario,
    agent_callable: Callable[[dict[str, Any]], Trace | dict[str, Any]],
) -> Trace:
    """Run a scenario against a Python callable target and return its trace."""
    payload = build_target_payload(scenario)

    try:
        trace_result = agent_callable(payload)
    except Exception as exc:
        raise AdapterError(f"Python callable raised an exception: {exc}") from exc

    if isinstance(trace_result, Trace):
        return trace_result

    if not isinstance(trace_result, dict):
        raise AdapterError(
            "Python callable must return a Trace or trace-shaped dictionary; "
            f"got {type(trace_result).__name__}"
        )

    return _trace_from_dict(
        trace_result,
        "Python callable returned invalid trace",
    )