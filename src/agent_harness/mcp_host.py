"""Minimal MCP host execution support.

This module owns the execution path that starts configured MCP servers and
passes a host context to a deterministic local target. The target can call real
MCP tools through ``MCPHostContext`` without involving an LLM.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from copy import deepcopy
from dataclasses import dataclass
import importlib
import inspect
import json
import threading
from typing import Any

from agent_harness.adapters import AdapterError
from agent_harness.mcp_adapter import (
    build_mcp_input,
    canonical_mcp_tool_name,
    mcp_workflow_result_to_trace,
)
from agent_harness.mcp_runtime import (
    MCPRuntimeConfig,
    MCPServerConfig,
    ensure_mcp_sdk_available,
)
from agent_harness.scenario import Scenario
from agent_harness.trace import Trace


MCPHostTargetResult = Trace | dict[str, Any]
MCPHostTarget = Callable[
    [dict[str, Any], "MCPHostContext"],
    MCPHostTargetResult | Awaitable[MCPHostTargetResult],
]

DEFAULT_RESULT_CONTENT_LIMIT = 4096
MAX_ERROR_MESSAGE_LENGTH = 512
MAX_STRING_LENGTH = 2048
MAX_COLLECTION_ITEMS = 50
MAX_JSON_DEPTH = 6
MAX_TOOL_SCHEMA_LENGTH = 4096
_HOST_OWNED_MCP_FIELDS = frozenset(
    {
        "mcp_servers",
        "mcp_tool_calls",
        "mcp_events",
    }
)


@dataclass(frozen=True)
class MCPHostExecutionResult:
    """Result of a deterministic MCP host execution."""

    trace: Trace
    target_result: MCPHostTargetResult
    workflow_result: dict[str, Any]
    mcp_servers: tuple[dict[str, Any], ...]
    mcp_tool_calls: tuple[dict[str, Any], ...]
    mcp_events: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class _MCPSDK:
    ClientSession: Any
    StdioServerParameters: Any
    stdio_client: Any


@dataclass
class _MCPConnection:
    config: MCPServerConfig
    session: Any
    metadata: dict[str, Any]
    tool_names: frozenset[str]


class MCPHostContext:
    """Host object passed to MCP targets so they can call configured tools."""

    def __init__(
        self,
        connections: dict[str, _MCPConnection],
        *,
        loop: asyncio.AbstractEventLoop,
        loop_thread_id: int,
        result_content_limit: int = DEFAULT_RESULT_CONTENT_LIMIT,
    ) -> None:
        self._connections = connections
        self._loop = loop
        self._loop_thread_id = loop_thread_id
        self._result_content_limit = result_content_limit
        self._mcp_tool_calls: list[dict[str, Any]] = []
        self._mcp_events: list[dict[str, Any]] = []
        self._closed = False

    @property
    def server_ids(self) -> tuple[str, ...]:
        """Return configured MCP server ids."""
        return tuple(self._connections)

    def call_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Synchronously call an MCP tool through the host.

        Synchronous targets are executed in a worker thread by
        ``async_run_mcp_host_target``. Calling this method from an async target
        would deadlock, so async targets should use ``await async_call_tool``.
        """
        if threading.get_ident() == self._loop_thread_id:
            raise AdapterError(
                "MCPHostContext.call_tool cannot be used from an async target; "
                "use await host.async_call_tool(...) instead"
            )

        future = asyncio.run_coroutine_threadsafe(
            self.async_call_tool(server_id, tool_name, arguments),
            self._loop,
        )

        try:
            return future.result()
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(
                f"MCP tool call failed: {_safe_error_message(exc)}"
            ) from exc

    async def async_call_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Asynchronously call an MCP tool through the host."""
        if self._closed:
            raise AdapterError("MCP host context is closed")

        normalized_server_id, normalized_tool_name = _validate_tool_call_parts(
            server_id,
            tool_name,
        )
        normalized_arguments = _normalize_tool_arguments(arguments)
        connection = self._connections.get(normalized_server_id)

        if connection is None:
            raise AdapterError(
                f"MCP server id is not configured: {normalized_server_id}"
            )

        if normalized_tool_name not in connection.tool_names:
            raise AdapterError(
                f"MCP tool is not advertised by server {normalized_server_id}: "
                f"{normalized_tool_name}"
            )

        canonical_tool_name = canonical_mcp_tool_name(
            normalized_server_id,
            normalized_tool_name,
        )
        self._mcp_tool_calls.append(
            {
                "name": canonical_tool_name,
                "server_id": normalized_server_id,
                "tool_name": normalized_tool_name,
                "arguments": deepcopy(normalized_arguments),
            }
        )

        try:
            result = await asyncio.wait_for(
                connection.session.call_tool(
                    normalized_tool_name,
                    arguments=normalized_arguments,
                ),
                timeout=connection.config.timeout_seconds,
            )
        except Exception as exc:
            self._mcp_events.append(
                {
                    "type": "mcp_tool_result",
                    "name": canonical_tool_name,
                    "server_id": normalized_server_id,
                    "tool_name": normalized_tool_name,
                    "is_error": True,
                    "error": _safe_error_message(exc),
                }
            )
            raise AdapterError(
                f"MCP tool call failed for {canonical_tool_name}: "
                f"{_safe_error_message(exc)}"
            ) from exc

        event = {
            "type": "mcp_tool_result",
            "name": canonical_tool_name,
            "server_id": normalized_server_id,
            "tool_name": normalized_tool_name,
        }
        event.update(
            _tool_result_event_fields(
                result,
                content_limit=self._result_content_limit,
            )
        )
        self._mcp_events.append(event)

        return result

    def _record_event(self, event: dict[str, Any]) -> None:
        self._mcp_events.append(deepcopy(event))

    def _close(self) -> None:
        self._closed = True

    def _snapshot_tool_calls(self) -> tuple[dict[str, Any], ...]:
        return tuple(deepcopy(self._mcp_tool_calls))

    def _snapshot_events(self) -> tuple[dict[str, Any], ...]:
        return tuple(deepcopy(self._mcp_events))


def run_mcp_host_target(
    scenario: Scenario,
    mcp_target: MCPHostTarget,
    runtime_config: MCPRuntimeConfig,
    *,
    result_content_limit: int = DEFAULT_RESULT_CONTENT_LIMIT,
    sdk_loader: Callable[[], _MCPSDK] | None = None,
) -> MCPHostExecutionResult:
    """Run a scenario against a deterministic target with real MCP tools."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            async_run_mcp_host_target(
                scenario,
                mcp_target,
                runtime_config,
                result_content_limit=result_content_limit,
                sdk_loader=sdk_loader,
            )
        )

    raise AdapterError(
        "run_mcp_host_target cannot be called from an active event loop; "
        "use await async_run_mcp_host_target(...) instead"
    )


