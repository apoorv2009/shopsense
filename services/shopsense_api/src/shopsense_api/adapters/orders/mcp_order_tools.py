"""OrderTools over the MCP server (M6; LLD-4). Replaces the direct HTTP adapter.

Every call carries a signed caller context in `X-Caller-Context`. The customer in it comes from
the verified identity (our code), never from the model. Read tools go to /mcp/read; refund and
replacement writes and reviewer decisions go to /mcp/system, which only code calls."""

import json
import re
from typing import Any, cast

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult

from shopsense_api.domain.exceptions import OrderToolError
from shopsense_contracts.caller_context import HEADER, Scope, issue

SYSTEM_SUBJECT = "system"
RETRYABLE = frozenset({"TIMEOUT", "ORDER_SYSTEM_UNAVAILABLE"})
TOKEN_TTL_S = 300
_TOOL_PREFIX = re.compile(r"^Error executing tool \S+: ")


class McpOrderTools:
    def __init__(self, base_url: str, key: bytes, *, timeout_s: float = 15.0) -> None:
        self._base = base_url.rstrip("/")
        self._key = key
        self._timeout = timeout_s

    async def list_my_orders(self, customer_id: str, limit: int) -> list[dict[str, Any]]:
        result = await self._read(customer_id, "list_my_orders", {"limit": limit})
        return list(result.get("orders", []))

    async def get_order(self, customer_id: str, order_no: str) -> dict[str, Any]:
        return await self._read(customer_id, "get_order", {"order_no": order_no})

    async def track_shipment(self, customer_id: str, order_no: str) -> dict[str, Any]:
        return await self._read(customer_id, "track_shipment", {"order_no": order_no})

    async def get_refund_status(self, customer_id: str, order_no: str) -> list[dict[str, Any]]:
        result = await self._read(customer_id, "get_refund_status", {"order_no": order_no})
        return list(result.get("refunds", []))

    async def calculate_refund(
        self, customer_id: str, order_no: str, item_sku: str, reason: str
    ) -> dict[str, Any]:
        args = {"order_no": order_no, "item_sku": item_sku, "reason": reason}
        return await self._read(customer_id, "calculate_refund", args)

    async def request_refund(
        self,
        customer_id: str,
        order_no: str,
        item_sku: str,
        amount_paise: int,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        args = {
            "order_no": order_no,
            "item_sku": item_sku,
            "amount_paise": amount_paise,
            "reason": reason,
            "idempotency_key": idempotency_key,
        }
        return await self._write(customer_id, "request_refund", args)

    async def request_replacement(
        self, customer_id: str, order_no: str, item_sku: str, reason: str, idempotency_key: str
    ) -> dict[str, Any]:
        args = {
            "order_no": order_no,
            "item_sku": item_sku,
            "reason": reason,
            "idempotency_key": idempotency_key,
        }
        return await self._write(customer_id, "request_replacement", args)

    async def decide_refund(self, refund_no: str, approve: bool) -> dict[str, Any]:
        return await self._write(
            SYSTEM_SUBJECT, "decide_refund", {"refund_no": refund_no, "approve": approve}
        )

    async def _read(self, customer_id: str, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        return await self._call("read", Scope.READ, customer_id, tool, args)

    async def _write(self, customer_id: str, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        return await self._call("system", Scope.SYSTEM, customer_id, tool, args)

    async def _call(
        self, endpoint: str, scope: Scope, customer_id: str, tool: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        token = issue(customer_id, scope, self._key, ttl_s=TOKEN_TTL_S)
        url = f"{self._base}/mcp/{endpoint}/"
        try:
            async with (
                streamablehttp_client(url, headers={HEADER: token}, timeout=self._timeout) as (
                    read,
                    write,
                    _,
                ),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                result = await session.call_tool(tool, args)
        except Exception as exc:  # transport or protocol failure: the order system is unreachable
            raise OrderToolError(
                "ORDER_SYSTEM_UNAVAILABLE", "order system unreachable", retryable=True
            ) from exc
        return cast(dict[str, Any], _payload(result))


def _payload(result: CallToolResult) -> Any:
    text = result.content[0].text if result.content and hasattr(result.content[0], "text") else ""
    if result.isError:
        text = _TOOL_PREFIX.sub("", text, count=1)  # FastMCP prefixes "Error executing tool X: "
        code, _, message = text.partition(": ")
        if not message:
            code, message = "UNEXPECTED", text
        raise OrderToolError(code, message, retryable=code in RETRYABLE)
    if result.structuredContent is not None:
        return result.structuredContent
    return json.loads(text) if text else {}
