"""Order tools port (LLD-4). Implemented over HTTP in M2 and over MCP from M6.

`customer_id` is always supplied by our code from the verified identity, never by the
model. Results are JSON-like dicts passed back to the agent; failures raise
OrderToolError with the LLD-4 error code.
"""

from typing import Any, Protocol


class OrderTools(Protocol):
    async def list_my_orders(self, customer_id: str, limit: int) -> list[dict[str, Any]]: ...

    async def get_order(self, customer_id: str, order_no: str) -> dict[str, Any]: ...

    async def track_shipment(self, customer_id: str, order_no: str) -> dict[str, Any]: ...

    async def get_refund_status(self, customer_id: str, order_no: str) -> list[dict[str, Any]]: ...

    async def calculate_refund(
        self, customer_id: str, order_no: str, item_sku: str, reason: str
    ) -> dict[str, Any]: ...

    async def request_refund(
        self,
        customer_id: str,
        order_no: str,
        item_sku: str,
        amount_paise: int,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]: ...

    async def request_replacement(
        self, customer_id: str, order_no: str, item_sku: str, reason: str, idempotency_key: str
    ) -> dict[str, Any]: ...
