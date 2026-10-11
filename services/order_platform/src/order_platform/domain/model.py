"""Order Platform domain model (its own bounded context; nothing shared with ShopSense)."""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from order_platform.domain.errors import NotFoundError


class OrderStatus(StrEnum):
    PLACED = "placed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class ShipmentStatus(StrEnum):
    LABEL_CREATED = "label_created"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    RTO = "rto"
    LOST = "lost"


class RefundStatus(StrEnum):
    APPROVED = "approved"
    PENDING_APPROVAL = "pending_approval"
    PROCESSED = "processed"
    REJECTED = "rejected"


class ReplacementStatus(StrEnum):
    CREATED = "created"
    PENDING_APPROVAL = "pending_approval"


class RefundReason(StrEnum):
    DAMAGED = "damaged"
    DEFECTIVE = "defective"
    WRONG_ITEM = "wrong_item"
    MISSING_ITEM = "missing_item"
    NOT_AS_DESCRIBED = "not_as_described"
    SIZE_ISSUE = "size_issue"
    CHANGED_MIND = "changed_mind"
    LOST_IN_TRANSIT = "lost_in_transit"
    OTHER = "other"


# Seller or courier at fault: shipping fee is refundable too (returns policy §4)
SELLER_FAULT = frozenset(
    {
        RefundReason.DAMAGED,
        RefundReason.DEFECTIVE,
        RefundReason.WRONG_ITEM,
        RefundReason.MISSING_ITEM,
        RefundReason.LOST_IN_TRANSIT,
    }
)


@dataclass(frozen=True, slots=True)
class Product:
    sku: str
    name: str
    category: str
    is_accessory: bool
    warranty_months: int


@dataclass(frozen=True, slots=True)
class OrderItem:
    product: Product
    qty: int
    unit_price_paise: int
    refunded_paise: int

    @property
    def paid_paise(self) -> int:
        return self.unit_price_paise * self.qty

    @property
    def remaining_paise(self) -> int:
        return self.paid_paise - self.refunded_paise


@dataclass(frozen=True, slots=True)
class ScanEvent:
    status: ShipmentStatus
    location: str
    scanned_at: datetime


@dataclass(frozen=True, slots=True)
class Shipment:
    carrier: str
    awb: str
    status: ShipmentStatus
    promised_date: date
    delivered_at: datetime | None
    events: tuple[ScanEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class Refund:
    refund_no: str
    order_no: str
    item_sku: str
    amount_paise: int
    reason: RefundReason
    status: RefundStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Replacement:
    replacement_no: str
    order_no: str
    item_sku: str
    reason: RefundReason
    status: ReplacementStatus
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Order:
    order_no: str
    customer_no: str
    status: OrderStatus
    payment_method: str
    placed_at: datetime
    shipping_fee_paise: int
    items: tuple[OrderItem, ...]
    shipment: Shipment | None = None
    refunds: tuple[Refund, ...] = field(default=())

    @property
    def total_paise(self) -> int:
        return sum(i.paid_paise for i in self.items) + self.shipping_fee_paise

    def item(self, sku: str) -> OrderItem:
        for item in self.items:
            if item.product.sku == sku:
                return item
        raise NotFoundError(f"item {sku} not found in order {self.order_no}")

    def pending_refund_for(self, sku: str) -> Refund | None:
        return next(
            (
                r
                for r in self.refunds
                if r.item_sku == sku and r.status is RefundStatus.PENDING_APPROVAL
            ),
            None,
        )
