"""M8 fabrication-guard tests: a reply may only use numbers the system holds."""

from typing import Any

from shopsense_api.application.workflow.flow import TicketFlow
from shopsense_api.domain.guardrails.fabrication import rupee_forms, unsupported


def test_policy_numbers_are_allowed() -> None:
    assert unsupported("Items can be returned within 15 days.", {"15"}) == set()


def test_an_invented_window_is_flagged() -> None:
    assert unsupported("Items can be returned within 60 days.", {"15", "30"}) == {"60"}


def test_paise_amounts_are_readable_as_rupees() -> None:
    assert (
        unsupported("Your refund of ₹1,499 has been processed.", rupee_forms({"149900"})) == set()
    )


def test_elapsed_day_counts_are_allowed_only_in_elapsed_sentences() -> None:
    assert unsupported("The 7-day window closed 3 days ago.", {"7"}) == set()
    assert unsupported("Your refund takes 60 days.", {"7"}) == {"60"}


def test_a_blocked_reply_becomes_a_hand_off() -> None:
    flow = TicketFlow(None, None, None, policy_numbers=frozenset({"15"}))  # type: ignore[arg-type]
    state: dict[str, Any] = {"message": "return window?", "allowed_numbers": []}
    update = flow._guard(state, "Electronics can be returned within 60 days.")  # type: ignore[arg-type]
    assert update["outcome"] == "handed_off"
    assert update["guard_blocked"] == ["60"]


def test_a_supported_reply_passes_the_guard() -> None:
    flow = TicketFlow(None, None, None, policy_numbers=frozenset({"15"}))  # type: ignore[arg-type]
    state: dict[str, Any] = {"message": "return window?", "allowed_numbers": []}
    assert flow._guard(state, "Electronics can be returned within 15 days.") == {}  # type: ignore[arg-type]
