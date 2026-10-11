"""Outbox worker (M7-6): sends pending writes with their idempotency keys until each one settles.

- Settled (approved or processed): the item is done.
- Retryable failure (timeout, unavailable, circuit open): the item stays pending for the next pass.
- Any other refusal: the item is dead and goes to a person; it is never retried blindly.
- NOT_ALLOWED on a decision: the refund may already have settled (a lost response). It is checked
  against the order system before anything is retried."""

from dataclasses import dataclass, replace
from typing import Any

from shopsense_api.application.ports.orders import OrderTools
from shopsense_api.application.ports.outbox import DEAD, DONE, PENDING, OutboxItem, OutboxStore
from shopsense_api.domain.exceptions import OrderToolError

SETTLED = frozenset({"approved", "processed"})


@dataclass(frozen=True, slots=True)
class DrainOutbox:
    store: OutboxStore
    orders: OrderTools

    async def drain_item(self, item: OutboxItem) -> OutboxItem:
        if item.status != PENDING:
            return item
        try:
            result = await self._send_refund(item)
            done = replace(
                item, status=DONE, result=result, attempts=item.attempts + 1, last_error=None
            )
        except OrderToolError as exc:
            status = PENDING if exc.retryable else DEAD
            done = replace(
                item,
                status=status,
                attempts=item.attempts + 1,
                last_error=f"{exc.code}: {exc.message}"[:300],
            )
        await self.store.update(done)
        return done

    async def drain_pending(self, limit: int = 50) -> list[OutboxItem]:
        return [await self.drain_item(item) for item in await self.store.pending(limit)]

    async def _send_refund(self, item: OutboxItem) -> dict[str, Any]:
        p = item.payload
        result = await self.orders.request_refund(
            p["customer_no"], p["order_no"], p["sku"], p["amount_paise"], p["reason"], item.key
        )
        if result["status"] == "pending_approval" and p.get("approved"):
            try:
                result = await self.orders.decide_refund(result["refund_no"], approve=True)
            except OrderToolError as exc:
                if exc.code != "NOT_ALLOWED" or not await self._settled(item, result["refund_no"]):
                    raise
                return {"refund_no": result["refund_no"], "status": "processed"}
        if result["status"] in SETTLED:
            return result
        raise OrderToolError("UNEXPECTED_STATUS", f"refund held as {result['status']}")

    async def _settled(self, item: OutboxItem, refund_no: str) -> bool:
        p = item.payload
        refunds = await self.orders.get_refund_status(p["customer_no"], p["order_no"])
        return any(
            r.get("refund_no") == refund_no and r.get("status") == "processed" for r in refunds
        )
