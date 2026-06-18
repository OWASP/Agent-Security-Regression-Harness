"""Tests for target adapters."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from urllib import error

import pytest
from test_assertions import make_scenario

from agent_harness.adapters import (
    AdapterError,
    load_python_callable,
    run_http_target,
    run_python_callable_target,
)
from agent_harness.trace import Trace


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


def test_python_callable_wraps_invalid_trace_item_shape():
    scenario = make_scenario(assertions=[])

    def malformed_agent(payload):
        return {
            "messages": ["not an object"],
            "tool_calls": [],
            "events": [],
        }

    with pytest.raises(
        AdapterError,
        match=r"Python callable returned invalid trace: messages\[0\] must be an object",
    ):
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


def test_python_async_callable_receives_target_payload():
    scenario = make_scenario(assertions=[])
    observed_payload = {}

    async def fake_agent(payload):
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


def test_python_async_callable_accepts_trace_return():
    scenario = make_scenario(assertions=[])

    expected_trace = Trace(
        messages=[{"role": "assistant", "content": "ok"}],
        tool_calls=[],
        events=[],
    )

    async def fake_agent(payload):
        return expected_trace

    trace = run_python_callable_target(scenario, fake_agent)

    assert trace is expected_trace


def test_python_async_callable_accepts_trace_shaped_dict_return():
    scenario = make_scenario(assertions=[])

    async def fake_agent(payload):
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


def test_python_async_callable_wraps_exception_in_adapter_error():
    scenario = make_scenario(assertions=[])

    async def broken_agent(payload):
        raise RuntimeError("boom")

    with pytest.raises(AdapterError, match="Python callable raised an exception"):
        run_python_callable_target(scenario, broken_agent)


def test_python_async_callable_object():
    """A callable object with async __call__ should work."""
    scenario = make_scenario(assertions=[])

    class AsyncAgent:
        async def __call__(self, payload):
            return {"messages": [], "tool_calls": [], "events": []}

    trace = run_python_callable_target(scenario, AsyncAgent())
    assert isinstance(trace, Trace)


def test_python_sync_wrapper_returning_awaitable():
    """A sync function returning a coroutine should work."""
    scenario = make_scenario(assertions=[])

    async def _inner(payload):
        return {"messages": [], "tool_calls": [], "events": []}

    def sync_wrapper(payload):
        return _inner(payload)

    trace = run_python_callable_target(scenario, sync_wrapper)
    assert isinstance(trace, Trace)


def test_python_async_callable_from_running_event_loop():
    """Calling run_python_callable_target from a running event loop should work."""
    import asyncio

    scenario = make_scenario(assertions=[])

    async def fake_agent(payload):
        return {"messages": [], "tool_calls": [], "events": []}

    async def run_from_loop():
        return run_python_callable_target(scenario, fake_agent)

    trace = asyncio.run(run_from_loop())
    assert isinstance(trace, Trace)


@patch("urllib.request.urlopen")
def test_run_http_target_respects_timeout(mock_urlopen):
    """The timeout argument is forwarded to the underlying network call."""
    scenario = make_scenario(assertions=[])

    mock_response = MagicMock()
    mock_response.read.return_value = b'{"messages": [], "tool_calls": [], "events": []}'
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    run_http_target(scenario, "http://127.0.0.1:8000/run", timeout=45)

    _, kwargs = mock_urlopen.call_args
    assert kwargs["timeout"] == 45


@patch("urllib.request.urlopen")
def test_run_http_target_defaults_to_thirty_second_timeout(mock_urlopen):
    """Omitting the timeout falls back to the documented 30 second default."""
    scenario = make_scenario(assertions=[])

    mock_response = MagicMock()
    mock_response.read.return_value = b'{"messages": [], "tool_calls": [], "events": []}'
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    run_http_target(scenario, "http://127.0.0.1:8000/run")

    _, kwargs = mock_urlopen.call_args
    assert kwargs["timeout"] == 30


@patch("urllib.request.urlopen")
def test_run_http_target_sends_custom_headers(mock_urlopen):
    """Custom HTTP headers are sent to the target request only."""
    scenario = make_scenario(assertions=[])

    mock_response = MagicMock()
    mock_response.read.return_value = b'{"messages": [], "tool_calls": [], "events": []}'
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    run_http_target(
        scenario,
        "http://127.0.0.1:8000/run",
        headers={
            "Authorization": "Bearer test-secret",
            "X-Tenant": "local-dev",
        },
    )

    http_request = mock_urlopen.call_args.args[0]
    assert http_request.get_header("Authorization") == "Bearer test-secret"
    assert http_request.get_header("X-tenant") == "local-dev"
    assert b"test-secret" not in http_request.data


@patch("urllib.request.urlopen")
def test_run_http_target_reports_timeout_errors(mock_urlopen):
    """A socket timeout surfaces as a clear AdapterError mentioning the limit."""
    mock_urlopen.side_effect = error.URLError(TimeoutError("timed out"))

    scenario = make_scenario(assertions=[])

    with pytest.raises(AdapterError, match="timed out after 5 seconds"):
        run_http_target(scenario, "http://127.0.0.1:8000/run", timeout=5)
