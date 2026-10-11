"""Caller-context enforcement (LLD-4 L4a, L4b). Pure ASGI middleware: it verifies the signed
header, checks that the token's scope matches the endpoint, and stores the verified caller in a
context variable for the tools. A request that fails is answered here and never reaches a tool."""

import json
from contextvars import ContextVar
from typing import Any

from shopsense_contracts.caller_context import (
    HEADER,
    CallerContext,
    InvalidCallerContextError,
    Scope,
    verify,
)

Asgi = Any
CALLER: ContextVar[CallerContext | None] = ContextVar("caller", default=None)
ENDPOINT_SCOPE = {"/mcp/read": Scope.READ, "/mcp/system": Scope.SYSTEM}


class CallerContextMiddleware:
    def __init__(self, app: Asgi, key: bytes) -> None:
        self._app = app
        self._key = key

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        required = _required_scope(scope["path"])
        if required is None:
            await self._app(scope, receive, send)
            return
        try:
            caller = verify(_header(scope, HEADER), self._key)
        except InvalidCallerContextError as exc:
            await _reply(send, 401, str(exc))
            return
        if caller.scope != required.value:
            await _reply(send, 403, f"scope {caller.scope} cannot call this endpoint")
            return
        token = CALLER.set(caller)
        try:
            await self._app(scope, receive, send)
        finally:
            CALLER.reset(token)


def current_caller() -> CallerContext:
    caller = CALLER.get()
    if caller is None:
        raise RuntimeError("tool called without a verified caller context")
    return caller


def _required_scope(path: str) -> Scope | None:
    for prefix, scope in ENDPOINT_SCOPE.items():
        if path == prefix or path.startswith(prefix + "/"):
            return scope
    return None


def _header(scope: dict[str, Any], name: str) -> str:
    wanted = name.lower().encode("latin-1")
    for key, value in scope.get("headers", []):
        if key == wanted:
            return str(value.decode("latin-1"))
    return ""


async def _reply(send: Any, status: int, detail: str) -> None:
    body = json.dumps({"code": "CALLER_NOT_ALLOWED", "message": detail}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})
