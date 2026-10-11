"""Customer memory use cases (M3). Recall builds the trusted context block for agents;
remember writes one system-derived record per ticket outcome (D9 anti-poisoning rule)."""

from dataclasses import dataclass
from datetime import date

from shopsense_api.application.ports.memory import MemoryStore
from shopsense_api.domain.memory.model import (
    MAX_CONTEXT_RECORDS,
    CustomerContext,
    CustomerPreferences,
    TicketOutcome,
    TicketRecord,
    summarize_ticket,
)
from shopsense_api.domain.ticket.enums import IssueType, Sentiment


@dataclass(frozen=True, slots=True)
class RecallCustomer:
    store: MemoryStore

    async def run(self, customer_no: str) -> CustomerContext:
        records = await self.store.recent_tickets(customer_no, MAX_CONTEXT_RECORDS)
        prefs = await self.store.preferences(customer_no) or CustomerPreferences()
        return CustomerContext(customer_no, tuple(records), prefs)


@dataclass(frozen=True, slots=True)
class RememberTicket:
    store: MemoryStore

    async def run(
        self,
        *,
        customer_no: str,
        ticket_no: str,
        issue_type: IssueType,
        order_no: str | None,
        outcome: TicketOutcome,
        sentiment: Sentiment | None,
        amount_paise: int | None,
        resolved_on: date,
    ) -> TicketRecord:
        record = TicketRecord(
            customer_no=customer_no,
            ticket_no=ticket_no,
            issue_type=issue_type,
            order_no=order_no,
            outcome=outcome,
            sentiment=sentiment,
            resolved_on=resolved_on,
            summary=summarize_ticket(issue_type, order_no, outcome, amount_paise),
        )
        await self.store.add_ticket(record)
        return record
