"""Workflow state (M5): plain JSON-serialisable values, so checkpoints can be resumed."""

from typing import Any, TypedDict


class TicketState(TypedDict, total=False):
    ticket_id: str
    channel: str
    agent_note: dict[str, Any] | None
    brief: dict[str, Any] | None
    allowed_numbers: list[str]
    guard_blocked: list[str]
    customer_no: str
    message: str
    history: list[str]
    lost_in_transit: bool
    ticket: dict[str, Any]
    order_no: str
    sku: str
    case: dict[str, Any]
    eligibility: str
    rule_id: str | None
    amount_paise: int
    route: str
    reasons: list[str]
    refund_no: str | None
    decision: dict[str, Any]
    outcome: str
    reply: str