async def async_run_mcp_host_target(
    scenario: Scenario,
    mcp_target: MCPHostTarget,
    runtime_config: MCPRuntimeConfig,
    *,
    result_content_limit: int = DEFAULT_RESULT_CONTENT_LIMIT,
    sdk_loader: Callable[[], _MCPSDK] | None = None,
) -> MCPHostExecutionResult:
    """Async implementation for deterministic MCP host target execution."""
    _validate_required_servers(scenario, runtime_config)
    _validate_result_content_limit(result_content_limit)

    sdk = sdk_loader() if sdk_loader is not None else _load_mcp_sdk()
    payload = build_mcp_input(scenario)
    connections: dict[str, _MCPConnection] = {}

    async with AsyncExitStack() as stack:
        initial_events: list[dict[str, Any]] = []

        for server_config in runtime_config.servers:
            connection, events = await _connect_stdio_server(
                server_config,
                sdk,
                stack,
            )
            connections[server_config.id] = connection
            initial_events.extend(events)

        loop = asyncio.get_running_loop()
        context = MCPHostContext(
            connections,
            loop=loop,
            loop_thread_id=threading.get_ident(),
            result_content_limit=result_content_limit,
        )

        for event in initial_events:
            context._record_event(event)

        try:
            target_result = await _invoke_mcp_host_target(
                mcp_target,
                payload,
                context,
            )
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(
                "MCP host target raised an exception: "
                f"{_safe_error_message(exc)}"
            ) from exc
        finally:
            context._close()

        mcp_servers = tuple(deepcopy(connection.metadata) for connection in connections.values())
        mcp_tool_calls = context._snapshot_tool_calls()
        mcp_events = context._snapshot_events()

    mcp_events = (
        *mcp_events,
        *(_connection_closed_event(connection) for connection in connections.values()),
    )
    workflow_result = _build_workflow_result(
        target_result,
        mcp_servers=mcp_servers,
        mcp_tool_calls=mcp_tool_calls,
        mcp_events=mcp_events,
    )
    trace = mcp_workflow_result_to_trace(
        scenario,
        workflow_result,
        default_user_message=_build_default_user_message(payload),
    )

    return MCPHostExecutionResult(
        trace=trace,
        target_result=target_result,
        workflow_result=workflow_result,
        mcp_servers=mcp_servers,
        mcp_tool_calls=mcp_tool_calls,
        mcp_events=mcp_events,
    )


