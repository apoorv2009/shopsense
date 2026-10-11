"""Ticket workflow steps (M5). Each step reads plain state and returns the fields it changes.

The steps know nothing about LangGraph: the adapter wires them into a graph and adds the
approval interrupt. Writes happen only in `execute_auto` and `execute_approved`, and each one
is reached only through the risk gate (see `domain/workflow/risk.py`)."""

import hashlib
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any, Protocol

from shopsense_api.application.agents.order_actions import OrderActionsCommand, OrderActionsRun
from shopsense_api.application.ports.orders import OrderTools
from shopsense_api.application.ports.outbox import DONE, PENDING, OutboxItem, OutboxStore
from shopsense_api.application.use_cases.answer_policy import PolicyAnswer
from shopsense_api.application.use_cases.decide_return import DecideReturn
from shopsense_api.application.use_cases.drain_outbox import DrainOutbox
from shopsense_api.application.use_cases.triage_ticket import (
    TriageCommand,
    TriageResult,
)
from shopsense_api.application.workflow.state import TicketState
from shopsense_api.domain.exceptions import OrderToolError
from shopsense_api.domain.policy.rules_engine import Eligibility, ReturnCase
from shopsense_api.domain.ticket.enums import IssueType
from shopsense_api.domain.ticket.support_ticket import SupportTicket
from shopsense_api.domain.values.untrusted_text import UntrustedText
from shopsense_api.domain.workflow.risk import REFUND_ISSUES, Route, assess

Clock = Callable[[], datetime]


class Triager(Protocol):
    async def execute(self, command: TriageCommand) -> TriageResult: ...


WRONG_OR_MISSING = frozenset({IssueType.WRONG_ITEM, IssueType.MISSING_ITEM})
REFUND_REASON = {
    IssueType.DAMAGED_OR_DEFECTIVE: "damaged",
    IssueType.WRONG_ITEM: "wrong_item",
    IssueType.MISSING_ITEM: "missing_item",
    IssueType.REFUND_REQUEST: "changed_mind",
    IssueType.RETURN_REQUEST: "changed_mind",
}


def refund_key(ticket_id: str, sku: str, amount_paise: int, stage: str) -> str:
    """Deterministic idempotency key: a retried step replays the same refund (LLD-7)."""
    raw = f"{ticket_id}|{sku}|{amount_paise}|{stage}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class OrderAdvisor(Protocol):
    async def run(self, command: OrderActionsCommand) -> OrderActionsRun: ...


class Answerer(Protocol):
    async def run(self, question: UntrustedText, category: str | None = None) -> PolicyAnswer: ...


class Reviewer(Protocol):
    async def run(self, message: UntrustedText, facts: dict[str, Any]) -> dict[str, Any]: ...


