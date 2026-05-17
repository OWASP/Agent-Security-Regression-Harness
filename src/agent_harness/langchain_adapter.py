"""LangChain and LangGraph adapter."""

from __future__ import annotations

import importlib
import json
from typing import Any

from agent_harness.adapters import AdapterError, build_target_payload
from agent_harness.recorder import TraceRecorder
from agent_harness.scenario import Scenario
from agent_harness.trace import Trace

LANGCHAIN_ADAPTER_ID = "langchain"
LANGCHAIN_INSTALL_MESSAGE = (
    "LangChain/LangGraph adapter dependencies are not installed. "
    'Install them with: python -m pip install "'
    'owasp-agent-security-regression-harness[langchain]"'
)


def build_langchain_input(scenario: Scenario) -> dict[str, Any]:
    """Build the state dictionary passed to a supported LangChain target."""
    payload = build_target_payload(scenario)

    try:
        user_content = json.dumps(payload, indent=2, sort_keys=True)
    except TypeError as exc:
        raise AdapterError(f"Scenario input is not JSON serializable: {exc}") from exc

    return {
        "messages": [
            {
                "role": "user",
                "content": user_content,
            }
        ]
    }


def load_langchain_target(import_path: str) -> Any:
    """Load a LangChain/LangGraph target from a module:object import path."""
    if not isinstance(import_path, str) or not import_path.strip():
        raise AdapterError("LangChain/LangGraph target import path must be non-empty")

    if ":" not in import_path:
        raise AdapterError(
            "LangChain/LangGraph target must use 'module:object' format, "
            f"got {import_path!r}"
        )

    module_name, object_name = import_path.split(":", 1)
    module_name = module_name.strip()
    object_name = object_name.strip()

    if not module_name or not object_name:
        raise AdapterError(
            "LangChain/LangGraph target must use 'module:object' format with "
            "both parts present"
        )

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if _is_missing_langchain_dependency(exc):
            raise AdapterError(LANGCHAIN_INSTALL_MESSAGE) from exc
        raise AdapterError(
            f"Could not import LangChain/LangGraph target module {module_name!r}"
        ) from exc
    except Exception as exc:
        raise AdapterError(
            f"Could not import LangChain/LangGraph target module {module_name!r}"
        ) from exc

    target: Any = module

    try:
        for attr in object_name.split("."):
            target = getattr(target, attr)
    except AttributeError as exc:
        raise AdapterError(
            f"LangChain/LangGraph target object {object_name!r} was not found "
            f"in module {module_name!r}"
        ) from exc

    if not _is_supported_target(target):
        raise AdapterError(
            "LangChain/LangGraph target must provide an invoke(input) method "
            "or be a callable runner function"
        )

    return target


def run_langchain_target(
    scenario: Scenario,
    target: Any,
    *,
    config: dict[str, Any] | None = None,
    goal_event_id: str | None = None,
) -> Trace:
    """Run a scenario against a supported LangChain/LangGraph target."""
    _validate_goal_event_id(goal_event_id)
    langchain_input = build_langchain_input(scenario)
    result = _invoke_target(target, langchain_input, config=config)

    return langchain_result_to_trace(
        scenario,
        result,
        runner_input=langchain_input,
        goal_event_id=goal_event_id,
    )


def langchain_result_to_trace(
    scenario: Scenario,
    result: Any,
    *,
    runner_input: dict[str, Any],
    goal_event_id: str | None = None,
) -> Trace:
    """Convert a LangChain/LangGraph result into a harness Trace."""
    if isinstance(result, Trace):
        return result

    _validate_goal_event_id(goal_event_id)
    recorder = TraceRecorder()
    recorder.add_message("user", _messages_user_content(runner_input))

    assistant_content = _extract_assistant_content(result)
    recorder.add_message("assistant", assistant_content)

    for tool_call in extract_langchain_tool_calls(result):
        recorder.add_tool_call(tool_call["name"], tool_call["arguments"])

    recorder.add_event("adapter", LANGCHAIN_ADAPTER_ID)
    recorder.add_event("scenario", scenario.id)

    if goal_event_id is not None:
        recorder.add_event("goal", goal_event_id)

    for event in _extract_events(result):
        _record_event(recorder, event)

    return recorder.to_trace()


def extract_langchain_tool_calls(result: Any) -> list[dict[str, Any]]:
    """Extract harness tool calls from supported LangChain output shapes."""
    tool_calls: list[dict[str, Any]] = []
    sources = [result]
    messages = _iter_messages(result)

    if not (len(messages) == 1 and messages[0] is result):
        sources.extend(messages)

    for source in sources:
        for raw_call in _raw_tool_calls(source):
            tool_call = _normalize_tool_call(raw_call)

            if tool_call is not None:
                tool_calls.append(tool_call)

    return tool_calls