async def _connect_stdio_server(
    server_config: MCPServerConfig,
    sdk: _MCPSDK,
    stack: AsyncExitStack,
) -> tuple[_MCPConnection, list[dict[str, Any]]]:
    if server_config.transport != "stdio":
        raise AdapterError(
            f"MCP server {server_config.id} uses unsupported transport: "
            f"{server_config.transport}"
        )

    try:
        server_params = _stdio_server_parameters(server_config, sdk)
        read_stream, write_stream = await _open_stdio_transport(
            server_config,
            sdk,
            stack,
            server_params,
        )
        session = await _open_client_session(
            server_config,
            sdk,
            stack,
            read_stream,
            write_stream,
        )
        initialize_result, tools_result = await _initialize_session(
            server_config,
            session,
        )
    except AdapterError:
        raise
    except Exception as exc:
        raise AdapterError(
            "Could not initialize MCP server "
            f"{server_config.id}: {_safe_error_message(exc)}"
        ) from exc

    metadata = _server_metadata(server_config, initialize_result)
    tool_names = _tool_names_from_list_tools_result(tools_result)
    events = [
        _connection_initialized_event(server_config, initialize_result),
        _tools_discovered_event(server_config, tools_result),
    ]

    return _MCPConnection(server_config, session, metadata, tool_names), events


def _stdio_server_parameters(server_config: MCPServerConfig, sdk: _MCPSDK) -> Any:
    kwargs: dict[str, Any] = {
        "command": server_config.command,
        "args": list(server_config.args),
        "env": dict(server_config.env),
    }

    if server_config.cwd is not None:
        if not _callable_accepts_keyword(sdk.StdioServerParameters, "cwd"):
            raise AdapterError(
                "MCP SDK StdioServerParameters does not support cwd; "
                f"server {server_config.id} configured cwd={server_config.cwd}"
            )
        kwargs["cwd"] = str(server_config.cwd)

    return sdk.StdioServerParameters(**kwargs)


async def _open_stdio_transport(
    server_config: MCPServerConfig,
    sdk: _MCPSDK,
    stack: AsyncExitStack,
    server_params: Any,
) -> tuple[Any, Any]:
    return await _wait_for_mcp_startup_step(
        stack.enter_async_context(sdk.stdio_client(server_params)),
        timeout_seconds=server_config.timeout_seconds,
        server_id=server_config.id,
        operation="open stdio transport",
    )


async def _open_client_session(
    server_config: MCPServerConfig,
    sdk: _MCPSDK,
    stack: AsyncExitStack,
    read_stream: Any,
    write_stream: Any,
) -> Any:
    return await _wait_for_mcp_startup_step(
        stack.enter_async_context(sdk.ClientSession(read_stream, write_stream)),
        timeout_seconds=server_config.timeout_seconds,
        server_id=server_config.id,
        operation="open client session",
    )


