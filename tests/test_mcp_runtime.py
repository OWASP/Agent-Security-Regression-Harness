"""Tests for MCP runtime configuration primitives."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from typing import Any

import pytest

from agent_harness.adapters import AdapterError
from agent_harness.mcp_runtime import (
    DEFAULT_MCP_TIMEOUT_SECONDS,
    MCP_INSTALL_HINT,
    MCPHostRuntime,
    MCPServerConfig,
    ensure_mcp_sdk_available,
    load_mcp_runtime_config,
    parse_mcp_runtime_config,
)


def parse_single_server(server: dict[str, Any]) -> MCPServerConfig:
    config = parse_mcp_runtime_config({"servers": [server]})
    return config.get_server(server["id"])


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


def test_stdio_defaults_equality_and_positional_constructor_remain_compatible():
    parsed_server = parse_single_server(
        {
            "id": "filesystem_fixture",
            "transport": "stdio",
            "command": "python",
        }
    )
    expected_server = MCPServerConfig(
        "filesystem_fixture",
        "stdio",
        "python",
        (),
        (),
        None,
        DEFAULT_MCP_TIMEOUT_SECONDS,
    )

    assert parsed_server == expected_server
    assert parsed_server.url is None
    assert parsed_server.headers == ()


def test_parse_mcp_runtime_config_rejects_missing_transport():
    with pytest.raises(AdapterError, match="transport must be a non-empty string"):
        parse_mcp_runtime_config(
            {
                "servers": [
                    {
                        "id": "filesystem_fixture",
                        "command": "python",
                    }
                ]
            }
        )


def test_parse_streamable_http_accepts_url_only():
    server = parse_single_server(
        {
            "id": "remote_fixture",
            "transport": "streamable_http",
            "url": "https://example.test/mcp",
        }
    )

    assert server.transport == "streamable_http"
    assert server.command is None
    assert server.args == ()
    assert server.env == ()
    assert server.cwd is None
    assert server.url == "https://example.test/mcp"
    assert server.headers == ()
    assert server.timeout_seconds == DEFAULT_MCP_TIMEOUT_SECONDS


def test_parse_streamable_http_accepts_headers_and_timeout_in_declaration_order():
    server = parse_single_server(
        {
            "id": "remote_fixture",
            "transport": "streamable_http",
            "url": "https://example.test/mcp",
            "headers": {
                "X-Client-Name": "agent-harness",
                "X-Request-Mode": "regression",
            },
            "timeout_seconds": 30,
        }
    )

    assert server.headers == (
        ("X-Client-Name", "agent-harness"),
        ("X-Request-Mode", "regression"),
    )
    assert server.timeout_seconds == 30.0


def test_streamable_http_headers_are_immutable():
    server = parse_single_server(
        {
            "id": "remote_fixture",
            "transport": "streamable_http",
            "url": "https://example.test/mcp",
            "headers": {"X-Client-Name": "agent-harness"},
        }
    )

    assert isinstance(server.headers, tuple)
    with pytest.raises(FrozenInstanceError):
        server.headers = ()  # type: ignore[misc]


def test_streamable_http_repr_omits_url_and_headers():
    config = parse_mcp_runtime_config(
        {
            "servers": [
                {
                    "id": "remote_fixture",
                    "transport": "streamable_http",
                    "url": "https://example.test/mcp?token=url-secret",
                    "headers": {"X-Api-Key": "header-secret"},
                }
            ]
        }
    )

    config_repr = repr(config)
    assert "url=" not in config_repr
    assert "headers=" not in config_repr
    assert "url-secret" not in config_repr
    assert "header-secret" not in config_repr


def test_parse_streamable_http_requires_url():
    with pytest.raises(AdapterError, match="url must be a non-empty string"):
        parse_single_server(
            {
                "id": "remote_fixture",
                "transport": "streamable_http",
            }
        )


@pytest.mark.parametrize("url", [None, "", " "])
def test_parse_streamable_http_rejects_empty_url_values(url):
    with pytest.raises(AdapterError, match="url must be a non-empty string"):
        parse_single_server(
            {
                "id": "remote_fixture",
                "transport": "streamable_http",
                "url": url,
            }
        )


@pytest.mark.parametrize(
    ("url", "error"),
    [
        ("ftp://example.test/mcp", "url scheme must be http or https"),
        ("https:///mcp", "url must include a host"),
        ("https://user@example.test/mcp", "url must not include credentials"),
        ("https://user:password@example.test/mcp", "url must not include credentials"),
        ("https://example.test/mcp#tools", "url must not include a fragment"),
        (r"https://example.test\mcp", "url must not contain backslashes"),
        ("https://example .test/mcp", "url must not contain spaces"),
        ("https://example.test:not-a-port/mcp", "url is invalid"),
        ("https://example.test:65536/mcp", "url is invalid"),
        ("https://[::1/mcp", "url is invalid"),
    ],
)
def test_parse_streamable_http_rejects_invalid_urls(url, error):
    with pytest.raises(AdapterError, match=error):
        parse_single_server(
            {
                "id": "remote_fixture",
                "transport": "streamable_http",
                "url": url,
            }
        )


@pytest.mark.parametrize("control", ["\x00", "\t", "\n", "\r", "\x1f", "\x7f"])
def test_parse_streamable_http_rejects_url_ascii_controls(control):
    with pytest.raises(AdapterError, match="url must not contain ASCII control"):
        parse_single_server(
            {
                "id": "remote_fixture",
                "transport": "streamable_http",
                "url": f"https://example.test/mcp{control}",
            }
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/mcp?mode=regression&limit=10",
        "http://localhost:8000/mcp",
        "http://192.168.1.25/mcp",
        "http://[::1]:8000/mcp",
    ],
)
def test_parse_streamable_http_accepts_supported_url_forms_without_rewriting(url):
    server = parse_single_server(
        {
            "id": "remote_fixture",
            "transport": "streamable_http",
            "url": url,
        }
    )

    assert server.url == url


@pytest.mark.parametrize("headers", [None, [], "X-Test: value"])
def test_parse_streamable_http_requires_headers_mapping(headers):
    with pytest.raises(AdapterError, match="headers must be an object"):
        parse_single_server(
            {
                "id": "remote_fixture",
                "transport": "streamable_http",
                "url": "https://example.test/mcp",
                "headers": headers,
            }
        )


def test_parse_streamable_http_requires_string_header_names():
    with pytest.raises(AdapterError, match="header names must be strings"):
        parse_single_server(
            {
                "id": "remote_fixture",
                "transport": "streamable_http",
                "url": "https://example.test/mcp",
                "headers": {123: "value"},
            }
        )


def test_parse_streamable_http_requires_string_header_values():
    with pytest.raises(AdapterError, match="header 'X-Retry' value must be a string"):
        parse_single_server(
            {
                "id": "remote_fixture",
                "transport": "streamable_http",
                "url": "https://example.test/mcp",
                "headers": {"X-Retry": 3},
            }
        )


@pytest.mark.parametrize(
    "name",
    ["", "Bad Header", "Bad:Header", " Header", "X-Ünicode"],
)
def test_parse_streamable_http_rejects_invalid_header_names(name):
    error = (
        "header names must be non-empty strings"
        if not name
        else "header name is invalid"
    )
    with pytest.raises(AdapterError, match=error):
        parse_single_server(
            {
                "id": "remote_fixture",
                "transport": "streamable_http",
                "url": "https://example.test/mcp",
                "headers": {name: "value"},
            }
        )


def test_parse_streamable_http_rejects_duplicate_header_names_case_insensitively():
    with pytest.raises(AdapterError, match="duplicate header name"):
        parse_single_server(
            {
                "id": "remote_fixture",
                "transport": "streamable_http",
                "url": "https://example.test/mcp",
                "headers": {
                    "X-Client-Name": "first",
                    "x-client-name": "second",
                },
            }
        )


@pytest.mark.parametrize(
    "name",
    [
        "Accept",
        "content-TYPE",
        "Mcp-Session-Id",
        "mcp-protocol-version",
        "Last-Event-ID",
        "HOST",
        "Content-Length",
        "transfer-encoding",
        "Connection",
    ],
)
def test_parse_streamable_http_rejects_reserved_headers_case_insensitively(name):
    with pytest.raises(AdapterError, match="header .* is reserved"):
        parse_single_server(
            {
                "id": "remote_fixture",
                "transport": "streamable_http",
                "url": "https://example.test/mcp",
                "headers": {name: "reserved-value"},
            }
        )


@pytest.mark.parametrize("control", ["\x00", "\t", "\n", "\r", "\x1f", "\x7f"])
def test_parse_streamable_http_rejects_header_value_ascii_controls(control):
    with pytest.raises(AdapterError, match="value must not contain ASCII control"):
        parse_single_server(
            {
                "id": "remote_fixture",
                "transport": "streamable_http",
                "url": "https://example.test/mcp",
                "headers": {"X-Test": f"safe{control}secret"},
            }
        )


def test_parse_streamable_http_accepts_static_authorization_and_custom_headers():
    server = parse_single_server(
        {
            "id": "remote_fixture",
            "transport": "streamable_http",
            "url": "https://example.test/mcp",
            "headers": {
                "Authorization": "Bearer test-token",
                "X-Api-Key": "test-key",
                "X-Custom": "custom-value",
            },
        }
    )

    assert server.headers == (
        ("Authorization", "Bearer test-token"),
        ("X-Api-Key", "test-key"),
        ("X-Custom", "custom-value"),
    )


@pytest.mark.parametrize(("field_name", "value"), [("url", None), ("headers", {})])
def test_stdio_rejects_streamable_http_fields_by_presence(field_name, value):
    with pytest.raises(AdapterError, match=f"field {field_name!r} is not allowed"):
        parse_single_server(
            {
                "id": "filesystem_fixture",
                "transport": "stdio",
                "command": "python",
                field_name: value,
            }
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("command", ""),
        ("command", None),
        ("args", []),
        ("args", None),
        ("env", {}),
        ("env", None),
        ("cwd", ""),
        ("cwd", None),
    ],
)
def test_streamable_http_rejects_stdio_fields_by_presence(field_name, value):
    with pytest.raises(AdapterError, match=f"field {field_name!r} is not allowed"):
        parse_single_server(
            {
                "id": "remote_fixture",
                "transport": "streamable_http",
                "url": "https://example.test/mcp",
                field_name: value,
            }
        )


def test_runtime_config_preserves_existing_unknown_field_policy():
    server = parse_single_server(
        {
            "id": "filesystem_fixture",
            "transport": "stdio",
            "command": "python",
            "unknown_future_field": "ignored",
        }
    )

    assert server.command == "python"


def test_header_validation_error_does_not_reveal_header_value():
    secret = "header-secret"

    with pytest.raises(AdapterError) as exc_info:
        parse_single_server(
            {
                "id": "remote_fixture",
                "transport": "streamable_http",
                "url": "https://example.test/mcp",
                "headers": {"X-Api-Key": f"{secret}\n"},
            }
        )

    assert secret not in str(exc_info.value)


def test_url_validation_error_does_not_reveal_url_or_query():
    secret = "query-secret"
    url = f"https://example.test:not-a-port/mcp?token={secret}"

    with pytest.raises(AdapterError) as exc_info:
        parse_single_server(
            {
                "id": "remote_fixture",
                "transport": "streamable_http",
                "url": url,
            }
        )

    assert url not in str(exc_info.value)
    assert secret not in str(exc_info.value)


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
    with pytest.raises(AdapterError, match="transport 'websocket' is not supported"):
        parse_mcp_runtime_config(
            {
                "servers": [
                    {
                        "id": "filesystem_fixture",
                        "transport": "websocket",
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
