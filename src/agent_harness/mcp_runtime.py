"""Runtime configuration primitives for future full MCP host execution.

This module intentionally does not start MCP servers yet. It validates the
local runtime configuration that a future host path will use, while keeping the
MCP SDK dependency optional and lazily imported.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agent_harness.adapters import AdapterError

DEFAULT_MCP_TIMEOUT_SECONDS = 5.0
SUPPORTED_MCP_TRANSPORTS = frozenset({"stdio", "streamable_http", "sse"})
MCP_INSTALL_HINT = (
    "MCP adapter dependencies are not installed. "
    'Install them with: python -m pip install '
    '"owasp-agent-security-regression-harness[mcp]"'
)


@dataclass(frozen=True)
class MCPServerConfig:
    """Validated configuration for one MCP server connection."""

    id: str
    transport: str
    command: str | None = None
    url: str | None = None
    args: tuple[str, ...] = ()
    headers: tuple[tuple[str, str], ...] = ()
    env: tuple[tuple[str, str], ...] = ()
    cwd: Path | None = None
    timeout_seconds: float = DEFAULT_MCP_TIMEOUT_SECONDS


@dataclass(frozen=True)
class MCPRuntimeConfig:
    """Validated runtime configuration for MCP host execution."""

    servers: tuple[MCPServerConfig, ...]

    @property
    def server_ids(self) -> tuple[str, ...]:
        """Return configured server ids in declaration order."""
        return tuple(server.id for server in self.servers)

    def get_server(self, server_id: str) -> MCPServerConfig:
        """Return one server config by id."""
        normalized_server_id = _normalize_server_id(server_id, "MCP server id")

        for server in self.servers:
            if server.id == normalized_server_id:
                return server

        raise AdapterError(f"MCP server id is not configured: {normalized_server_id}")


@dataclass(frozen=True)
class MCPHostRuntime:
    """Validated shell for the future full MCP host implementation."""

    config: MCPRuntimeConfig

    def ensure_dependencies(
        self,
        import_module: Callable[[str], Any] = importlib.import_module,
    ) -> None:
        """Verify that optional MCP runtime dependencies are installed."""
        ensure_mcp_sdk_available(import_module=import_module)


def load_mcp_runtime_config(path: str | Path) -> MCPRuntimeConfig:
    """Load and validate an MCP runtime config YAML file."""
    config_path = Path(path)

    if not config_path.exists():
        raise AdapterError(f"MCP runtime config file does not exist: {config_path}")

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise AdapterError(f"MCP runtime config contains invalid YAML: {exc}") from exc

    return parse_mcp_runtime_config(data)


def parse_mcp_runtime_config(data: Any) -> MCPRuntimeConfig:
    """Validate parsed MCP runtime config data."""
    if not isinstance(data, dict):
        raise AdapterError("MCP runtime config must be a YAML mapping/object")

    server_entries = _extract_server_entries(data)
    servers: list[MCPServerConfig] = []
    seen_server_ids: set[str] = set()

    for index, entry in server_entries:
        server = _parse_server_config(index, entry)

        if server.id in seen_server_ids:
            raise AdapterError(f"Duplicate MCP server id: {server.id}")

        seen_server_ids.add(server.id)
        servers.append(server)

    if not servers:
        raise AdapterError("MCP runtime config must define at least one server")

    return MCPRuntimeConfig(servers=tuple(servers))


def ensure_mcp_sdk_available(
    import_module: Callable[[str], Any] = importlib.import_module,
) -> None:
    """Raise a clear AdapterError when the optional MCP SDK is unavailable."""
    try:
        import_module("mcp")
    except ModuleNotFoundError as exc:
        if exc.name == "mcp":
            raise AdapterError(MCP_INSTALL_HINT) from exc
        raise


def _extract_server_entries(
    data: dict[str, Any],
) -> list[tuple[int, dict[str, Any]]]:
    has_servers = "servers" in data
    has_mcp_servers = "mcp_servers" in data

    if has_servers and has_mcp_servers:
        raise AdapterError(
            "MCP runtime config must define only one of servers or mcp_servers"
        )

    if not has_servers and not has_mcp_servers:
        raise AdapterError("MCP runtime config must define servers")

    raw_servers = data["servers"] if has_servers else data["mcp_servers"]

    if not isinstance(raw_servers, list):
        raise AdapterError("MCP runtime config servers must be a list")

    entries = []
    for index, entry in enumerate(raw_servers):
        if not isinstance(entry, dict):
            raise AdapterError(f"MCP server entry {index} must be an object")
        entries.append((index, entry))

    return entries


def _parse_server_config(
    index: int,
    entry: dict[str, Any],
) -> MCPServerConfig:
    label = _server_label(index)
    server_id = _server_id_from_entry(index, entry)
    transport = _parse_transport(label, entry)
    command = _parse_stdio_command(label, entry, transport)
    url = _parse_http_url(label, entry, transport)
    headers = _parse_headers(label, entry, transport)
    args = _parse_args(label, entry)
    env = _parse_env(label, entry)
    cwd = _parse_cwd(label, entry)
    timeout_seconds = _parse_timeout_seconds(label, entry)

    return MCPServerConfig(
        id=server_id,
        transport=transport,
        command=command,
        url=url,
        args=args,
        headers=headers,
        env=env,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
    )


def _server_id_from_entry(
    index: int,
    entry: dict[str, Any],
) -> str:
    return _normalize_server_id(
        entry.get("id"),
        f"MCP server entry {index} id",
    )


def _normalize_server_id(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AdapterError(f"{field_name} must be a non-empty string")

    normalized = value.strip()

    if "/" in normalized:
        raise AdapterError(f"{field_name} must not contain '/'")

    return normalized


def _parse_transport(label: str, entry: dict[str, Any]) -> str:
    transport = entry.get("transport")

    if not isinstance(transport, str) or not transport.strip():
        raise AdapterError(f"{label} transport must be a non-empty string")

    transport = transport.strip()

    if transport not in SUPPORTED_MCP_TRANSPORTS:
        supported = ", ".join(sorted(SUPPORTED_MCP_TRANSPORTS))
        raise AdapterError(
            f"{label} transport {transport!r} is not supported; "
            f"supported transports: {supported}"
        )

    return transport


def _parse_stdio_command(
    label: str,
    entry: dict[str, Any],
    transport: str,
) -> str:
    if transport != "stdio":
        if "command" in entry:
            raise AdapterError(
                f"{label} command is only supported with the stdio transport"
            )
        return ""

    command = entry.get("command")
    if not isinstance(command, str) or not command.strip():
        raise AdapterError(f"{label} command must be a non-empty string")

    return command.strip()


def _parse_http_url(
    label: str,
    entry: dict[str, Any],
    transport: str,
) -> str:
    if transport == "stdio":
        return ""

    url = entry.get("url")
    if not isinstance(url, str) or not url.strip():
        raise AdapterError(f"{label} url must be a non-empty string")

    return url.strip()


def _parse_headers(
    label: str,
    entry: dict[str, Any],
    transport: str,
) -> tuple[tuple[str, str], ...]:
    raw_headers = entry.get("headers", {})

    if transport == "stdio":
        return () if raw_headers is None else _coerce_headers(label, raw_headers)

    if raw_headers is None:
        return ()

    return _coerce_headers(label, raw_headers)


def _coerce_headers(label: str, raw_headers: Any) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw_headers, dict):
        raise AdapterError(f"{label} headers must be an object")

    normalized_headers = []
    for key, value in raw_headers.items():
        if not isinstance(key, str) or not key.strip():
            raise AdapterError(f"{label} header names must be non-empty strings")
        if not isinstance(value, str):
            raise AdapterError(
                f"{label} header {key!r} value must be a string"
            )
        normalized_headers.append((key.strip(), value))

    return tuple(normalized_headers)


def _parse_args(label: str, entry: dict[str, Any]) -> tuple[str, ...]:
    args = entry.get("args", [])

    if not isinstance(args, list):
        raise AdapterError(f"{label} args must be a list")

    normalized_args = []
    for index, arg in enumerate(args):
        if not isinstance(arg, str):
            raise AdapterError(f"{label} args[{index}] must be a string")
        normalized_args.append(arg)

    return tuple(normalized_args)


def _parse_env(label: str, entry: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    env = entry.get("env", {})

    if env is None:
        return ()

    if not isinstance(env, dict):
        raise AdapterError(f"{label} env must be an object")

    normalized_env = []
    for name, value in env.items():
        if not isinstance(name, str) or not name.strip():
            raise AdapterError(f"{label} env names must be non-empty strings")
        if not isinstance(value, str):
            raise AdapterError(f"{label} env[{name!r}] must be a string")
        normalized_env.append((name.strip(), value))

    return tuple(normalized_env)


def _parse_cwd(label: str, entry: dict[str, Any]) -> Path | None:
    cwd = entry.get("cwd")

    if cwd is None:
        return None

    if not isinstance(cwd, str) or not cwd.strip():
        raise AdapterError(f"{label} cwd must be a non-empty string")

    return Path(cwd.strip())


def _parse_timeout_seconds(label: str, entry: dict[str, Any]) -> float:
    timeout_seconds = entry.get("timeout_seconds", DEFAULT_MCP_TIMEOUT_SECONDS)

    if isinstance(timeout_seconds, bool) or not isinstance(
        timeout_seconds,
        int | float,
    ):
        raise AdapterError(f"{label} timeout_seconds must be a number")

    timeout_seconds = float(timeout_seconds)
    if timeout_seconds <= 0:
        raise AdapterError(f"{label} timeout_seconds must be greater than zero")

    return timeout_seconds


def _server_label(index: int) -> str:
    return f"MCP server entry {index}"
