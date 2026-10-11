"""Financial invariants of the Order Platform (D10, LLD-7 money gate).

These hold regardless of what any caller (or model) asks for:
- a refund never exceeds what was paid minus what was already refunded;
- refunds and replacements above the automatic cap are held for human approval;
- an item with a refund pending approval cannot be refunded again.
Return-window eligibility is support policy and lives in ShopSense (D11), not here.
"""

from dataclasses import dataclass

from order_platform.domain.errors import NotAllowedError, ValidationFailedError
from order_platform.domain.model import (
    SELLER_FAULT,
    Order,
    OrderStatus,
    RefundReason,
    RefundStatus,
    ReplacementStatus,
    ShipmentStatus,
)

AUTO_APPROVAL_CAP_PAISE = 500_000  # ₹5,000 (Refund Authorisation Matrix, POL-AUTH-002)


@dataclass(frozen=True, slots=True)
class RefundQuote:
    order_no: str
    item_sku: str
    paid_paise: int
    already_refunded_paise: int
    shipping_fee_paise: int
    refundable_paise: int
    requires_approval: bool


def _refundable_order(order: Order) -> None:
    lost = order.shipment is not None and order.shipment.status is ShipmentStatus.LOST
    if order.status is not OrderStatus.DELIVERED and not lost:
        raise NotAllowedError(
            f"order {order.order_no} is {order.status.value}; refunds need delivery"
        )


def quote_refund(order: Order, sku: str, reason: RefundReason) -> RefundQuote:
    _refundable_order(order)
    item = order.item(sku)
    if order.pending_refund_for(sku) is not None:
        raise NotAllowedError(f"a refund for {sku} is already pending approval")
    no_prior_refunds = not order.refunds
    shipping = order.shipping_fee_paise if reason in SELLER_FAULT and no_prior_refunds else 0
    refundable = item.remaining_paise + shipping
    if refundable <= 0:
        raise NotAllowedError(f"item {sku} is already fully refunded")
    return RefundQuote(
        order_no=order.order_no,
        item_sku=sku,
        paid_paise=item.paid_paise,
        already_refunded_paise=item.refunded_paise,
        shipping_fee_paise=shipping,
        refundable_paise=refundable,
        requires_approval=refundable > AUTO_APPROVAL_CAP_PAISE,
    )


def decide_refund(quote: RefundQuote, amount_paise: int) -> RefundStatus:
    if amount_paise <= 0:
        raise ValidationFailedError("refund amount must be positive")
    if amount_paise > quote.refundable_paise:
        raise NotAllowedError(
            f"refund of {amount_paise} paise exceeds refundable {quote.refundable_paise} paise"
        )
    if amount_paise > AUTO_APPROVAL_CAP_PAISE:
        return RefundStatus.PENDING_APPROVAL
    return RefundStatus.APPROVED


def decide_replacement(order: Order, sku: str) -> ReplacementStatus:
    if order.status is not OrderStatus.DELIVERED:
        raise NotAllowedError(
            f"order {order.order_no} is {order.status.value}; replacement needs delivery"
        )
    item = order.item(sku)
    if item.remaining_paise <= 0:
        raise NotAllowedError(f"item {sku} was refunded and cannot be replaced")
    if item.paid_paise > AUTO_APPROVAL_CAP_PAISE:
        return ReplacementStatus.PENDING_APPROVAL
    return ReplacementStatus.CREATED