def _invoke_target(
    target: Any,
    langchain_input: dict[str, Any],
    *,
    config: dict[str, Any] | None,
) -> Any:
    invoke = getattr(target, "invoke", None)

    try:
        if callable(invoke):
            if config is None:
                return invoke(langchain_input)
            return invoke(langchain_input, config=config)

        if callable(target):
            if config is None:
                return target(langchain_input)
            return target(langchain_input, config)
    except Exception as exc:
        raise AdapterError(f"LangChain/LangGraph target failed: {exc}") from exc

    raise AdapterError(
        "LangChain/LangGraph target must provide an invoke(input) method "
        "or be a callable runner function"
    )


def _is_supported_target(target: Any) -> bool:
    return callable(getattr(target, "invoke", None)) or callable(target)


def _validate_goal_event_id(goal_event_id: str | None) -> None:
    if goal_event_id is None:
        return

    if not isinstance(goal_event_id, str) or not goal_event_id.strip():
        raise AdapterError("LangChain/LangGraph goal event id must be non-empty")


def _is_missing_langchain_dependency(exc: ModuleNotFoundError) -> bool:
    missing_name = getattr(exc, "name", "") or ""
    dependency_names = ("langchain", "langchain_core", "langgraph")

    return missing_name in dependency_names or missing_name.startswith(
        tuple(f"{dependency_name}." for dependency_name in dependency_names)
    )


def _messages_user_content(runner_input: dict[str, Any]) -> str:
    messages = runner_input.get("messages", [])

    if isinstance(messages, list) and messages:
        content = _message_content(messages[0])
        if content:
            return content

    return _stringify_content(runner_input)


def _extract_assistant_content(result: Any) -> str:
    messages = _iter_messages(result)

    for message in reversed(messages):
        if _message_role(message) == "assistant":
            return _message_content(message)

    if isinstance(result, str):
        return result

    for field_name in ("output", "answer", "final_output", "response"):
        value = _field(result, field_name)

        if value is not None:
            return _stringify_content(value)

    return _stringify_content(result)


def _iter_messages(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value

    messages = _field(value, "messages")
    if isinstance(messages, list):
        return messages

    if _looks_like_message(value):
        return [value]

    return []


def _looks_like_message(value: Any) -> bool:
    if isinstance(value, dict):
        return "content" in value or "role" in value or "type" in value

    return hasattr(value, "content") or hasattr(value, "tool_calls")


def _message_role(message: Any) -> str | None:
    raw_role = _field(message, "role")

    if raw_role is None:
        raw_role = _field(message, "type")

    if isinstance(raw_role, str):
        role = raw_role.lower().strip()

        if role in {"user", "human"}:
            return "user"

        if role in {"assistant", "ai"}:
            return "assistant"

        return role or None

    class_name = type(message).__name__.lower()

    if class_name.startswith("human"):
        return "user"

    if class_name.startswith("ai"):
        return "assistant"

    return None


def _message_content(message: Any) -> str:
    content = _field(message, "content")

    if content is None:
        return ""

    return _stringify_content(content)


def _raw_tool_calls(source: Any) -> list[Any]:
    raw_calls = _field(source, "tool_calls")

    if isinstance(raw_calls, list):
        return raw_calls

    additional_kwargs = _field(source, "additional_kwargs")
    if isinstance(additional_kwargs, dict):
        raw_additional_calls = additional_kwargs.get("tool_calls")

        if isinstance(raw_additional_calls, list):
            return raw_additional_calls

    return []


def _normalize_tool_call(raw_call: Any) -> dict[str, Any] | None:
    function = _field(raw_call, "function", {})
    name = (
        _field(raw_call, "name")
        or _field(raw_call, "tool")
        or _field(raw_call, "tool_name")
        or _field(function, "name")
    )

    if not isinstance(name, str) or not name.strip():
        return None

    arguments = (
        _field(raw_call, "args")
        if _field(raw_call, "args") is not None
        else _field(raw_call, "arguments")
    )

    if arguments is None:
        arguments = _field(function, "arguments")

    return {
        "name": name.strip(),
        "arguments": _parse_tool_arguments(arguments),
    }


def _parse_tool_arguments(arguments: Any) -> dict[str, Any]:
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


def _extract_events(result: Any) -> list[dict[str, Any]]:
    events = _field(result, "events")

    if events is None:
        return []

    if not isinstance(events, list):
        raise AdapterError("LangChain/LangGraph result field events must be a list")

    normalized_events = []

    for event in events:
        if not isinstance(event, dict):
            raise AdapterError("LangChain/LangGraph result events must be objects")
        normalized_events.append(event)

    return normalized_events


def _record_event(recorder: TraceRecorder, event: dict[str, Any]) -> None:
    event_type = event.get("type")

    if not isinstance(event_type, str) or not event_type.strip():
        raise AdapterError("LangChain/LangGraph result event type must be non-empty")

    fields = dict(event)
    fields.pop("type", None)
    event_id = fields.pop("id", None)

    if event_id is not None and (
        not isinstance(event_id, str) or not event_id.strip()
    ):
        raise AdapterError("LangChain/LangGraph result event id must be non-empty")

    recorder.add_event(event_type, event_id, **fields)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)

    return getattr(value, name, default)


def _stringify_content(value: Any) -> str:
    if isinstance(value, str):
        return value

    try:
        return json.dumps(value, indent=2, sort_keys=True)
    except TypeError:
        return str(value)
