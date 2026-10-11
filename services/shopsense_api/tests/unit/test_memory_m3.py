"""M3 memory tests: recall, remember and the anti-poisoning rule (D9)."""

from datetime import date

from shopsense_api.application.use_cases.memory import RecallCustomer, RememberTicket
from shopsense_api.domain.memory.model import (
    Channel,
    CustomerPreferences,
    RefundMethod,
    TicketOutcome,
    TicketRecord,
    summarize_ticket,
)
from shopsense_api.domain.ticket.enums import IssueType, Language, Sentiment


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self.tickets: list[TicketRecord] = []
        self.prefs: dict[str, CustomerPreferences] = {}

    async def recent_tickets(self, customer_no: str, limit: int) -> list[TicketRecord]:
        mine = [t for t in self.tickets if t.customer_no == customer_no]
        return sorted(mine, key=lambda t: t.resolved_on, reverse=True)[:limit]

    async def add_ticket(self, record: TicketRecord) -> None:
        self.tickets.append(record)

    async def preferences(self, customer_no: str) -> CustomerPreferences | None:
        return self.prefs.get(customer_no)

    async def set_preferences(self, customer_no: str, prefs: CustomerPreferences) -> None:
        self.prefs[customer_no] = prefs


async def _remember(store: InMemoryMemoryStore, **overrides: object) -> TicketRecord:
    args: dict[str, object] = {
        "customer_no": "C0001",
        "ticket_no": "TKT-1001",
        "issue_type": IssueType.REFUND_REQUEST,
        "order_no": "ORD-100002",
        "outcome": TicketOutcome.PENDING_APPROVAL,
        "sentiment": Sentiment.ANGRY,
        "amount_paise": 149_900,
        "resolved_on": date(2026, 10, 1),
    }
    return await RememberTicket(store).run(**(args | overrides))  # type: ignore[arg-type]


def test_summary_uses_system_facts_only() -> None:
    text = summarize_ticket(IssueType.REFUND_REQUEST, "ORD-100002", TicketOutcome.RESOLVED, 149_900)
    assert text == "refund request for ORD-100002, ₹1,499: resolved"


def test_summary_has_no_room_for_customer_text() -> None:
    # The only inputs are enums, an order number and an integer amount (D9 anti-poisoning).
    text = summarize_ticket(IssueType.COMPLAINT, None, TicketOutcome.HANDED_OFF, None)
    assert text == "complaint for no order: handed to a support specialist"


async def test_remember_stores_the_templated_summary() -> None:
    store = InMemoryMemoryStore()
    record = await _remember(store)
    assert store.tickets == [record]
    assert record.summary == "refund request for ORD-100002, ₹1,499: sent for approval"


async def test_recall_returns_recent_tickets_newest_first_and_preferences() -> None:
    store = InMemoryMemoryStore()
    await _remember(store, ticket_no="TKT-1", resolved_on=date(2026, 9, 1))
    await _remember(store, ticket_no="TKT-2", resolved_on=date(2026, 10, 2))
    await store.set_preferences(
        "C0001", CustomerPreferences(Language.HINGLISH, RefundMethod.BANK_TRANSFER, Channel.EMAIL)
    )
    ctx = await RecallCustomer(store).run("C0001")
    assert [r.ticket_no for r in ctx.records] == ["TKT-2", "TKT-1"]
    assert ctx.preferences.refund_method is RefundMethod.BANK_TRANSFER


async def test_recall_for_new_customer_is_empty_with_defaults() -> None:
    ctx = await RecallCustomer(InMemoryMemoryStore()).run("C0009")
    assert ctx.records == ()
    assert "no previous support tickets" in ctx.as_prompt_text()
    assert ctx.preferences == CustomerPreferences()


async def test_context_block_contains_only_system_records() -> None:
    store = InMemoryMemoryStore()
    await _remember(store)
    text = (await RecallCustomer(store).run("C0001")).as_prompt_text()
    assert "system records" in text
    assert "refund request for ORD-100002" in text
    assert "ignore" not in text.lower()


async def test_customers_do_not_see_each_others_history() -> None:
    store = InMemoryMemoryStore()
    await _remember(store, customer_no="C0002", ticket_no="TKT-9")
    ctx = await RecallCustomer(store).run("C0001")
    assert ctx.records == ()
