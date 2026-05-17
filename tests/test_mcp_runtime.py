"""Tests for MCP runtime configuration primitives."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent_harness.adapters import AdapterError
from agent_harness.mcp_runtime import (
    DEFAULT_MCP_TIMEOUT_SECONDS,
    MCP_INSTALL_HINT,
    MCPHostRuntime,
    ensure_mcp_sdk_available,
    load_mcp_runtime_config,
    parse_mcp_runtime_config,
)


def test_load_mcp_runtime_config_accepts_valid_list_shape(tmp_path):
    config_path = tmp_path / "mcp-runtime.yaml"
    config_path.write_text(
        """
servers:
  - id: filesystem_fixture
    transport: stdio
    command: python
    args:
      - tests/fixtures/mcp_servers/filesystem_server.py
    timeout_seconds: 5
""",
        encoding="utf-8",
    )

    config = load_mcp_runtime_config(config_path)

    assert config.server_ids == ("filesystem_fixture",)
    server = config.get_server("filesystem_fixture")
    assert server.id == "filesystem_fixture"
    assert server.transport == "stdio"
    assert server.command == "python"
    assert server.args == ("tests/fixtures/mcp_servers/filesystem_server.py",)
    assert server.timeout_seconds == 5.0


def test_parse_mcp_runtime_config_rejects_servers_mapping_shape():
    with pytest.raises(AdapterError, match="servers must be a list"):
        parse_mcp_runtime_config(
            {
                "servers": {
                    "filesystem_fixture": {
                        "transport": "stdio",
                        "command": "python",
                    }
                }
            }
        )


def test_parse_mcp_runtime_config_accepts_mcp_servers_list_shape():
    config = parse_mcp_runtime_config(
        {
            "mcp_servers": [
                {
                    "id": "filesystem_fixture",
                    "transport": "stdio",
                    "command": "python",
                }
            ]
        }
    )

    assert config.server_ids == ("filesystem_fixture",)
    assert config.get_server("filesystem_fixture").args == ()
    assert (
        config.get_server("filesystem_fixture").timeout_seconds
        == DEFAULT_MCP_TIMEOUT_SECONDS
    )


def test_parse_mcp_runtime_config_accepts_explicit_env_and_cwd():
    config = parse_mcp_runtime_config(
        {
            "servers": [
                {
                    "id": "filesystem_fixture",
                    "transport": "stdio",
                    "command": "python",
                    "env": {
                        "SAFE_ENV_NAME": "value",
                    },
                    "cwd": "tests/fixtures/mcp_servers",
                }
            ]
        }
    )

    server = config.get_server("filesystem_fixture")
    assert server.env == (("SAFE_ENV_NAME", "value"),)
    assert str(server.cwd) in {
        "tests/fixtures/mcp_servers",
        "tests\\fixtures\\mcp_servers",
    }


def test_parse_mcp_runtime_config_rejects_empty_servers():
    with pytest.raises(AdapterError, match="at least one server"):
        parse_mcp_runtime_config({"servers": []})


def test_parse_mcp_runtime_config_rejects_empty_server_id():
    with pytest.raises(AdapterError, match="id must be a non-empty string"):
        parse_mcp_runtime_config(
            {
                "servers": [
                    {
                        "id": " ",
                        "transport": "stdio",
                        "command": "python",
                    }
                ]
            }
        )


def test_parse_mcp_runtime_config_rejects_server_id_with_slash():
    with pytest.raises(AdapterError, match="must not contain '/'"):
        parse_mcp_runtime_config(
            {
                "servers": [
                    {
                        "id": "bad/server",
                        "transport": "stdio",
                        "command": "python",
                    }
                ]
            }
        )


def test_parse_mcp_runtime_config_rejects_duplicate_server_ids():
    with pytest.raises(AdapterError, match="Duplicate MCP server id"):
        parse_mcp_runtime_config(
            {
                "servers": [
                    {
                        "id": "filesystem_fixture",
                        "transport": "stdio",
                        "command": "python",
                    },
                    {
                        "id": "filesystem_fixture",
                        "transport": "stdio",
                        "command": "python",
                    },
                ]
            }
        )


def test_parse_mcp_runtime_config_rejects_unknown_transport():
    with pytest.raises(AdapterError, match="transport 'streamable_http' is not supported"):
        parse_mcp_runtime_config(
            {
                "servers": [
                    {
                        "id": "filesystem_fixture",
                        "transport": "streamable_http",
                        "command": "python",
                    }
                ]
            }
        )


def test_parse_mcp_runtime_config_rejects_missing_command():
    with pytest.raises(AdapterError, match="command must be a non-empty string"):
        parse_mcp_runtime_config(
            {
                "servers": [
                    {
                        "id": "filesystem_fixture",
                        "transport": "stdio",
                    }
                ]
            }
        )


def test_parse_mcp_runtime_config_rejects_non_list_args():
    with pytest.raises(AdapterError, match="args must be a list"):
        parse_mcp_runtime_config(
            {
                "servers": [
                    {
                        "id": "filesystem_fixture",
                        "transport": "stdio",
                        "command": "python",
                        "args": "server.py",
                    }
                ]
            }
        )


def test_parse_mcp_runtime_config_rejects_non_string_arg():
    with pytest.raises(AdapterError, match=r"args\[0\] must be a string"):
        parse_mcp_runtime_config(
            {
                "servers": [
                    {
                        "id": "filesystem_fixture",
                        "transport": "stdio",
                        "command": "python",
                        "args": [123],
                    }
                ]
            }
        )


def test_parse_mcp_runtime_config_rejects_invalid_timeout():
    with pytest.raises(AdapterError, match="timeout_seconds must be greater than zero"):
        parse_mcp_runtime_config(
            {
                "servers": [
                    {
                        "id": "filesystem_fixture",
                        "transport": "stdio",
                        "command": "python",
                        "timeout_seconds": 0,
                    }
                ]
            }
        )


def test_ensure_mcp_sdk_available_raises_clear_install_hint_when_missing():
    def missing_import(name):
        raise ModuleNotFoundError(f"No module named {name!r}", name=name)

    with pytest.raises(AdapterError) as exc_info:
        ensure_mcp_sdk_available(import_module=missing_import)

    assert str(exc_info.value) == MCP_INSTALL_HINT


def test_ensure_mcp_sdk_available_uses_lazy_import():
    imported_names = []

    def fake_import(name):
        imported_names.append(name)
        return SimpleNamespace()

    ensure_mcp_sdk_available(import_module=fake_import)

    assert imported_names == ["mcp"]


def test_mcp_host_runtime_placeholder_checks_dependencies():
    def missing_import(name):
        raise ModuleNotFoundError(f"No module named {name!r}", name=name)

    config = parse_mcp_runtime_config(
        {
            "servers": [
                {
                    "id": "filesystem_fixture",
                    "transport": "stdio",
                    "command": "python",
                }
            ]
        }
    )
    runtime = MCPHostRuntime(config)

    with pytest.raises(AdapterError, match="MCP adapter dependencies are not installed"):
        runtime.ensure_dependencies(import_module=missing_import)
