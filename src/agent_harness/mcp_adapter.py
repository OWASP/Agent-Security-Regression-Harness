"""MCP workflow adapter.

This MVP adapter does not act as a full MCP host. It runs a local Python
callable that represents an MCP-integrated workflow, then translates observed
MCP tool calls into the harness Trace format.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from agent_harness.adapters import AdapterError, build_target_payload
from agent_harness.scenario import Scenario
from agent_harness.trace import Trace, TraceValidationError

MCP_ADAPTER_ID = "mcp"
MCP_TOOL_NAME_PREFIX = "mcp"
MCP_RESOURCES_READ_METHOD = "resources/read"
MCP_PROMPTS_GET_METHOD = "prompts/get"
MCP_TOOLS_CALL_METHOD = "tools/call"

MCPWorkflowTarget = Callable[[dict[str, Any]], Trace | dict[str, Any]]

MCP_EVENT_TYPES = frozenset(
    {
        "mcp_connection_initialized",
        "mcp_capabilities_negotiated",
        "mcp_tools_discovered",
        "mcp_resource_read",
        "mcp_prompt_get",
        "mcp_tool_result",
        "mcp_client_request",
        "mcp_policy_decision",
        "mcp_connection_closed",
    }
)
MCP_EVENT_DEFAULT_METHODS = {
    "mcp_resource_read": MCP_RESOURCES_READ_METHOD,
    "mcp_prompt_get": MCP_PROMPTS_GET_METHOD,
    "mcp_tool_result": MCP_TOOLS_CALL_METHOD,
}
MCP_SERVER_SCOPED_EVENT_TYPES = MCP_EVENT_TYPES


def build_mcp_input(scenario: Scenario) -> dict[str, Any]:
    """Build the payload passed to an MCP workflow target."""
    return build_target_payload(scenario)


def canonical_mcp_tool_name(server_id: str, tool_name: str) -> str:
    """Build the canonical harness tool name for an MCP tool call."""
    normalized_server_id = _normalize_name_part(server_id, "MCP server id")
    normalized_tool_name = _normalize_name_part(tool_name, "MCP tool name")

    return f"{MCP_TOOL_NAME_PREFIX}/{normalized_server_id}/{normalized_tool_name}"


def translate_mcp_tool_call(
    call: dict[str, Any],
    *,
    server_registry: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Translate one MCP tool call observation into a harness tool call."""
    if not isinstance(call, dict):
        raise AdapterError("MCP tool call must be an object")

    registry = server_registry or {}
    method = _optional_string(
        call.get("mcp_method") or call.get("method"),
        default=MCP_TOOLS_CALL_METHOD,
    )

    params = call.get("params", {})
    if params is None:
        params = {}

    if not isinstance(params, dict):
        raise AdapterError("MCP tool call params must be an object when provided")

    server_id = _extract_server_id(call)
    tool_name = _extract_tool_name(call, params)

    if tool_name.startswith(f"{MCP_TOOL_NAME_PREFIX}/") and server_id is None:
        server_id, tool_name = _split_canonical_tool_name(tool_name)

    if server_id is None:
        raise AdapterError("MCP tool call is missing server_id")

    server_id = _normalize_name_part(server_id, "MCP server id")
    tool_name = _normalize_name_part(tool_name, "MCP tool name")

    arguments = (
        call["arguments"]
        if "arguments" in call
        else params.get("arguments")
    )

    translated = {
        "name": canonical_mcp_tool_name(server_id, tool_name),
        "arguments": _normalize_arguments(arguments),
        "mcp_server_id": server_id,
        "mcp_tool_name": tool_name,
        "mcp_method": method,
    }

    translated.update(_source_metadata(call, registry.get(server_id, {})))
    return translated