async def _initialize_session(
    server_config: MCPServerConfig,
    session: Any,
) -> tuple[Any, Any]:
    initialize_result = await _wait_for_mcp_startup_step(
        session.initialize(),
        timeout_seconds=server_config.timeout_seconds,
        server_id=server_config.id,
        operation="initialize session",
    )
    tools_result = await _wait_for_mcp_startup_step(
        session.list_tools(),
        timeout_seconds=server_config.timeout_seconds,
        server_id=server_config.id,
        operation="list tools",
    )
    return initialize_result, tools_result


async def _wait_for_mcp_startup_step(
    awaitable: Awaitable[Any],
    *,
    timeout_seconds: float,
    server_id: str,
    operation: str,
) -> Any:
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout_seconds)
    except TimeoutError as exc:
        raise AdapterError(
            f"Timed out while trying to {operation} for MCP server {server_id}"
        ) from exc


def _callable_accepts_keyword(callable_object: Any, keyword: str) -> bool:
    try:
        signature = inspect.signature(callable_object)
    except (TypeError, ValueError):
        return True

    return keyword in signature.parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )


async def _invoke_mcp_host_target(
    mcp_target: MCPHostTarget,
    payload: dict[str, Any],
    context: MCPHostContext,
) -> MCPHostTargetResult:
    if not callable(mcp_target):
        raise AdapterError("MCP host target must be callable")

    if inspect.iscoroutinefunction(mcp_target):
        result = mcp_target(payload, context)
    else:
        result = await asyncio.to_thread(mcp_target, payload, context)

    if inspect.isawaitable(result):
        result = await result

    if isinstance(result, Trace):
        return result

    if not isinstance(result, dict):
        raise AdapterError(
            "MCP host target must return a Trace or MCP workflow dictionary; "
            f"got {type(result).__name__}"
        )

    return result


def _load_mcp_sdk(
    import_module: Callable[[str], Any] = importlib.import_module,
) -> _MCPSDK:
    ensure_mcp_sdk_available(import_module=import_module)

    mcp_module = import_module("mcp")
    stdio_module = import_module("mcp.client.stdio")

    client_session = getattr(mcp_module, "ClientSession", None)
    if client_session is None:
        client_session = import_module("mcp.client.session").ClientSession

    stdio_server_parameters = getattr(mcp_module, "StdioServerParameters", None)
    if stdio_server_parameters is None:
        stdio_server_parameters = getattr(stdio_module, "StdioServerParameters")

    return _MCPSDK(
        ClientSession=client_session,
        StdioServerParameters=stdio_server_parameters,
        stdio_client=stdio_module.stdio_client,
    )


def _validate_required_servers(
    scenario: Scenario,
    runtime_config: MCPRuntimeConfig,
) -> None:
    required_servers = scenario.raw.get("target", {}).get("required_servers", [])

    if required_servers is None:
        return

    if not isinstance(required_servers, list):
        raise AdapterError("MCP scenario target.required_servers must be a list")

    configured_servers = set(runtime_config.server_ids)
    missing_servers = []

    for index, server_id in enumerate(required_servers):
        if not isinstance(server_id, str) or not server_id.strip():
            raise AdapterError(
                f"MCP scenario target.required_servers[{index}] "
                "must be a non-empty string"
            )

        normalized_server_id = server_id.strip()
        if normalized_server_id not in configured_servers:
            missing_servers.append(normalized_server_id)

    if missing_servers:
        joined = ", ".join(missing_servers)
        raise AdapterError(f"MCP runtime config is missing required servers: {joined}")


def _validate_result_content_limit(result_content_limit: int) -> None:
    if isinstance(result_content_limit, bool) or not isinstance(
        result_content_limit,
        int,
    ):
        raise AdapterError("MCP host result_content_limit must be an integer")

    if result_content_limit <= 0:
        raise AdapterError("MCP host result_content_limit must be greater than zero")


def _validate_tool_call_parts(server_id: str, tool_name: str) -> tuple[str, str]:
    canonical_name = canonical_mcp_tool_name(server_id, tool_name)
    _, normalized_server_id, normalized_tool_name = canonical_name.split("/", 2)
    return normalized_server_id, normalized_tool_name


def _normalize_tool_arguments(arguments: dict[str, Any] | None) -> dict[str, Any]:
    if arguments is None:
        return {}

    if not isinstance(arguments, dict):
        raise AdapterError("MCP tool call arguments must be an object when provided")

    return deepcopy(arguments)


