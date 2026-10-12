"""In-memory implementations of the Order Platform ports for fast unit tests."""

from dataclasses import replace
from datetime import UTC, date, datetime
from types import TracebackType
from typing import Any, Self

from order_platform.application.ports import StoredResponse
from order_platform.domain.errors import NotAllowedError, NotFoundError
from order_platform.domain.model import (
    Order,
    OrderItem,
    OrderStatus,
    Product,
    Refund,
    RefundStatus,
    Replacement,
    Shipment,
    ShipmentStatus,
)

NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)
LAPTOP = Product("ELE-LAPTOP14", "Laptop 14-inch", "electronics", False, 12)
KURTA = Product("APP-KURTA", "Cotton Kurta", "apparel", False, 0)


def order(
    order_no: str = "ORD-100003",
    customer_no: str = "C0002",
    product: Product = LAPTOP,
    price_paise: int = 5_499_000,
    status: OrderStatus = OrderStatus.DELIVERED,
    shipping_fee_paise: int = 0,
    shipment_status: ShipmentStatus = ShipmentStatus.DELIVERED,
) -> Order:
    shipment = Shipment("Blue Dart", "BL123", shipment_status, date(2026, 10, 1), NOW)
    return Order(
        order_no=order_no,
        customer_no=customer_no,
        status=status,
        payment_method="Credit Card",
        placed_at=NOW,
        shipping_fee_paise=shipping_fee_paise,
        items=(OrderItem(product, 1, price_paise, 0),),
        shipment=shipment,
    )


class MemoryRepo:
    def __init__(self, orders: list[Order]) -> None:
        self.orders = {o.order_no: o for o in orders}
        self.replacements: list[Replacement] = []

    async def list_for_customer(self, customer_no: str, limit: int) -> list[Order]:
        return [o for o in self.orders.values() if o.customer_no == customer_no][:limit]

    async def get(
        self, customer_no: str, order_no: str, *, for_update: bool = False
    ) -> Order | None:
        found = self.orders.get(order_no)
        return found if found and found.customer_no == customer_no else None

    async def add_refund(self, refund: Refund) -> None:
        current = self.orders[refund.order_no]
        items = tuple(
            replace(i, refunded_paise=i.refunded_paise + refund.amount_paise)
            if i.product.sku == refund.item_sku and refund.status is RefundStatus.APPROVED
            else i
            for i in current.items
        )
        self.orders[refund.order_no] = replace(
            current, items=items, refunds=(*current.refunds, refund)
        )

    async def add_replacement(self, replacement: Replacement) -> None:
        self.replacements.append(replacement)

    async def refund_scope(self, refund_no: str) -> tuple[str, str, int]:
        for order in self.orders.values():
            for r in order.refunds:
                if r.refund_no == refund_no:
                    return order.order_no, r.item_sku, r.amount_paise
        raise NotFoundError(f"refund {refund_no} not found")

    async def decide_refund(self, refund_no: str, approve: bool) -> Refund:
        found = next(
            (
                (no, r)
                for no, o in self.orders.items()
                for r in o.refunds
                if r.refund_no == refund_no
            ),
            None,
        )
        if found is None:
            raise NotFoundError(f"refund {refund_no} not found")
        order_no, match = found
        current = self.orders[order_no]
        if match.status is not RefundStatus.PENDING_APPROVAL:
            raise NotAllowedError(f"refund {refund_no} is {match.status.value}")
        settled = replace(
            match, status=RefundStatus.PROCESSED if approve else RefundStatus.REJECTED
        )
        items = tuple(
            replace(i, refunded_paise=i.refunded_paise + match.amount_paise)
            if approve and i.product.sku == match.item_sku
            else i
            for i in current.items
        )
        refunds = tuple(settled if r.refund_no == refund_no else r for r in current.refunds)
        self.orders[order_no] = replace(current, items=items, refunds=refunds)
        return settled


class MemoryIdempotency:
    def __init__(self) -> None:
        self.records: dict[str, StoredResponse] = {}

    async def get(self, key: str) -> StoredResponse | None:
        return self.records.get(key)

    async def save(self, key: str, request_hash: str, body: dict[str, Any]) -> None:
        self.records[key] = StoredResponse(request_hash, body)


class MemoryUoW:
    def __init__(self, repo: MemoryRepo, idem: MemoryIdempotency) -> None:
        self._repo, self._idem = repo, idem
        self.commits = 0

    @property
    def orders(self) -> MemoryRepo:
        return self._repo

    @property
    def idempotency(self) -> MemoryIdempotency:
        return self._idem

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


class FixedClock:
    def now(self) -> datetime:
        return NOW


class CountingIds:
    def __init__(self) -> None:
        self.n = 0

    def new(self, prefix: str) -> str:
        self.n += 1
        return f"{prefix}-{self.n:04d}"