def normalize_mcp_event(
    event: dict[str, Any],
    *,
    server_registry: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Normalize one MCP lifecycle observation into a harness trace event."""
    if not isinstance(event, dict):
        raise AdapterError("MCP event must be an object")

    event_type = _required_string(
        event.get("type") or event.get("mcp_event_type"),
        "MCP event type",
    )

    if event_type not in MCP_EVENT_TYPES:
        raise AdapterError(f"Unsupported MCP event type: {event_type}")

    registry = server_registry or {}
    params = event.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise AdapterError("MCP event params must be an object when provided")

    server_id = _extract_server_id(event)
    tool_name = None

    if event_type == "mcp_tool_result":
        tool_name = _extract_tool_name(event, params)
        if tool_name.startswith(f"{MCP_TOOL_NAME_PREFIX}/"):
            canonical_server_id, tool_name = _split_canonical_tool_name(tool_name)
            if server_id is None:
                server_id = canonical_server_id
            elif _normalize_name_part(server_id, "MCP server id") != canonical_server_id:
                raise AdapterError(
                    "MCP tool result canonical name does not match server_id"
                )

    if event_type in MCP_SERVER_SCOPED_EVENT_TYPES:
        if server_id is None:
            raise AdapterError(f"{event_type} event is missing server_id")
        server_id = _normalize_name_part(server_id, "MCP server id")

    normalized = deepcopy(event)
    normalized["type"] = event_type
    normalized.pop("mcp_event_type", None)

    if server_id is not None:
        normalized["server_id"] = server_id
        normalized.pop("mcp_server_id", None)
        _add_event_source_metadata(normalized, event, registry.get(server_id, {}))

    if event_type == "mcp_resource_read":
        normalized["uri"] = _required_string(
            event.get("uri") or event.get("resource_uri"),
            "MCP resource URI",
        )
        normalized["mcp_method"] = _optional_string(
            event.get("mcp_method") or event.get("method"),
            default=MCP_EVENT_DEFAULT_METHODS[event_type],
        )
    elif event_type == "mcp_prompt_get":
        prompt_name = (
            event.get("mcp_prompt_name")
            or event.get("prompt_name")
            or params.get("name")
            or event.get("name")
        )
        normalized["mcp_prompt_name"] = _normalize_name_part(
            prompt_name,
            "MCP prompt name",
        )
        normalized["mcp_method"] = _optional_string(
            event.get("mcp_method") or event.get("method"),
            default=MCP_EVENT_DEFAULT_METHODS[event_type],
        )
    elif event_type == "mcp_tool_result":
        assert tool_name is not None
        assert server_id is not None
        tool_name = _normalize_name_part(tool_name, "MCP tool name")
        normalized["mcp_tool_name"] = tool_name
        normalized["name"] = canonical_mcp_tool_name(server_id, tool_name)
        normalized["mcp_method"] = _optional_string(
            event.get("mcp_method") or event.get("method"),
            default=MCP_EVENT_DEFAULT_METHODS[event_type],
        )
    elif event_type == "mcp_policy_decision":
        normalized["decision"] = _required_string(
            event.get("decision"),
            "MCP policy decision",
        )

    return normalized


def normalize_mcp_events(
    events: Any,
    *,
    server_registry: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Normalize MCP lifecycle observations from an MCP workflow result."""
    if events is None:
        return []

    if not isinstance(events, list):
        raise AdapterError("MCP workflow field mcp_events must be a list")

    return [
        normalize_mcp_event(event, server_registry=server_registry)
        for event in events
    ]


def mcp_workflow_result_to_trace(
    scenario: Scenario,
    result: Trace | dict[str, Any],
    *,
    default_user_message: str | None = None,
) -> Trace:
    """Convert an MCP workflow result into a harness Trace."""
    if isinstance(result, Trace):
        return result

    if not isinstance(result, dict):
        raise AdapterError(
            "MCP target must return a Trace or MCP workflow dictionary; "
            f"got {type(result).__name__}"
        )

    if _is_plain_trace_result(result):
        return _trace_from_dict(result, "MCP target returned invalid trace")

    server_registry = _build_server_registry(result.get("mcp_servers", []))
    messages = _normalize_messages(result.get("messages", []))

    if not messages and default_user_message is not None:
        messages.append(
            {
                "role": "user",
                "content": default_user_message,
            }
        )

    assistant_content = result.get("assistant_message")
    if assistant_content is None:
        assistant_content = result.get("final_output")

    if assistant_content is not None:
        messages.append(
            {
                "role": "assistant",
                "content": _stringify_content(assistant_content),
            }
        )

    tool_calls = _normalize_existing_tool_calls(result.get("tool_calls", []))

    raw_mcp_tool_calls = result.get("mcp_tool_calls", [])
    if not isinstance(raw_mcp_tool_calls, list):
        raise AdapterError("MCP workflow field mcp_tool_calls must be a list")

    for call in raw_mcp_tool_calls:
        tool_calls.append(
            translate_mcp_tool_call(
                call,
                server_registry=server_registry,
            )
        )

    events = [
        {
            "type": "adapter",
            "id": MCP_ADAPTER_ID,
        },
        {
            "type": "scenario",
            "id": scenario.id,
        },
    ]
    events.extend(
        normalize_mcp_events(
            result.get("mcp_events", []),
            server_registry=server_registry,
        )
    )
    events.extend(_normalize_events(result.get("events", [])))

    return _trace_from_dict(
        {
            "messages": messages,
            "tool_calls": tool_calls,
            "events": events,
        },
        "MCP workflow produced invalid trace",
    )


def run_mcp_target(
    scenario: Scenario,
    mcp_target: MCPWorkflowTarget,
) -> Trace:
    """Run a scenario against a local MCP-integrated workflow target."""
    payload = build_mcp_input(scenario)

    try:
        result = mcp_target(payload)
    except Exception as exc:
        raise AdapterError(f"MCP target raised an exception: {exc}") from exc

    return mcp_workflow_result_to_trace(
        scenario,
        result,
        default_user_message=_build_default_user_message(payload),
    )


def _normalize_name_part(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AdapterError(f"{field_name} must be a non-empty string")

    normalized = value.strip()

    if "/" in normalized:
        raise AdapterError(f"{field_name} must not contain '/'")

    return normalized


def _optional_string(value: Any, *, default: str) -> str:
    if value is None:
        return default

    if not isinstance(value, str) or not value.strip():
        raise AdapterError("MCP method must be a non-empty string")

    return value.strip()


def _required_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AdapterError(f"{field_name} must be a non-empty string")

    return value.strip()


def _extract_server_id(call: dict[str, Any]) -> str | None:
    server_id = call.get("mcp_server_id") or call.get("server_id")

    if server_id is not None:
        return server_id

    server = call.get("server")
    if isinstance(server, dict):
        nested_server_id = (
            server.get("id")
            or server.get("server_id")
            or server.get("mcp_server_id")
        )

        if nested_server_id is not None:
            return nested_server_id

    return None


def _extract_tool_name(call: dict[str, Any], params: dict[str, Any]) -> str:
    tool_name = (
        call.get("mcp_tool_name")
        or call.get("tool_name")
        or params.get("name")
        or call.get("name")
    )

    if not isinstance(tool_name, str) or not tool_name.strip():
        raise AdapterError("MCP tool call is missing tool_name")

    return tool_name.strip()


def _split_canonical_tool_name(name: str) -> tuple[str, str]:
    parts = name.split("/", 2)

    if len(parts) != 3 or parts[0] != MCP_TOOL_NAME_PREFIX:
        raise AdapterError(f"Invalid canonical MCP tool name: {name!r}")

    return parts[1], parts[2]


def _normalize_arguments(arguments: Any) -> dict[str, Any]:
    if arguments is None:
        return {}

    if isinstance(arguments, dict):
        return deepcopy(arguments)

    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            return {"raw": arguments}

        if isinstance(parsed, dict):
            return parsed

        return {"raw": parsed}

    return {"raw": deepcopy(arguments)}


def _source_metadata(
    call: dict[str, Any],
    registered_server: dict[str, Any],
) -> dict[str, Any]:
    server = call.get("server")
    if not isinstance(server, dict):
        server = {}

    metadata: dict[str, Any] = {}
    field_map = {
        "trust": (("trust",), ("trust",)),
        "mcp_transport": (
            ("mcp_transport", "transport"),
            ("mcp_transport", "transport"),
        ),
        "mcp_server_name": (
            ("mcp_server_name", "server_name"),
            ("mcp_server_name", "server_name", "name"),
        ),
        "mcp_server_title": (
            ("mcp_server_title", "server_title"),
            ("mcp_server_title", "server_title", "title"),
        ),
        "mcp_server_version": (
            ("mcp_server_version", "server_version"),
            ("mcp_server_version", "server_version", "version"),
        ),
    }

    for output_field, (call_fields, server_fields) in field_map.items():
        value = (
            _first_present(call, call_fields)
            or _first_present(server, server_fields)
            or _first_present(registered_server, server_fields)
        )
        if isinstance(value, str) and value.strip():
            metadata[output_field] = value.strip()

    return metadata


def _add_event_source_metadata(
    event: dict[str, Any],
    raw_event: dict[str, Any],
    registered_server: dict[str, Any],
) -> None:
    server = raw_event.get("server")
    if not isinstance(server, dict):
        server = {}

    field_map = {
        "trust": (("trust",), ("trust",)),
        "transport": (
            ("transport", "mcp_transport"),
            ("transport", "mcp_transport"),
        ),
        "server_name": (
            ("server_name", "mcp_server_name"),
            ("server_name", "mcp_server_name", "name"),
        ),
        "server_title": (
            ("server_title", "mcp_server_title"),
            ("server_title", "mcp_server_title", "title"),
        ),
        "server_version": (
            ("server_version", "mcp_server_version"),
            ("server_version", "mcp_server_version", "version"),
        ),
        "protocol_version": (
            ("protocol_version",),
            ("protocol_version",),
        ),
    }

    for output_field, (event_fields, server_fields) in field_map.items():
        if output_field in event:
            continue

        value = (
            _first_present(raw_event, event_fields)
            or _first_present(server, server_fields)
            or _first_present(registered_server, server_fields)
        )
        if isinstance(value, str) and value.strip():
            event[output_field] = value.strip()


def _first_present(
    source: dict[str, Any],
    fields: tuple[str, ...],
) -> Any:
    for field in fields:
        if field in source:
            return source[field]

    return None


def _build_server_registry(value: Any) -> dict[str, dict[str, Any]]:
    if value is None:
        return {}

    if not isinstance(value, list):
        raise AdapterError("MCP workflow field mcp_servers must be a list")

    registry: dict[str, dict[str, Any]] = {}

    for index, server in enumerate(value):
        if not isinstance(server, dict):
            raise AdapterError(f"MCP server entry {index} must be an object")

        raw_server_id = (
            server.get("id")
            or server.get("server_id")
            or server.get("mcp_server_id")
        )
        server_id = _normalize_name_part(raw_server_id, "MCP server id")

        if server_id in registry:
            raise AdapterError(f"Duplicate MCP server id: {server_id}")

        registry[server_id] = deepcopy(server)

    return registry


def _normalize_messages(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []

    if not isinstance(value, list):
        raise AdapterError("MCP workflow field messages must be a list")

    return deepcopy(value)


def _normalize_existing_tool_calls(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []

    if not isinstance(value, list):
        raise AdapterError("MCP workflow field tool_calls must be a list")

    return deepcopy(value)


def _normalize_events(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []

    if not isinstance(value, list):
        raise AdapterError("MCP workflow field events must be a list")

    return deepcopy(value)


def _stringify_content(value: Any) -> str:
    if isinstance(value, str):
        return value

    return str(value)


def _is_plain_trace_result(result: dict[str, Any]) -> bool:
    mcp_fields = {
        "mcp_tool_calls",
        "mcp_events",
        "mcp_servers",
        "assistant_message",
        "final_output",
    }

    if set(result).isdisjoint(mcp_fields):
        return {"messages", "tool_calls", "events"} <= set(result)

    return False


def _trace_from_dict(trace_data: dict[str, Any], error_prefix: str) -> Trace:
    try:
        return Trace.from_dict(trace_data)
    except TraceValidationError as exc:
        raise AdapterError(f"{error_prefix}: {exc}") from exc


def _build_default_user_message(payload: dict[str, Any]) -> str:
    try:
        return json.dumps(payload, indent=2, sort_keys=True)
    except TypeError as exc:
        raise AdapterError(f"Scenario input is not JSON serializable: {exc}") from exc
