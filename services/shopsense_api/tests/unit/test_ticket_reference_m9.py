"""A ticket number in a message is found and normalised; its status is a plain sentence."""

import pytest

from shopsense_api.domain.ticket.reference import find_ticket_reference, status_sentence


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Need help related to TKT-CH-d18a6b19b3", "TKT-CH-d18a6b19b3"),
        ("status of tkt-ch-D18A6B19B3 please", "TKT-CH-d18a6b19b3"),
        ("my ticket TKT-EM-0123456789ab", "TKT-EM-0123456789ab"),
    ],
)
def test_ticket_reference_is_found(text: str, expected: str) -> None:
    assert find_ticket_reference(text) == expected


def test_no_reference_in_ordinary_text() -> None:
    assert find_ticket_reference("where is my order ORD-100011") is None


def test_status_sentence_names_the_ticket() -> None:
    assert status_sentence("TKT-CH-d18a6b19b3", "pending_human_approval") == (
        "Ticket TKT-CH-d18a6b19b3 is waiting for a specialist to approve the refund. "
        "If you meant your order, please share the order number (ORD-xxxxxx)."
    )