class TicketFlow:
    """Steps of the ticket workflow. Agents are optional so each step can be tested alone."""

    def __init__(
        self,
        triage: Triager,
        orders: OrderTools,
        decide: DecideReturn,
        clock: Clock = lambda: datetime.now(UTC),
        *,
        advisor: OrderAdvisor | None = None,
        answerer: Answerer | None = None,
        reviewer: Reviewer | None = None,
        outbox: OutboxStore | None = None,
        drainer: DrainOutbox | None = None,
    ) -> None:
        self._triage = triage
        self._orders = orders
        self._decide = decide
        self._clock = clock
        self._advisor = advisor
        self._answerer = answerer
        self._reviewer = reviewer
        self._outbox = outbox
        self._drainer = drainer

    async def advise_step(self, state: TicketState) -> dict[str, Any]:
        """Order-Actions agent, read-only: an explanation for the case, never a write."""
        if self._advisor is None:
            return {"agent_note": None}
        command = OrderActionsCommand(
            state["customer_no"], state["ticket_id"], UntrustedText(state["message"])
        )
        run = await self._advisor.run(command)
        return {
            "agent_note": {
                "outcome": run.result.outcome.value,
                "reason": run.result.reason,
                "reply": run.result.customer_reply,
            }
        }

    async def review_step(self, state: TicketState) -> dict[str, Any]:
        """Escalation Reviewer: a brief for the human decision-maker. Advisory, no tools."""
        if self._reviewer is None:
            return {"brief": None}
        facts = {
            "order": state.get("order_no"),
            "item_sku": state.get("sku"),
            "amount_paise": state.get("amount_paise"),
            "policy_result": state.get("eligibility"),
            "rule_id": state.get("rule_id"),
            "held_because": ", ".join(state.get("reasons", [])),
            "channel": state.get("channel", "chat"),
        }
        brief = await self._reviewer.run(UntrustedText(state["message"]), facts)
        return {"brief": brief}

    async def triage_step(self, state: TicketState) -> dict[str, Any]:
        result = await self._triage.execute(TriageCommand(UntrustedText(state["message"])))
        return {"ticket": result.ticket.model_dump(mode="json")}

    async def lookup_step(self, state: TicketState) -> dict[str, Any]:
        ticket = SupportTicket.model_validate(state["ticket"])
        if ticket.order_id is None:
            return _done("needs_customer_info", "Could you share your order number (ORD-xxxxxx)?")
        try:
            order = await self._orders.get_order(state["customer_no"], ticket.order_id)
        except OrderToolError as exc:
            if exc.retryable:  # outage: we cannot check the order, so a person follows up (M7-5)
                return _done("parked_human_queue", _PARKED)
            return _done("needs_customer_info", "I could not find that order on your account.")
        if order.get("delivered_at") is None:
            return _done("cannot_help", f"Order {ticket.order_id} has not been delivered yet.")
        item = _pick_item(order["items"], state["message"])
        if item is None:
            return _done("needs_customer_info", "Which item in the order is this about?")
        case = _case(item, order, ticket, self._clock())
        return {"order_no": ticket.order_id, "sku": item["sku"], "case": _case_state(case)}

    async def assess_step(self, state: TicketState) -> dict[str, Any]:
        ticket = SupportTicket.model_validate(state["ticket"])
        if ticket.issue_type not in REFUND_ISSUES:
            verdict = assess(ticket, Eligibility.ELIGIBLE, 0)
            return {
                "route": verdict.route.value,
                "reasons": list(verdict.reasons),
                "outcome": "answered",
                "reply": await self._info_reply(ticket, state),
            }
        case = _case_from_state(state["case"])
        policy = await self._decide.run(case)
        try:
            quote = await self._orders.calculate_refund(
                state["customer_no"], state["order_no"], state["sku"], _reason(ticket)
            )
        except OrderToolError:
            return _done("handed_off", _HANDOFF) | {"route": Route.HUMAN.value, "reasons": []}
        refundable = int(quote["refundable_paise"])
        claimed = ticket.claimed_amount_paise
        amount = refundable if claimed is None else min(claimed, refundable)
        verdict = assess(ticket, policy.eligibility, amount, state.get("channel", "chat"))
        update: dict[str, Any] = {
            "eligibility": policy.eligibility.value,
            "rule_id": policy.rule_id,
            "amount_paise": amount,
            "route": verdict.route.value,
            "reasons": list(verdict.reasons),
        }
        if verdict.route is Route.REPLY:
            update |= {"outcome": "answered", "reply": policy.reply}
        if verdict.route is Route.HUMAN:
            update |= {"outcome": "handed_off", "reply": _HANDOFF}
        return update

    async def _info_reply(self, ticket: SupportTicket, state: TicketState) -> str:
        if ticket.issue_type is IssueType.POLICY_QUESTION and self._answerer is not None:
            answer = await self._answerer.run(UntrustedText(state["message"]))
            return answer.reply
        return _INFO_REPLY

    async def execute_auto(self, state: TicketState) -> dict[str, Any]:
        """The only write for a calm, in-cap refund; reached only from the AUTO route."""
        if state.get("route") != Route.AUTO.value:
            raise RuntimeError("write attempted outside the AUTO route")
        return await self._refund(state, stage="auto", approve_pending=False)

    async def execute_approved(self, state: TicketState) -> dict[str, Any]:
        """Runs after a reviewer decision. A rejection writes nothing."""
        decision = state.get("decision") or {}
        if not decision.get("approve"):
            return _done("rejected", _REJECTED)
        return await self._refund(state, stage="approved", approve_pending=True)

    async def respond_step(self, state: TicketState) -> dict[str, Any]:
        if state.get("reply"):
            return {}
        return _done(state.get("outcome", "handed_off"), _HANDOFF)

    async def _refund(
        self, state: TicketState, *, stage: str, approve_pending: bool
    ) -> dict[str, Any]:
        sku, amount = state["sku"], int(state["amount_paise"])
        ticket = SupportTicket.model_validate(state["ticket"])
        key = refund_key(state["ticket_id"], sku, amount, stage)
        if self._outbox is not None and self._drainer is not None:
            return await self._refund_via_outbox(state, key, approve_pending, ticket)
        try:
            result = await self._orders.request_refund(
                state["customer_no"], state["order_no"], sku, amount, _reason(ticket), key
            )
            if result["status"] == "pending_approval" and approve_pending:
                result = await self._orders.decide_refund(result["refund_no"], approve=True)
        except OrderToolError:
            return _done("handed_off", _HANDOFF) | {"refund_no": None}
        status = result["status"]
        if status in ("approved", "processed"):
            return _done("resolved", _approved_reply(amount)) | {"refund_no": result["refund_no"]}
        return _done("handed_off", _HANDOFF) | {"refund_no": result.get("refund_no")}

    async def _refund_via_outbox(
        self, state: TicketState, key: str, approve_pending: bool, ticket: SupportTicket
    ) -> dict[str, Any]:
        """Record the write, then send it. A failure leaves it pending for the worker (M7-6)."""
        if self._outbox is None or self._drainer is None:
            raise RuntimeError("outbox path needs an outbox and a drainer")
        amount = int(state["amount_paise"])
        payload = {
            "customer_no": state["customer_no"],
            "order_no": state["order_no"],
            "sku": state["sku"],
            "amount_paise": amount,
            "reason": _reason(ticket),
            "approved": approve_pending,
        }
        item = OutboxItem(key=key, ticket_id=state["ticket_id"], action="refund", payload=payload)
        await self._outbox.enqueue(item)
        settled = await self._drainer.drain_item(item)
        if settled.status == DONE:
            refund_no = settled.result.get("refund_no")
            return _done("resolved", _approved_reply(amount)) | {"refund_no": refund_no}
        if settled.status == PENDING:
            return _done("queued_for_retry", _QUEUED) | {"refund_no": None}
        return _done("handed_off", _HANDOFF) | {"refund_no": None}


