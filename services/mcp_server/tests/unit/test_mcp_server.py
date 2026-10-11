"""MCP server tests: caller context, endpoint scopes, tool surface and error mapping."""

from typing import Any

import httpx
import pytest
from mcp.server.fastmcp import FastMCP
from mcp.types import Tool
from mcp_server.auth import CallerContextMiddleware
from mcp_server.order_client import OrderClient, ToolFailureError
from mcp_server.tools import build_read_server, build_system_server
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from shopsense_contracts.caller_context import (
    HEADER,
    InvalidCallerContextError,
    Scope,
    issue,
    verify,
)

KEY = b"test-key"


def _inner() -> Starlette:
    async def ok(request: object) -> JSONResponse:
        return JSONResponse({"ok": True})

    return Starlette(routes=[Route("/mcp/read/", ok), Route("/mcp/system/", ok)])


def _client() -> TestClient:
    app: Any = CallerContextMiddleware(_inner(), KEY)
    return TestClient(app)


def test_round_trip_keeps_the_customer_and_scope() -> None:
    token = issue("C0001", Scope.READ, KEY, ticket_id="TKT-1", channel="chat", now=1_000)
    ctx = verify(token, KEY, now=1_100)
    assert (ctx.customer_no, ctx.scope, ctx.ticket_id, ctx.channel) == (
        "C0001",
        "tools.read",
        "TKT-1",
        "chat",
    )


def test_forged_token_is_refused() -> None:
    token = issue("C0001", Scope.READ, b"other-key", now=1_000)
    with pytest.raises(InvalidCallerContextError, match="bad signature"):
        verify(token, KEY, now=1_100)


def test_tampered_payload_is_refused() -> None:
    good = issue("C0001", Scope.READ, KEY, now=1_000)
    body, mac = good.split(".")
    evil = issue("C0002", Scope.READ, KEY, now=1_000).split(".")[0]
    with pytest.raises(InvalidCallerContextError):
        verify(f"{evil}.{mac}", KEY, now=1_100)
    assert body != evil


def test_expired_token_is_refused() -> None:
    token = issue("C0001", Scope.READ, KEY, ttl_s=60, now=1_000)
    with pytest.raises(InvalidCallerContextError, match="expired"):
        verify(token, KEY, now=1_100)


def test_malformed_token_is_refused() -> None:
    with pytest.raises(InvalidCallerContextError, match="malformed"):
        verify("not-a-token", KEY)


def test_missing_header_is_401() -> None:
    response = _client().post("/mcp/read/")
    assert response.status_code == 401


def test_read_token_cannot_call_the_system_endpoint() -> None:
    token = issue("C0001", Scope.READ, KEY)
    response = _client().post("/mcp/system/", headers={HEADER: token})
    assert response.status_code == 403


def test_system_token_reaches_the_system_endpoint() -> None:
    token = issue("system", Scope.SYSTEM, KEY)
    response = _client().get("/mcp/system/", headers={HEADER: token})
    assert response.status_code == 200


def test_read_endpoint_offers_no_write_tools() -> None:
    orders = OrderClient(httpx.AsyncClient(base_url="http://order.test"))
    read = build_read_server(orders)
    system = build_system_server(orders)
    read_names = {t.name for t in _tools(read)}
    system_names = {t.name for t in _tools(system)}
    assert read_names == {
        "list_my_orders",
        "get_order",
        "track_shipment",
        "get_refund_status",
        "calculate_refund",
    }
    assert {"request_refund", "request_replacement", "decide_refund"} <= system_names
    assert read_names.isdisjoint(system_names)


def _tools(server: FastMCP) -> list[Tool]:
    import asyncio

    async def listing() -> list[Tool]:
        return list(await server.list_tools())

    return asyncio.run(listing())


async def test_not_found_maps_to_a_tool_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"code": "NOT_FOUND", "message": "no", "retryable": False})

    client = httpx.AsyncClient(base_url="http://order.test", transport=httpx.MockTransport(handler))
    with pytest.raises(ToolFailureError) as exc:
        await OrderClient(client).get("C0001", "/v1/orders/ORD-1")
    assert exc.value.code == "NOT_FOUND"
    assert exc.value.retryable is False


async def test_server_error_is_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="bad gateway")

    client = httpx.AsyncClient(base_url="http://order.test", transport=httpx.MockTransport(handler))
    with pytest.raises(ToolFailureError) as exc:
        await OrderClient(client).get("C0001", "/v1/orders")
    assert exc.value.code == "ORDER_SYSTEM_UNAVAILABLE"
    assert exc.value.retryable is True


async def test_customer_header_comes_from_the_caller_not_the_arguments() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["customer"] = request.headers["X-Customer-Id"]
        return httpx.Response(200, json={"order_no": "ORD-100002"})

    client = httpx.AsyncClient(base_url="http://order.test", transport=httpx.MockTransport(handler))
    await OrderClient(client).get("C0001", "/v1/orders/ORD-100002")
    assert seen["customer"] == "C0001"
