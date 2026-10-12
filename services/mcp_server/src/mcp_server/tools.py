"""MCP tools (LLD-4). Two servers: read tools for agents, system tools for code only.

No tool takes a customer ID: the customer comes from the verified caller context, so a model
cannot name another customer's order by changing an argument."""

import os
from typing import Any, cast

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from mcp_server.auth import current_caller
from mcp_server.order_client import OrderClient

MAX_LIST = 10


def _transport_security() -> TransportSecuritySettings:
    """Host check for the streamable HTTP endpoints.

    FastMCP only allows localhost by default, so calls to the App Service hostname get HTTP 421.
    MCP_ALLOWED_HOSTS lists the deployed hostnames (comma separated, no port).
    """
    deployed = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", *deployed],
    )


def build_read_server(orders: OrderClient) -> FastMCP:
    mcp = FastMCP(
        "shopsense-read",
        stateless_http=True,
        streamable_http_path="/",
        transport_security=_transport_security(),
    )

    @mcp.tool()
    async def list_my_orders(limit: int = 5) -> dict[str, Any]:
        """The caller's most recent orders (at most 10)."""
        bounded = min(max(limit, 1), MAX_LIST)
        found: list[dict[str, Any]] = await orders.get(
            current_caller().customer_no, "/v1/orders", {"limit": bounded}
        )
        return {"orders": found}

    @mcp.tool()
    async def get_order(order_no: str) -> dict[str, Any]:
        """Items (sku, name, category, paid and refunded amounts), status and delivery time."""
        return cast(
            dict[str, Any], await orders.get(current_caller().customer_no, f"/v1/orders/{order_no}")
        )

    @mcp.tool()
    async def track_shipment(order_no: str) -> dict[str, Any]:
        """Carrier, status, promised date and recent scans for one order."""
        return cast(
            dict[str, Any],
            await orders.get(current_caller().customer_no, f"/v1/orders/{order_no}/shipment"),
        )

    @mcp.tool()
    async def get_refund_status(order_no: str) -> dict[str, Any]:
        """Refunds already requested for one order and their status."""
        found: list[dict[str, Any]] = await orders.get(
            current_caller().customer_no, f"/v1/orders/{order_no}/refunds"
        )
        return {"refunds": found}

    @mcp.tool()
    async def calculate_refund(order_no: str, item_sku: str, reason: str) -> dict[str, Any]:
        """Refundable amount for one item. A pure calculation; nothing is written."""
        body = {"item_sku": item_sku, "reason": reason}
        path = f"/v1/orders/{order_no}/refund-quote"
        return cast(dict[str, Any], await orders.post(current_caller().customer_no, path, body))

    return mcp


def build_system_server(orders: OrderClient) -> FastMCP:
    mcp = FastMCP(
        "shopsense-system",
        stateless_http=True,
        streamable_http_path="/",
        transport_security=_transport_security(),
    )

    @mcp.tool()
    async def request_refund(
        order_no: str, item_sku: str, amount_paise: int, reason: str, idempotency_key: str
    ) -> dict[str, Any]:
        """Request a refund. Above the auto-approval cap the order system holds it for review."""
        body = {
            "order_no": order_no,
            "item_sku": item_sku,
            "amount_paise": amount_paise,
            "reason": reason,
        }
        customer = current_caller().customer_no
        return cast(
            dict[str, Any], await orders.post(customer, "/v1/refunds", body, idempotency_key)
        )

    @mcp.tool()
    async def request_replacement(
        order_no: str, item_sku: str, reason: str, idempotency_key: str
    ) -> dict[str, Any]:
        """Request a replacement for one delivered item."""
        body = {"order_no": order_no, "item_sku": item_sku, "reason": reason}
        customer = current_caller().customer_no
        return cast(
            dict[str, Any], await orders.post(customer, "/v1/replacements", body, idempotency_key)
        )

    @mcp.tool()
    async def decide_refund(refund_no: str, approve: bool, grant: str = "") -> dict[str, Any]:
        """Reviewer decision on a pending refund. An approval needs its signed grant."""
        path = f"/v1/refunds/{refund_no}/decision"
        headers = {"X-Approval-Grant": grant} if grant else None
        body = {"approve": approve}
        return cast(dict[str, Any], await orders.post(None, path, body, headers=headers))

    return mcp
