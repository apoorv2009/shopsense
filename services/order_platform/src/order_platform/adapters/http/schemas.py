"""API request/response models. Responses expose only what callers need (L4d):
no phone, email, address or payment details beyond the payment-method type."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from order_platform.domain.model import Order, RefundReason, Shipment
from order_platform.domain.rules import RefundQuote

SKU_PATTERN = r"^[A-Z0-9-]{3,32}$"
ORDER_PATTERN = r"^ORD-\d{6}$"


class ItemOut(BaseModel):
    sku: str
    name: str
    category: str
    is_accessory: bool
    warranty_months: int
    qty: int
    paid_paise: int
    refunded_paise: int


class OrderSummaryOut(BaseModel):
    order_no: str
    status: str
    placed_at: datetime
    total_paise: int
    item_names: list[str]


class OrderOut(BaseModel):
    order_no: str
    status: str
    payment_method_type: str
    placed_at: datetime
    delivered_at: datetime | None
    shipment_status: str | None = None
    shipping_fee_paise: int
    items: list[ItemOut]


class ScanOut(BaseModel):
    status: str
    location: str
    scanned_at: datetime


class ShipmentOut(BaseModel):
    carrier: str
    awb: str
    status: str
    promised_date: date
    delivered_at: datetime | None
    recent_scans: list[ScanOut]


class RefundOut(BaseModel):
    refund_no: str
    order_no: str
    item_sku: str
    amount_paise: int
    reason: str
    status: str
    created_at: datetime


class RefundDecisionIn(BaseModel):
    approve: bool


class QuoteIn(BaseModel):
    item_sku: str = Field(pattern=SKU_PATTERN)
    reason: RefundReason


class QuoteOut(BaseModel):
    order_no: str
    item_sku: str
    paid_paise: int
    already_refunded_paise: int
    shipping_fee_paise: int
    refundable_paise: int
    requires_approval: bool


class RefundIn(BaseModel):
    order_no: str = Field(pattern=ORDER_PATTERN)
    item_sku: str = Field(pattern=SKU_PATTERN)
    amount_paise: int = Field(gt=0)
    reason: RefundReason


class ReplacementIn(BaseModel):
    order_no: str = Field(pattern=ORDER_PATTERN)
    item_sku: str = Field(pattern=SKU_PATTERN)
    reason: RefundReason


class ErrorOut(BaseModel):
    code: str
    message: str
    retryable: bool


def payment_type(method: str) -> str:
    return "card" if "card" in method.lower() else method


def order_out(order: Order) -> OrderOut:
    return OrderOut(
        order_no=order.order_no,
        status=order.status.value,
        payment_method_type=payment_type(order.payment_method),
        placed_at=order.placed_at,
        delivered_at=order.shipment.delivered_at if order.shipment else None,
        shipment_status=order.shipment.status.value if order.shipment else None,
        shipping_fee_paise=order.shipping_fee_paise,
        items=[
            ItemOut(
                sku=i.product.sku,
                name=i.product.name,
                category=i.product.category,
                is_accessory=i.product.is_accessory,
                warranty_months=i.product.warranty_months,
                qty=i.qty,
                paid_paise=i.paid_paise,
                refunded_paise=i.refunded_paise,
            )
            for i in order.items
        ],
    )


def summary_out(order: Order) -> OrderSummaryOut:
    return OrderSummaryOut(
        order_no=order.order_no,
        status=order.status.value,
        placed_at=order.placed_at,
        total_paise=order.total_paise,
        item_names=[i.product.name for i in order.items],
    )


def shipment_out(shipment: Shipment) -> ShipmentOut:
    scans = [
        ScanOut(status=e.status.value, location=e.location, scanned_at=e.scanned_at)
        for e in shipment.events
    ]
    return ShipmentOut(
        carrier=shipment.carrier,
        awb=shipment.awb,
        status=shipment.status.value,
        promised_date=shipment.promised_date,
        delivered_at=shipment.delivered_at,
        recent_scans=scans[-5:],
    )


def quote_out(quote: RefundQuote) -> QuoteOut:
    return QuoteOut(
        order_no=quote.order_no,
        item_sku=quote.item_sku,
        paid_paise=quote.paid_paise,
        already_refunded_paise=quote.already_refunded_paise,
        shipping_fee_paise=quote.shipping_fee_paise,
        refundable_paise=quote.refundable_paise,
        requires_approval=quote.requires_approval,
    )
