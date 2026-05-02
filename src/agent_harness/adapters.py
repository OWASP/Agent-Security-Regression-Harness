"""Target adapters for live scenario execution."""

from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from agent_harness.scenario import Scenario
from agent_harness.trace import Trace, TraceValidationError

class AdapterError(RuntimeError):
    """Raised when a live target adapter fails"""
    
def build_http_request_body(scenario: Scenario) -> dict[str, Any]:
    """Build the JSON request body sent to an HTTP target."""
    return {
        "scenario_id": scenario.id,
        "input": scenario.raw["input"],
    }

def run_http_target(scenario: Scenario, target_url: str) -> Trace:
    """Run a scenario against an HTTP target and return its trace."""
    body = build_http_request_body(scenario)
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
    
    try:
        return Trace.from_dict(trace_data)
    except TraceValidationError as exc:
        raise AdapterError(f"HTTP target returned invalid trace: {exc}") from exc 
    