_INFO_REPLY = (
    "Thanks for your message. Your order status is in your order tracker, "
    "and a specialist can help with anything else."
)
_PARKED = (
    "We are having trouble reaching our order system. "
    "A specialist will check your order and follow up."
)
_QUEUED = "Your refund is approved and is being processed. We will confirm once it has settled."
_HANDOFF = "A support specialist will review your request and get back to you shortly."
_REJECTED = "We could not approve this refund. A support specialist will contact you with details."


def _done(outcome: str, reply: str) -> dict[str, Any]:
    return {"outcome": outcome, "reply": reply}


def _approved_reply(amount_paise: int) -> str:
    return f"Your refund of ₹{amount_paise // 100:,} has been processed."


def _reason(ticket: SupportTicket) -> str:
    return REFUND_REASON.get(ticket.issue_type, "other")


def _pick_item(items: list[dict[str, Any]], message: str) -> dict[str, Any] | None:
    if len(items) == 1:
        return items[0]
    named = [i for i in items if i["name"].lower() in message.lower()]
    return named[0] if len(named) == 1 else None


def _case(
    item: dict[str, Any], order: dict[str, Any], ticket: SupportTicket, now: datetime
) -> ReturnCase:
    delivered = datetime.fromisoformat(order["delivered_at"])
    minutes = int((now - delivered).total_seconds() // 60)
    return ReturnCase(
        category=item["category"],
        is_accessory=bool(item["is_accessory"]),
        payment_method="cod"
        if str(order.get("payment_method_type", "")).upper() == "COD"
        else "prepaid",
        delivered_on=delivered.date(),
        today=now.date(),
        item_condition=_condition(ticket),
        reported_minutes=max(minutes, 0),
        photo_verified=False,
        price_paise=int(item["paid_paise"]),
    )


def _condition(ticket: SupportTicket) -> str | None:
    if ticket.issue_type is IssueType.DAMAGED_OR_DEFECTIVE:
        return "damaged"
    if ticket.issue_type in WRONG_OR_MISSING:
        return "wrong_or_missing"
    return None


def _case_state(case: ReturnCase) -> dict[str, Any]:
    return {
        "category": case.category,
        "is_accessory": case.is_accessory,
        "payment_method": case.payment_method,
        "delivered_on": case.delivered_on.isoformat(),
        "today": case.today.isoformat(),
        "item_condition": case.item_condition,
        "reported_minutes": case.reported_minutes,
        "photo_verified": case.photo_verified,
        "price_paise": case.price_paise,
    }


def _case_from_state(data: dict[str, Any]) -> ReturnCase:
    return ReturnCase(
        category=data["category"],
        is_accessory=data["is_accessory"],
        payment_method=data["payment_method"],
        delivered_on=date.fromisoformat(data["delivered_on"]),
        today=date.fromisoformat(data["today"]),
        item_condition=data["item_condition"],
        reported_minutes=data["reported_minutes"],
        photo_verified=data["photo_verified"],
        price_paise=data["price_paise"],
    )
