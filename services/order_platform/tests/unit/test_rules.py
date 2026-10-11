from dataclasses import replace

import pytest

from order_platform.domain.errors import NotAllowedError, ValidationFailedError
from order_platform.domain.model import (
    OrderStatus,
    RefundReason,
    RefundStatus,
    ReplacementStatus,
    ShipmentStatus,
)
from order_platform.domain.rules import (
    AUTO_APPROVAL_CAP_PAISE,
    decide_refund,
    decide_replacement,
    quote_refund,
)

from memory import KURTA, NOW, order


def test_quote_is_paid_minus_refunded() -> None:
    quote = quote_refund(order(), "ELE-LAPTOP14", RefundReason.DEFECTIVE)
    assert quote.refundable_paise == 5_499_000
    assert quote.requires_approval


def test_shipping_fee_refunded_only_for_seller_fault() -> None:
    small = order(product=KURTA, price_paise=39_900, shipping_fee_paise=4_900)
    assert quote_refund(small, "APP-KURTA", RefundReason.DAMAGED).refundable_paise == 44_800
    assert quote_refund(small, "APP-KURTA", RefundReason.SIZE_ISSUE).refundable_paise == 39_900


def test_refund_needs_delivery_unless_lost() -> None:
    shipped = order(status=OrderStatus.SHIPPED, shipment_status=ShipmentStatus.IN_TRANSIT)
    with pytest.raises(NotAllowedError):
        quote_refund(shipped, "ELE-LAPTOP14", RefundReason.CHANGED_MIND)
    lost = order(status=OrderStatus.SHIPPED, shipment_status=ShipmentStatus.LOST)
    assert quote_refund(lost, "ELE-LAPTOP14", RefundReason.LOST_IN_TRANSIT).refundable_paise > 0


def test_fully_refunded_item_cannot_be_refunded_again() -> None:
    o = order(product=KURTA, price_paise=149_900)
    refunded = replace(o, items=(replace(o.items[0], refunded_paise=149_900),))
    with pytest.raises(NotAllowedError):
        quote_refund(refunded, "APP-KURTA", RefundReason.SIZE_ISSUE)


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (AUTO_APPROVAL_CAP_PAISE, RefundStatus.APPROVED),
        (AUTO_APPROVAL_CAP_PAISE + 1, RefundStatus.PENDING_APPROVAL),
        (100, RefundStatus.APPROVED),
    ],
)
def test_cap_boundary(amount: int, expected: RefundStatus) -> None:
    quote = quote_refund(order(), "ELE-LAPTOP14", RefundReason.DEFECTIVE)
    assert decide_refund(quote, amount) is expected


def test_refund_above_refundable_is_rejected() -> None:
    quote = quote_refund(
        order(product=KURTA, price_paise=149_900), "APP-KURTA", RefundReason.SIZE_ISSUE
    )
    with pytest.raises(NotAllowedError):
        decide_refund(quote, 149_901)
    with pytest.raises(ValidationFailedError):
        decide_refund(quote, 0)


def test_pending_refund_blocks_another() -> None:
    from order_platform.domain.model import Refund

    pending = Refund(
        "RF-1",
        "ORD-100003",
        "ELE-LAPTOP14",
        5_499_000,
        RefundReason.DEFECTIVE,
        RefundStatus.PENDING_APPROVAL,
        NOW,
    )
    with pytest.raises(NotAllowedError, match="pending"):
        quote_refund(replace(order(), refunds=(pending,)), "ELE-LAPTOP14", RefundReason.DEFECTIVE)


def test_replacement_cap_and_delivery() -> None:
    assert decide_replacement(order(), "ELE-LAPTOP14") is ReplacementStatus.PENDING_APPROVAL
    kurta = order(product=KURTA, price_paise=149_900)
    assert decide_replacement(kurta, "APP-KURTA") is ReplacementStatus.CREATED
    with pytest.raises(NotAllowedError):
        decide_replacement(order(status=OrderStatus.PLACED), "ELE-LAPTOP14")
