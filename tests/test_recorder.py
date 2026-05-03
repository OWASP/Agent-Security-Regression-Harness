"""Tests for trace recording helpers."""

from __future__ import annotations

import pytest

from agent_harness.recorder import TraceRecorder
from agent_harness.trace import Trace


def test_empty_recorder_returns_empty_trace_shape():
    recorder = TraceRecorder()

    trace = recorder.to_trace()

    assert isinstance(trace, Trace)
    assert trace.to_dict() == {
        "messages": [],
        "tool_calls": [],
        "events": [],
    }


def test_add_message_strips_role_and_preserves_content():
    recorder = TraceRecorder()

    recorder.add_message(" user ", "")

    assert recorder.to_dict()["messages"] == [
        {
            "role": "user",
            "content": "",
        }
    ]


def test_add_tool_call_strips_name_and_deep_copies_arguments():
    recorder = TraceRecorder()
    arguments = {"to": "attacker@example.com"}

    recorder.add_tool_call(" send_email ", arguments)
    arguments["to"] = "changed@example.com"

    assert recorder.to_dict()["tool_calls"] == [
        {
            "name": "send_email",
            "arguments": {
                "to": "attacker@example.com",
            },
        }
    ]


def test_add_tool_call_defaults_arguments_to_empty_object():
    recorder = TraceRecorder()

    recorder.add_tool_call("send_email")

    assert recorder.to_dict()["tool_calls"] == [
        {
            "name": "send_email",
            "arguments": {},
        }
    ]


def test_add_event_strips_type_and_id_and_deep_copies_fields():
    recorder = TraceRecorder()
    source = {"trust": "untrusted"}

    recorder.add_event(" goal ", " summarize_document ", source=source)
    source["trust"] = "trusted"

    assert recorder.to_dict()["events"] == [
        {
            "type": "goal",
            "id": "summarize_document",
            "source": {
                "trust": "untrusted",
            },
        }
    ]


@pytest.mark.parametrize("role", ["", "   ", 123, None])
def test_add_message_rejects_invalid_role(role):
    recorder = TraceRecorder()

    with pytest.raises(ValueError, match="role must be a non-empty string"):
        recorder.add_message(role, "hello")  # type: ignore[arg-type]


@pytest.mark.parametrize("content", [123, None, [], {}])
def test_add_message_rejects_non_string_content(content):
    recorder = TraceRecorder()

    with pytest.raises(ValueError, match="content must be a string"):
        recorder.add_message("user", content)  # type: ignore[arg-type]


@pytest.mark.parametrize("name", ["", "   ", 123, None])
def test_add_tool_call_rejects_invalid_name(name):
    recorder = TraceRecorder()

    with pytest.raises(ValueError, match="tool name must be a non-empty string"):
        recorder.add_tool_call(name)  # type: ignore[arg-type]


@pytest.mark.parametrize("arguments", ["bad", 123, [], None])
def test_add_tool_call_rejects_non_object_arguments(arguments):
    recorder = TraceRecorder()

    if arguments is None:
        recorder.add_tool_call("send_email", arguments)
        return

    with pytest.raises(ValueError, match="tool call arguments must be an object"):
        recorder.add_tool_call("send_email", arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize("event_type", ["", "   ", 123, None])
def test_add_event_rejects_invalid_event_type(event_type):
    recorder = TraceRecorder()

    with pytest.raises(ValueError, match="event type must be a non-empty string"):
        recorder.add_event(event_type)  # type: ignore[arg-type]


@pytest.mark.parametrize("event_id", ["", "   ", 123])
def test_add_event_rejects_invalid_event_id(event_id):
    recorder = TraceRecorder()

    with pytest.raises(ValueError, match="event id must be a non-empty string"):
        recorder.add_event("goal", event_id)  # type: ignore[arg-type]