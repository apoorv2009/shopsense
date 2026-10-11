"""OrderTools over the Order Platform REST API (M2). Replaced by the MCP client in M6.

Identity travels in `X-Customer-Id`, set from the verified customer, never from model
output. Order-system errors become OrderToolError with the LLD-4 error code.
"""

import asyncio
from typing import Any

import httpx

from shopsense_api.domain.exceptions import OrderToolError


class HttpOrderTools:
    def __init__(
        self, client: httpx.AsyncClient, *, retries: int = 2, backoff_s: float = 0.5
    ) -> None:
        self._client = client
        self._retries = retries
        self._backoff_s = backoff_s

    async def list_my_orders(self, customer_id: str, limit: int) -> list[dict[str, Any]]:
        result = await self._call("GET", "/v1/orders", customer_id, params={"limit": limit})
        return list(result)

    async def get_order(self, customer_id: str, order_no: str) -> dict[str, Any]:
        return dict(await self._call("GET", f"/v1/orders/{order_no}", customer_id))

    async def track_shipment(self, customer_id: str, order_no: str) -> dict[str, Any]:
        return dict(await self._call("GET", f"/v1/orders/{order_no}/shipment", customer_id))

    async def get_refund_status(self, customer_id: str, order_no: str) -> list[dict[str, Any]]:
        return list(await self._call("GET", f"/v1/orders/{order_no}/refunds", customer_id))

    async def calculate_refund(
        self, customer_id: str, order_no: str, item_sku: str, reason: str
    ) -> dict[str, Any]:
        body = {"item_sku": item_sku, "reason": reason}
        path = f"/v1/orders/{order_no}/refund-quote"
        return dict(await self._call("POST", path, customer_id, json=body))

    async def request_refund(
        self,
        customer_id: str,
        order_no: str,
        item_sku: str,
        amount_paise: int,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        body = {
            "order_no": order_no,
            "item_sku": item_sku,
            "amount_paise": amount_paise,
            "reason": reason,
        }
        result = await self._call(
            "POST", "/v1/refunds", customer_id, json=body, key=idempotency_key
        )
        return dict(result)

    async def request_replacement(
        self, customer_id: str, order_no: str, item_sku: str, reason: str, idempotency_key: str
    ) -> dict[str, Any]:
        body = {"order_no": order_no, "item_sku": item_sku, "reason": reason}
        result = await self._call(
            "POST", "/v1/replacements", customer_id, json=body, key=idempotency_key
        )
        return dict(result)

    async def _call(
        self,
        method: str,
        path: str,
        customer_id: str,
        *,
        key: str | None = None,
        **kwargs: Any,
    ) -> Any:
        headers = {"X-Customer-Id": customer_id} | ({"Idempotency-Key": key} if key else {})
        for attempt in range(self._retries + 1):
            try:
                return await self._once(method, path, headers, **kwargs)
            except OrderToolError as exc:
                # Safe for writes too: the same idempotency key replays, never repeats
                if not exc.retryable or attempt == self._retries:
                    raise
                await asyncio.sleep(self._backoff_s * (attempt + 1))
        raise AssertionError("unreachable")

    async def _once(self, method: str, path: str, headers: dict[str, str], **kwargs: Any) -> Any:
        try:
            response = await self._client.request(method, path, headers=headers, **kwargs)
        except httpx.TimeoutException as exc:
            raise OrderToolError("TIMEOUT", "order system too slow", retryable=True) from exc
        except httpx.TransportError as exc:
            raise OrderToolError(
                "ORDER_SYSTEM_UNAVAILABLE", "order system unreachable", retryable=True
            ) from exc
        if response.is_success:
            return response.json()
        raise _error(response)


def _error(response: httpx.Response) -> OrderToolError:
    try:
        body = response.json()
        return OrderToolError(
            str(body["code"]), str(body["message"]), retryable=bool(body.get("retryable"))
        )
    except (ValueError, KeyError, TypeError):
        retryable = response.status_code >= 500
        code = "ORDER_SYSTEM_UNAVAILABLE" if retryable else "UNEXPECTED_RESPONSE"
        return OrderToolError(code, f"HTTP {response.status_code}", retryable=retryable)