def _server_metadata(
    server_config: MCPServerConfig,
    initialize_result: Any,
) -> dict[str, Any]:
    metadata = {
        "id": server_config.id,
        "transport": server_config.transport,
        "command": _command_basename(server_config.command),
    }
    metadata.update(_initialize_result_metadata(initialize_result))
    return metadata


def _connection_initialized_event(
    server_config: MCPServerConfig,
    initialize_result: Any,
) -> dict[str, Any]:
    event = {
        "type": "mcp_connection_initialized",
        "id": server_config.id,
        "server_id": server_config.id,
        "transport": server_config.transport,
        "command": _command_basename(server_config.command),
    }
    event.update(_initialize_result_metadata(initialize_result))
    return event


def _connection_closed_event(connection: _MCPConnection) -> dict[str, Any]:
    return {
        "type": "mcp_connection_closed",
        "id": connection.config.id,
        "server_id": connection.config.id,
        "transport": connection.config.transport,
        "command": _command_basename(connection.config.command),
    }


def _command_basename(command: str) -> str:
    normalized = command.strip().rstrip("\\/")
    if not normalized:
        return command

    return normalized.replace("\\", "/").split("/")[-1]


def _initialize_result_metadata(initialize_result: Any) -> dict[str, Any]:
    result_data = _object_to_jsonable(initialize_result)
    if not isinstance(result_data, dict):
        return {}

    metadata: dict[str, Any] = {}
    protocol_version = _first_present(
        result_data,
        ("protocolVersion", "protocol_version"),
    )
    if isinstance(protocol_version, str) and protocol_version.strip():
        metadata["protocol_version"] = protocol_version.strip()

    server_info = _first_present(
        result_data,
        ("serverInfo", "server_info"),
    )
    if isinstance(server_info, dict):
        server_name = server_info.get("name")
        server_title = server_info.get("title")
        server_version = server_info.get("version")

        if isinstance(server_name, str) and server_name.strip():
            metadata["server_name"] = server_name.strip()
        if isinstance(server_title, str) and server_title.strip():
            metadata["server_title"] = server_title.strip()
        if isinstance(server_version, str) and server_version.strip():
            metadata["server_version"] = server_version.strip()

    capabilities = result_data.get("capabilities")
    if isinstance(capabilities, dict):
        metadata["capabilities"] = deepcopy(capabilities)

    return metadata


def _tools_discovered_event(
    server_config: MCPServerConfig,
    tools_result: Any,
) -> dict[str, Any]:
    tools_data = _object_to_jsonable(tools_result)
    tools = []
    tools_truncated = False

    if isinstance(tools_data, dict):
        raw_tools = tools_data.get("tools", [])
        if isinstance(raw_tools, list):
            tools_truncated = any(
                isinstance(tool, dict) and "truncated_items" in tool
                for tool in raw_tools
            )
            tools = [
                _tool_summary(tool)
                for tool in raw_tools
                if isinstance(tool, dict) and "name" in tool
            ]

    event = {
        "type": "mcp_tools_discovered",
        "server_id": server_config.id,
        "tools": tools,
    }

    if tools_truncated:
        event["tools_truncated"] = True

    return event


def _tool_summary(tool: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}

    for field in (
        "name",
        "title",
        "description",
        "inputSchema",
        "input_schema",
        "outputSchema",
        "output_schema",
    ):
        if field in tool:
            value = _object_to_jsonable(tool[field])
            if field in {
                "inputSchema",
                "input_schema",
                "outputSchema",
                "output_schema",
            }:
                value, truncated = _truncate_jsonable(
                    value,
                    limit=MAX_TOOL_SCHEMA_LENGTH,
                )
                if truncated:
                    summary[f"{field}_truncated"] = True
            summary[field] = deepcopy(value)

    return summary


