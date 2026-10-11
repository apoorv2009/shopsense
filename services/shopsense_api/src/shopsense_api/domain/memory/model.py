"""Long-term customer memory (D9): system-derived facts only, never customer free text."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from shopsense_api.domain.ticket.enums import IssueType, Language, Sentiment

MAX_CONTEXT_RECORDS = 5


class TicketOutcome(StrEnum):
    RESOLVED = "resolved"
    PENDING_APPROVAL = "pending_approval"
    NEEDS_INFO = "needs_info"
    HANDED_OFF = "handed_off"


class RefundMethod(StrEnum):
    ORIGINAL_PAYMENT = "original_payment"
    BANK_TRANSFER = "bank_transfer"
    STORE_CREDIT = "store_credit"


class Channel(StrEnum):
    CHAT = "chat"
    EMAIL = "email"


_OUTCOME_LABEL = {
    TicketOutcome.RESOLVED: "resolved",
    TicketOutcome.PENDING_APPROVAL: "sent for approval",
    TicketOutcome.NEEDS_INFO: "more information requested",
    TicketOutcome.HANDED_OFF: "handed to a support specialist",
}


@dataclass(frozen=True, slots=True)
class TicketRecord:
    customer_no: str
    ticket_no: str
    issue_type: IssueType
    order_no: str | None
    outcome: TicketOutcome
    sentiment: Sentiment | None
    resolved_on: date
    summary: str


@dataclass(frozen=True, slots=True)
class CustomerPreferences:
    language: Language = Language.ENGLISH
    refund_method: RefundMethod = RefundMethod.ORIGINAL_PAYMENT
    channel: Channel = Channel.CHAT


@dataclass(frozen=True, slots=True)
class CustomerContext:
    customer_no: str
    records: tuple[TicketRecord, ...]
    preferences: CustomerPreferences

    def as_prompt_text(self) -> str:
        if not self.records:
            return f"Customer {self.customer_no}: no previous support tickets on record."
        lines = [f"- {r.resolved_on.isoformat()} {r.ticket_no}: {r.summary}" for r in self.records]
        return "\n".join(
            [
                f"Customer {self.customer_no} previous tickets (system records):",
                *lines,
                f"Preferences: language={self.preferences.language}, "
                f"refund_method={self.preferences.refund_method}",
            ]
        )


def summarize_ticket(
    issue_type: IssueType, order_no: str | None, outcome: TicketOutcome, amount_paise: int | None
) -> str:
    """Neutral one-line summary built from system facts only (D9 anti-poisoning rule)."""
    order = order_no or "no order"
    amount = f", ₹{amount_paise // 100:,}" if amount_paise else ""
    return f"{issue_type.value.replace('_', ' ')} for {order}{amount}: {_OUTCOME_LABEL[outcome]}"
