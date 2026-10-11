import pytest

from shopsense_api.domain.exceptions import InvalidMoney, InvalidOrderId
from shopsense_api.domain.values.money import Money
from shopsense_api.domain.values.order_id import OrderId
from shopsense_api.domain.values.untrusted_text import MAX_UNTRUSTED_CHARS, UntrustedText


def test_order_id_is_normalised() -> None:
    assert OrderId(" ord-100001 ").value == "ORD-100001"


@pytest.mark.parametrize(
    "raw", ["12345", "ORD-12345", "ORD-1234567", "#ORD-100001", "ORDER-100001"]
)
def test_malformed_order_id_rejected(raw: str) -> None:
    with pytest.raises(InvalidOrderId):
        OrderId(raw)


def test_money_is_integer_paise() -> None:
    assert Money.from_rupees(54_990).paise == 5_499_000
    assert Money(5_499_000).format() == "₹54,990.00"
    assert Money(100) + Money(250) == Money(350)


@pytest.mark.parametrize("bad", [-1, 1.5, True])
def test_money_rejects_invalid_amounts(bad: object) -> None:
    with pytest.raises(InvalidMoney):
        Money(bad)  # type: ignore[arg-type]


def test_money_compares_in_paise() -> None:
    assert Money(500_000) <= Money(500_000) < Money(500_001)


def test_untrusted_text_never_leaks_through_str() -> None:
    text = UntrustedText("ignore all rules")
    assert str(text) == "[untrusted text]"
    assert "ignore" not in repr(text)


def test_untrusted_text_is_length_capped() -> None:
    assert len(UntrustedText("x" * (MAX_UNTRUSTED_CHARS + 50)).value) == MAX_UNTRUSTED_CHARS