def _tool_names_from_list_tools_result(tools_result: Any) -> frozenset[str]:
    raw_tools = _first_present_from_object(tools_result, ("tools",), default=None)
    if raw_tools is None:
        tools_data = _object_to_jsonable(tools_result)
        if not isinstance(tools_data, dict):
            return frozenset()
        raw_tools = tools_data.get("tools", [])

    if not isinstance(raw_tools, (list, tuple)):
        return frozenset()

    tool_names = []
    for tool in raw_tools:
        tool_name = _first_present_from_object(tool, ("name",), default=None)
        if isinstance(tool_name, str) and tool_name.strip():
            tool_names.append(tool_name.strip())

    return frozenset(tool_names)


def _tool_result_event_fields(
    result: Any,
    *,
    content_limit: int,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "is_error": bool(
            _first_present_from_object(
                result,
                ("isError", "is_error"),
                default=False,
            )
        )
    }

    structured_content = _first_present_from_object(
        result,
        ("structuredContent", "structured_content"),
    )
    if structured_content is not None:
        structured_jsonable = _object_to_jsonable(structured_content)
        structured_summary, structured_truncated = _truncate_jsonable(
            structured_jsonable,
            limit=content_limit,
        )
        fields["structured_content"] = structured_summary
        fields["structured_content_truncated"] = structured_truncated

    content = _first_present_from_object(result, ("content",), default=[])
    content_jsonable = _object_to_jsonable(content)
    content_summary, content_truncated = _truncate_jsonable(
        content_jsonable,
        limit=content_limit,
    )
    fields["content"] = content_summary
    fields["content_truncated"] = content_truncated

    return fields


