"""Tests for target adapters."""

from __future__ import annotations

import pytest

from agent_harness.adapters import (
    AdapterError,
    load_python_callable,
    run_python_callable_target,
)
from agent_harness.trace import Trace
from test_assertions import make_scenario


def write_fake_target_module(tmp_path, monkeypatch) -> str:
    """Create an importable fake Python target module for adapter tests."""
    module_path = tmp_path / "fake_python_target.py"
    module_path.write_text(
        '''
NON_CALLABLE = "not callable"


def run_agent(payload):
    return {
        "messages": [],
        "tool_calls": [],
        "events": [],
    }
''',
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    return "fake_python_target"


def test_python_callable_receives_target_payload():
    scenario = make_scenario(assertions=[])
    observed_payload = {}

    def fake_agent(payload):
        observed_payload.update(payload)
        return {
            "messages": [],
            "tool_calls": [],
            "events": [],
        }

    trace = run_python_callable_target(scenario, fake_agent)

    assert isinstance(trace, Trace)
    assert observed_payload == {
        "scenario_id": scenario.id,
        "input": scenario.raw["input"],
    }


def test_python_callable_accepts_trace_return():
    scenario = make_scenario(assertions=[])

    expected_trace = Trace(
        messages=[{"role": "assistant", "content": "ok"}],
        tool_calls=[],
        events=[],
    )

    def fake_agent(payload):
        return expected_trace

    trace = run_python_callable_target(scenario, fake_agent)

    assert trace is expected_trace


def test_python_callable_accepts_trace_shaped_dict_return():
    scenario = make_scenario(assertions=[])

    def fake_agent(payload):
        return {
            "messages": [{"role": "assistant", "content": "ok"}],
            "tool_calls": [],
            "events": [],
        }

    trace = run_python_callable_target(scenario, fake_agent)

    assert trace.to_dict() == {
        "messages": [{"role": "assistant", "content": "ok"}],
        "tool_calls": [],
        "events": [],
    }


def test_python_callable_wraps_exception_in_adapter_error():
    scenario = make_scenario(assertions=[])

    def broken_agent(payload):
        raise RuntimeError("boom")

    with pytest.raises(AdapterError, match="Python callable raised an exception"):
        run_python_callable_target(scenario, broken_agent)


@pytest.mark.parametrize("bad_return", ["not a dict", 123, [], None])
def test_python_callable_rejects_invalid_return_type(bad_return):
    scenario = make_scenario(assertions=[])

    def bad_agent(payload):
        return bad_return

    with pytest.raises(AdapterError, match="Trace or trace-shaped dictionary"):
        run_python_callable_target(scenario, bad_agent)


def test_python_callable_wraps_invalid_trace_shape():
    scenario = make_scenario(assertions=[])

    def malformed_agent(payload):
        return {
            "messages": [],
            "tool_calls": "should be a list",
            "events": [],
        }

    with pytest.raises(AdapterError, match="Python callable returned invalid trace"):
        run_python_callable_target(scenario, malformed_agent)


def test_load_python_callable_loads_valid_module_function(tmp_path, monkeypatch):
    module_name = write_fake_target_module(tmp_path, monkeypatch)

    target = load_python_callable(f"{module_name}:run_agent")

    assert callable(target)


def test_load_python_callable_rejects_missing_colon():
    with pytest.raises(AdapterError, match="module:function"):
        load_python_callable("fake_python_target.run_agent")


def test_load_python_callable_rejects_missing_module_name():
    with pytest.raises(AdapterError, match="both parts present"):
        load_python_callable(":run_agent")


def test_load_python_callable_rejects_missing_callable_name():
    with pytest.raises(AdapterError, match="both parts present"):
        load_python_callable("fake_python_target:")


def test_load_python_callable_rejects_missing_module():
    with pytest.raises(AdapterError, match="Could not import Python target module"):
        load_python_callable("definitely_missing_agent_target_module:run_agent")


def test_load_python_callable_rejects_missing_callable(tmp_path, monkeypatch):
    module_name = write_fake_target_module(tmp_path, monkeypatch)

    with pytest.raises(AdapterError, match="was not found"):
        load_python_callable(f"{module_name}:does_not_exist")


def test_load_python_callable_rejects_non_callable(tmp_path, monkeypatch):
    module_name = write_fake_target_module(tmp_path, monkeypatch)

    with pytest.raises(AdapterError, match="is not callable"):
        load_python_callable(f"{module_name}:NON_CALLABLE")