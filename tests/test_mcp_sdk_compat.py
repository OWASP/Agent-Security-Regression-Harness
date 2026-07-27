"""Compatibility checks against the real installed MCP and HTTPX packages."""

from __future__ import annotations

import asyncio
import importlib
import importlib.metadata
import importlib.util
import os
import socket
from collections.abc import Callable, Generator
from typing import Any

import pytest

if importlib.util.find_spec("mcp") is None:
    pytest.skip(
        "real MCP SDK is required for compatibility tests",
        allow_module_level=True,
    )

import httpx

from agent_harness import mcp_host

_EXPECTED_API_ENV = "EXPECTED_MCP_HTTP_API"
_SUPPORTED_EXPECTATIONS = frozenset({"legacy", "modern"})
_CONSTRUCTION_URL = "https://example.invalid/mcp?compatibility-marker=issue161"
_HEADER_NAME = "X-Issue161-Compatibility"
_HEADER_VALUE = "compat-secret-marker"


@pytest.fixture(autouse=True)
def prevent_network_io(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    def blocked_socket_connection(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("compatibility tests must not open network connections")

    async def blocked_http_send(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("compatibility tests must not send HTTP requests")

    monkeypatch.setattr(socket, "create_connection", blocked_socket_connection)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked_http_send)
    yield


@pytest.fixture(scope="module")
def expected_api() -> str:
    value = os.environ.get(_EXPECTED_API_ENV)
    if value is None:
        pytest.skip(
            f"{_EXPECTED_API_ENV} is required for boundary-specific checks"
        )
    if value not in _SUPPORTED_EXPECTATIONS:
        pytest.fail(
            f"{_EXPECTED_API_ENV} must be one of "
            f"{sorted(_SUPPORTED_EXPECTATIONS)}; got {value!r}"
        )
    return value


def test_real_sdk_loader_preserves_stdio_and_selects_actual_http_callable() -> None:
    sdk = mcp_host._load_mcp_sdk()
    selected = mcp_host._select_streamable_http_client(sdk)
    streamable_http_module = importlib.import_module("mcp.client.streamable_http")
    selected_symbol = (
        "streamable_http_client"
        if selected.kind == "modern"
        else "streamablehttp_client"
    )

    assert callable(sdk.ClientSession)
    assert callable(sdk.StdioServerParameters)
    assert callable(sdk.stdio_client)
    assert selected.client is getattr(streamable_http_module, selected_symbol)
    assert selected.client.__module__.startswith("mcp.")


def test_real_selector_matches_explicit_matrix_expectation(
    expected_api: str,
) -> None:
    sdk = mcp_host._load_mcp_sdk()
    selected = mcp_host._select_streamable_http_client(sdk)
    diagnostic = _version_diagnostic()

    assert selected.kind == expected_api, (
        f"{diagnostic}; expected {expected_api!r}, selected {selected.kind!r}"
    )

    if expected_api == "legacy":
        assert sdk.streamablehttp_client is not None, diagnostic
    else:
        assert sdk.streamable_http_client is not None, diagnostic
        assert selected.client is sdk.streamable_http_client


def test_real_modern_invocation_accepts_production_argument_shape(
    expected_api: str,
) -> None:
    if expected_api != "modern":
        pytest.skip("modern invocation applies only to the latest-v1 boundary")

    sdk = mcp_host._load_mcp_sdk()
    selected = mcp_host._select_streamable_http_client(sdk)
    client = httpx.AsyncClient(
        headers={_HEADER_NAME: _HEADER_VALUE},
        timeout=httpx.Timeout(1.25),
        follow_redirects=False,
    )

    try:
        transport_context = selected.client(
            _CONSTRUCTION_URL,
            http_client=client,
        )
        _assert_async_context_manager(transport_context)
        assert client.follow_redirects is False
        request = client.build_request("POST", "https://example.invalid/mcp")
        if request.headers.get(_HEADER_NAME) != _HEADER_VALUE:
            pytest.fail("modern client did not preserve the configured header")
    finally:
        asyncio.run(client.aclose())

    assert client.is_closed


def test_real_legacy_invocation_accepts_production_argument_shape(
    expected_api: str,
) -> None:
    if expected_api != "legacy":
        pytest.skip("legacy invocation applies only to the minimum boundary")

    sdk = mcp_host._load_mcp_sdk()
    selected = mcp_host._select_streamable_http_client(sdk)
    factory = mcp_host._legacy_httpx_client_factory(httpx)
    transport_context = selected.client(
        _CONSTRUCTION_URL,
        headers={_HEADER_NAME: _HEADER_VALUE},
        timeout=1.25,
        sse_read_timeout=1.25,
        httpx_client_factory=factory,
    )

    _assert_async_context_manager(transport_context)


def test_legacy_factory_uses_real_httpx_and_forces_redirects_off() -> None:
    factory = mcp_host._legacy_httpx_client_factory(httpx)
    auth = httpx.BasicAuth("compat-user", "compat-password")
    client = factory(
        headers={_HEADER_NAME: _HEADER_VALUE},
        timeout=httpx.Timeout(1.25),
        auth=auth,
        follow_redirects=True,
    )

    try:
        assert isinstance(client, httpx.AsyncClient)
        assert client.follow_redirects is False
        assert client.auth is auth
        request = client.build_request("POST", "https://example.invalid/mcp")
        if request.headers.get(_HEADER_NAME) != _HEADER_VALUE:
            pytest.fail("legacy factory did not preserve the configured header")
    finally:
        asyncio.run(client.aclose())

    assert client.is_closed


def _assert_async_context_manager(value: Any) -> None:
    enter = getattr(value, "__aenter__", None)
    exit_ = getattr(value, "__aexit__", None)
    assert isinstance(enter, Callable)
    assert isinstance(exit_, Callable)


def _version_diagnostic() -> str:
    return (
        f"Python package compatibility: MCP {importlib.metadata.version('mcp')}, "
        f"HTTPX {importlib.metadata.version('httpx')}"
    )