def _build_workflow_result(
    target_result: MCPHostTargetResult,
    *,
    mcp_servers: tuple[dict[str, Any], ...],
    mcp_tool_calls: tuple[dict[str, Any], ...],
    mcp_events: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    if isinstance(target_result, Trace):
        workflow_result = target_result.to_dict()
    elif isinstance(target_result, dict):
        workflow_result = deepcopy(target_result)
        _reject_host_owned_mcp_fields(workflow_result)
    else:
        raise AdapterError(
            "MCP host target must return a Trace or MCP workflow dictionary; "
            f"got {type(target_result).__name__}"
        )

    _reject_target_mcp_trace_evidence(workflow_result)

    workflow_result["mcp_servers"] = [deepcopy(server) for server in mcp_servers]
    workflow_result["mcp_tool_calls"] = [
        deepcopy(tool_call)
        for tool_call in mcp_tool_calls
    ]
    workflow_result["mcp_events"] = [deepcopy(event) for event in mcp_events]

    return workflow_result


def _reject_host_owned_mcp_fields(workflow_result: dict[str, Any]) -> None:
    forbidden = sorted(_HOST_OWNED_MCP_FIELDS.intersection(workflow_result))
    if forbidden:
        joined = ", ".join(forbidden)
        raise AdapterError(
            "MCP host target must not return host-owned MCP evidence fields: "
            f"{joined}"
        )


def _reject_target_mcp_trace_evidence(workflow_result: dict[str, Any]) -> None:
    forbidden = []

    tool_calls = workflow_result.get("tool_calls", [])
    if "tool_calls" in workflow_result and not isinstance(tool_calls, list):
        raise AdapterError("MCP host target tool_calls must be a list")

    if isinstance(tool_calls, list) and any(
        _tool_call_contains_mcp_evidence(tool_call)
        for tool_call in tool_calls
    ):
        forbidden.append("tool_calls")

    events = workflow_result.get("events", [])
    if isinstance(events, list) and any(
        isinstance(event, dict)
        and isinstance(event.get("type"), str)
        and event["type"].startswith("mcp_")
        for event in events
    ):
        forbidden.append("events")

    if forbidden:
        joined = ", ".join(forbidden)
        raise AdapterError(
            "MCP host target must not return MCP trace evidence fields: "
            f"{joined}"
        )


def _tool_call_contains_mcp_evidence(tool_call: Any) -> bool:
    if not isinstance(tool_call, dict):
        return False

    return (
        _tool_call_contains_canonical_mcp_tool_name(tool_call)
        or _tool_call_contains_mcp_metadata_field(tool_call)
    )


def _tool_call_contains_canonical_mcp_tool_name(tool_call: Any) -> bool:
    if not isinstance(tool_call, dict):
        return False

    for field_name in ("name", "tool", "tool_name"):
        value = tool_call.get(field_name)
        if isinstance(value, str) and _is_canonical_mcp_tool_name(value.strip()):
            return True

    return False


def _tool_call_contains_mcp_metadata_field(tool_call: dict[str, Any]) -> bool:
    return any(
        isinstance(field_name, str) and field_name.startswith("mcp_")
        for field_name in tool_call
    )


def _is_canonical_mcp_tool_name(name: str) -> bool:
    try:
        server_id, tool_name = name.split("/", 2)[1:]
    except ValueError:
        return False

    try:
        return canonical_mcp_tool_name(server_id, tool_name) == name
    except AdapterError:
        return False


def _object_to_jsonable(
    value: Any,
    *,
    _depth: int = 0,
    _seen: set[int] | None = None,
) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value

    if isinstance(value, str):
        return _truncate_string(value, MAX_STRING_LENGTH)

    if _depth >= MAX_JSON_DEPTH:
        return "<max depth reached>"

    if _seen is None:
        _seen = set()

    value_id = id(value)
    if value_id in _seen:
        return "<cycle>"

    if isinstance(value, dict):
        _seen.add(value_id)
        try:
            items = list(value.items())
            normalized = {
                _truncate_string(str(key), MAX_STRING_LENGTH): _object_to_jsonable(
                    item,
                    _depth=_depth + 1,
                    _seen=_seen,
                )
                for key, item in items[:MAX_COLLECTION_ITEMS]
            }
            remaining_items = len(items) - MAX_COLLECTION_ITEMS
            if remaining_items > 0:
                normalized["truncated_items"] = remaining_items
            return normalized
        finally:
            _seen.discard(value_id)

    if isinstance(value, (list, tuple)):
        _seen.add(value_id)
        try:
            normalized_items = [
                _object_to_jsonable(
                    item,
                    _depth=_depth + 1,
                    _seen=_seen,
                )
                for item in value[:MAX_COLLECTION_ITEMS]
            ]
            remaining_items = len(value) - MAX_COLLECTION_ITEMS
            if remaining_items > 0:
                normalized_items.append({"truncated_items": remaining_items})
            return normalized_items
        finally:
            _seen.discard(value_id)

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        _seen.add(value_id)
        try:
            for kwargs in (
                {"mode": "json", "by_alias": True, "exclude_none": True},
                {"mode": "json", "exclude_none": True},
                {},
            ):
                try:
                    return _object_to_jsonable(
                        model_dump(**kwargs),
                        _depth=_depth,
                        _seen=_seen,
                    )
                except TypeError:
                    continue
        finally:
            _seen.discard(value_id)

    return _truncate_string(str(value), MAX_STRING_LENGTH)


def _truncate_jsonable(value: Any, *, limit: int) -> tuple[Any, bool]:
    try:
        serialized = json.dumps(value, sort_keys=True)
    except TypeError:
        value = _object_to_jsonable(value)
        serialized = json.dumps(value, sort_keys=True)

    if len(serialized) <= limit:
        return value, False

    return {"truncated_json": serialized[:limit]}, True


def _safe_error_message(exc: Exception) -> str:
    message = str(exc) or exc.__class__.__name__
    return _truncate_string(message, MAX_ERROR_MESSAGE_LENGTH)


def _truncate_string(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value

    return value[:limit] + "...[truncated]"


def _first_present(source: dict[str, Any], fields: tuple[str, ...]) -> Any:
    for field in fields:
        if field in source:
            return source[field]

    return None


def _first_present_from_object(
    value: Any,
    fields: tuple[str, ...],
    *,
    default: Any = None,
) -> Any:
    if isinstance(value, dict):
        for field in fields:
            if field in value:
                return value[field]
        return default

    for field in fields:
        if hasattr(value, field):
            return getattr(value, field)

    return default


def _build_default_user_message(payload: dict[str, Any]) -> str:
    try:
        return json.dumps(payload, indent=2, sort_keys=True)
    except TypeError as exc:
        raise AdapterError(f"Scenario input is not JSON serializable: {exc}") from exc
