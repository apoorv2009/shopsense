"""M8 approval-grant tests: a grant is bound to one refund (order, item, amount) and expires."""

import pytest

from shopsense_contracts.approval_grant import GrantScope, InvalidGrantError, issue, verify

KEY = b"grant-test-key"
SCOPE = GrantScope("ORD-100003", "ELE-LAPTOP14", 2_500_000, "reviewer-1", "TKT-1")
NOW = 1_000_000


def test_grant_round_trip_for_the_same_refund() -> None:
    token = issue(SCOPE, KEY, now=NOW)
    assert verify(token, KEY, expect=SCOPE, now=NOW + 10) == SCOPE


def test_grant_for_another_amount_is_refused() -> None:
    token = issue(SCOPE, KEY, now=NOW)
    other = GrantScope("ORD-100003", "ELE-LAPTOP14", 2_600_000, "reviewer-1", "TKT-1")
    with pytest.raises(InvalidGrantError, match="another amount"):
        verify(token, KEY, expect=other, now=NOW)


def test_grant_for_another_item_is_refused() -> None:
    token = issue(SCOPE, KEY, now=NOW)
    other = GrantScope("ORD-100003", "ELE-PHONE", 2_500_000, "reviewer-1", "TKT-1")
    with pytest.raises(InvalidGrantError, match="another item"):
        verify(token, KEY, expect=other, now=NOW)


def test_expired_grant_is_refused() -> None:
    token = issue(SCOPE, KEY, ttl_s=60, now=NOW)
    with pytest.raises(InvalidGrantError, match="expired"):
        verify(token, KEY, expect=SCOPE, now=NOW + 61)


def test_forged_grant_is_refused() -> None:
    token = issue(SCOPE, b"someone-else", now=NOW)
    with pytest.raises(InvalidGrantError, match="bad signature"):
        verify(token, KEY, expect=SCOPE, now=NOW)


def test_grant_names_the_reviewer_who_approved() -> None:
    token = issue(SCOPE, KEY, now=NOW)
    assert verify(token, KEY, expect=SCOPE, now=NOW).reviewer == "reviewer-1"
