import pytest

from shopsense_api.domain.guardrails.safety_screen import looks_like_safety_report
from shopsense_api.domain.ticket.enums import RiskFlag

from support import make_ticket


@pytest.mark.parametrize(
    "text",
    [
        "The lid of the pressure cooker blew off and burnt my wife's hand.",
        "it caused a skin reaction, can I talk to a human",
        "Used the serum and now my face has red rashes and burning",
        "The power bank started smoking while charging",
        "my son choked on a small part",
    ],
)
def test_safety_reports_detected(text: str) -> None:
    assert looks_like_safety_report(text)


@pytest.mark.parametrize(
    "text",
    [
        "Where is my order ORD-100006? Tracking has not moved.",
        "The kurta is too tight, I want size L.",
        "Refund status for ORD-100009 please",
    ],
)
def test_ordinary_tickets_not_flagged(text: str) -> None:
    assert not looks_like_safety_report(text)


def test_safety_issue_type_implies_flag() -> None:
    ticket = make_ticket(issue_type="product_safety", flags=[])
    assert ticket.flags == [RiskFlag.PRODUCT_SAFETY]
