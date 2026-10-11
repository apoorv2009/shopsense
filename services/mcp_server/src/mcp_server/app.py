"""ASGI app for the MCP server: /mcp/read and /mcp/system behind the caller-context middleware.

Run locally: uv run uvicorn mcp_server.app:app --port 8100"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from mcp_server.auth import CallerContextMiddleware
from mcp_server.entrypoints.settings import McpSettings
from mcp_server.order_client import OrderClient
from mcp_server.resilience import CircuitBreaker
from mcp_server.tools import build_read_server, build_system_server


def _breaker_health(breaker: CircuitBreaker) -> Any:
    async def health(_: Request) -> JSONResponse:
        return JSONResponse(breaker.snapshot())

    return health


def create_app(settings: McpSettings | None = None) -> CallerContextMiddleware:
    cfg = settings or McpSettings()
    client = httpx.AsyncClient(
        base_url=cfg.order_platform_url, timeout=cfg.order_platform_timeout_s
    )
    orders = OrderClient(client)
    breaker_view = orders.breaker
    read = build_read_server(orders)
    system = build_system_server(orders)
    read_app = read.streamable_http_app()
    system_app = system.streamable_http_app()

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        async with read.session_manager.run(), system.session_manager.run():
            try:
                yield
            finally:
                await client.aclose()

    routes = [
        Route("/health/breaker", _breaker_health(breaker_view)),
        Mount("/mcp/read", app=read_app),
        Mount("/mcp/system", app=system_app),
    ]
    inner = Starlette(routes=routes, lifespan=lifespan)
    return CallerContextMiddleware(inner, cfg.context_key.get_secret_value().encode("utf-8"))


app = create_app()
