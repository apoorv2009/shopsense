from typing import Any

import pytest
from pydantic import ValidationError

from shopsense_api.domain.ticket.enums import IssueType, RiskFlag
from shopsense_api.domain.ticket.support_ticket import SUMMARY_MAX_CHARS, SupportTicket

from support import make_ticket


def make(**overrides: Any) -> SupportTicket:
    return make_ticket(**overrides)


def test_valid_ticket() -> None:
    ticket = make()
    assert ticket.issue_type is IssueType.REFUND_REQUEST
    assert not ticket.missing_order_id


def test_order_id_normalised_by_validator() -> None:
    assert make(order_id="ord-100003").order_id == "ORD-100003"


def test_malformed_order_id_is_a_validation_error() -> None:
    with pytest.raises(ValidationError, match="ORD-123456"):
        make(order_id="12345")


def test_missing_order_id_is_derived_by_code() -> None:
    assert make(order_id=None).missing_order_id
    assert not make(order_id=None, issue_type="policy_question").missing_order_id


@pytest.mark.parametrize(
    ("field", "value"),
    [("claimed_amount_paise", -1), ("summary", "x" * (SUMMARY_MAX_CHARS + 1)), ("urgency", "asap")],
)
def test_invalid_values_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        make(**{field: value})


def test_unknown_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        make(approved=True)


def test_ticket_is_frozen() -> None:
    ticket = make()
    with pytest.raises(ValidationError):
        setattr(ticket, "issue_type", IssueType.COMPLAINT)  # noqa: B010


def test_with_flag_adds_once() -> None:
    flagged = make().with_flag(RiskFlag.PROMPT_INJECTION_SUSPECTED)
    assert flagged.flags == [RiskFlag.PROMPT_INJECTION_SUSPECTED]
    assert flagged.with_flag(RiskFlag.PROMPT_INJECTION_SUSPECTED) is flagged
