"""M3 demo: a returning customer is recognised from memory, the order agent works with that
context, the outcome is written back, and policy questions are answered from retrieved sections.

Prerequisites:
  - the Order Platform API running (uvicorn order_platform.entrypoints.api:app --port 8001)
  - SHOPSENSE_DATABASE_URL set (migrations run automatically)
  - policies ingested (uv run shopsense-ingest)

  uv run python milestones/m3/demo.py      # clears and reseeds the demo customer's memory first
"""

import asyncio
from datetime import date

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import delete

from shopsense_api.adapters.db.shopsense_tables import CustomerProfileRow, TicketHistoryRow
from shopsense_api.application.agents.order_actions import (
    OrderActionsCommand,
    OrderActionsRun,
    Outcome,
)
from shopsense_api.application.use_cases.answer_policy import PolicyAnswer
from shopsense_api.domain.memory.model import (
    Channel,
    CustomerContext,
    CustomerPreferences,
    RefundMethod,
    TicketOutcome,
)
from shopsense_api.domain.ticket.enums import IssueType, Language, Sentiment
from shopsense_api.domain.values.untrusted_text import UntrustedText
from shopsense_api.entrypoints.composition import Container, container
from shopsense_api.entrypoints.logging_config import configure_logging
from shopsense_api.entrypoints.settings import Settings

console = Console()
TODAY = date(2026, 10, 11)
CUSTOMER = "C0001"
PAST_TICKETS = (
    (
        "TKT-DEMO-1",
        IssueType.REFUND_REQUEST,
        "ORD-100001",
        TicketOutcome.RESOLVED,
        date(2026, 9, 20),
    ),
    (
        "TKT-DEMO-2",
        IssueType.DELIVERY_DELAY,
        "ORD-100002",
        TicketOutcome.RESOLVED,
        date(2026, 10, 2),
    ),
)
QUESTIONS = (
    "Can I return an opened vitamin C serum?",
    "I bought a power bank 10 days ago. Can I still return it?",
    "How do I get a refund for a cash on delivery order?",
    "Do you deliver to Mars?",
)
OUTCOME_OF = {
    Outcome.RESOLVED: TicketOutcome.RESOLVED,
    Outcome.PENDING_HUMAN_APPROVAL: TicketOutcome.PENDING_APPROVAL,
    Outcome.NEEDS_CUSTOMER_INFO: TicketOutcome.NEEDS_INFO,
    Outcome.CANNOT_HELP: TicketOutcome.HANDED_OFF,
}


async def reset_demo_memory(app: Container) -> None:
    assert app.sessions is not None
    async with app.sessions.begin() as session:
        await session.execute(
            delete(TicketHistoryRow).where(TicketHistoryRow.customer_no == CUSTOMER)
        )
        await session.execute(
            delete(CustomerProfileRow).where(CustomerProfileRow.customer_no == CUSTOMER)
        )


async def seed_history(app: Container) -> None:
    for ticket_no, issue, order_no, outcome, when in PAST_TICKETS:
        await app.remember().run(
            customer_no=CUSTOMER,
            ticket_no=ticket_no,
            issue_type=issue,
            order_no=order_no,
            outcome=outcome,
            sentiment=Sentiment.NEUTRAL,
            amount_paise=None,
            resolved_on=when,
        )
    prefs = CustomerPreferences(Language.HINGLISH, RefundMethod.ORIGINAL_PAYMENT, Channel.CHAT)
    await app.memory_store().set_preferences(CUSTOMER, prefs)


def show_context(ctx: CustomerContext) -> None:
    console.print(Panel(ctx.as_prompt_text(), title="Trusted customer context (system records)"))


async def serve_returning_customer(app: Container) -> None:
    ctx = await app.recall().run(CUSTOMER)
    show_context(ctx)
    message = "The refund for ORD-100001 I asked about last month still has not reached me."
    run = await app.order_actions().run(
        OrderActionsCommand(CUSTOMER, "demo-m3-1", UntrustedText(message), ctx.as_prompt_text())
    )
    show_agent(run, message)
    await app.remember().run(
        customer_no=CUSTOMER,
        ticket_no="TKT-DEMO-3",
        issue_type=IssueType.REFUND_STATUS,
        order_no="ORD-100001",
        outcome=OUTCOME_OF[run.result.outcome],
        sentiment=Sentiment.FRUSTRATED,
        amount_paise=None,
        resolved_on=TODAY,
    )


def show_agent(run: OrderActionsRun, message: str) -> None:
    console.print(Panel(f"[dim]{CUSTOMER}: {message}[/dim]", title="1. Returning customer"))
    trace = Table("tool", "arguments", "result", show_lines=True)
    for step in run.tool_log:
        trace.add_row(step["tool"], str(step["arguments"]), str(step["result"])[:120])
    console.print(trace)
    console.print(f"outcome: [bold]{run.result.outcome}[/bold] · {run.result.customer_reply}\n")


async def after_memory(app: Container) -> None:
    ctx = await app.recall().run(CUSTOMER)
    console.rule("[bold]Memory after the ticket[/bold]")
    show_context(ctx)


async def answer_policies(app: Container) -> None:
    answerer = app.answer_policy()
    console.rule("[bold]Policy answers (retrieved sections, cited)[/bold]")
    for question in QUESTIONS:
        answer: PolicyAnswer = await answerer.run(UntrustedText(question))
        cites = ", ".join(answer.citations) or "none"
        console.print(Panel(f"{answer.reply}\n[dim]citations: {cites}[/dim]", title=question))


async def main() -> None:
    configure_logging(json=False)
    async with container(Settings()) as app:
        await reset_demo_memory(app)
        await seed_history(app)
        console.rule("[bold]M3 · Memory and policy index[/bold]")
        await serve_returning_customer(app)
        await after_memory(app)
        await answer_policies(app)


if __name__ == "__main__":
    asyncio.run(main())
