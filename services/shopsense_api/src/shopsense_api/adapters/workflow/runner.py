"""Start, inspect and resume ticket workflows by ticket ID (the LangGraph thread ID, D9a)."""

from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from typing import Any

from langgraph.types import Command

from shopsense_api.application.ports.outbox import DEAD, DONE, OutboxStore
from shopsense_api.application.workflow.state import TicketState


@dataclass(frozen=True, slots=True)
class TicketView:
    ticket_id: str
    outcome: str | None
    paused: bool
    route: str | None
    reply: str | None
    approval: dict[str, Any] | None = field(default=None)
    eligibility: str | None = field(default=None)
    rule_id: str | None = field(default=None)
    amount_paise: int | None = field(default=None)
    issue_type: str | None = field(default=None)


class TicketRunner:
    def __init__(self, graph: Any, outbox: OutboxStore | None = None) -> None:
        self._graph = graph
        self._outbox = outbox

    async def start(
        self, ticket_id: str, customer_no: str, message: str, channel: str = "chat"
    ) -> TicketView:
        config = _config(ticket_id)
        initial: TicketState = {
            "ticket_id": ticket_id,
            "customer_no": customer_no,
            "message": message,
            "channel": channel,
        }
        await self._graph.ainvoke(initial, config)
        return await self.view(ticket_id)

    async def resume(self, ticket_id: str, approve: bool, reviewer: str) -> TicketView:
        decision = {"approve": approve, "reviewer": reviewer}
        await self._graph.ainvoke(Command(resume=decision), _config(ticket_id))
        return await self.view(ticket_id)

    async def view(self, ticket_id: str) -> TicketView:
        snapshot = await self._graph.aget_state(_config(ticket_id))
        values = snapshot.values
        paused = "approval" in snapshot.next
        approval = None
        if paused and snapshot.tasks and snapshot.tasks[0].interrupts:
            approval = dict(snapshot.tasks[0].interrupts[0].value)
        outcome = "pending_human_approval" if paused else values.get("outcome")
        reply = values.get("reply")
        refund_no = values.get("refund_no")
        if outcome == "queued_for_retry" and self._outbox is not None:
            outcome, reply, refund_no = await _settled_from_outbox(
                self._outbox, ticket_id, outcome, reply, refund_no
            )
        return TicketView(
            ticket_id=ticket_id,
            outcome=outcome,
            paused=paused,
            route=values.get("route"),
            reply=reply,
            approval=approval,
            eligibility=values.get("eligibility"),
            rule_id=values.get("rule_id"),
            amount_paise=values.get("amount_paise"),
            issue_type=(values.get("ticket") or {}).get("issue_type"),
        )

    async def stream(
        self, ticket_id: str, customer_no: str, message: str, channel: str = "chat"
    ) -> AsyncIterator[dict[str, Any]]:
        """Run a ticket and yield one event per finished step, then the final view (SSE demo)."""
        initial: TicketState = {
            "ticket_id": ticket_id,
            "customer_no": customer_no,
            "message": message,
            "channel": channel,
        }
        async for chunk in self._graph.astream(initial, _config(ticket_id), stream_mode="updates"):
            for step, update in chunk.items():
                if step == "__interrupt__":
                    yield {"step": "approval", "paused": True}
                    continue
                yield {"step": step, "outcome": (update or {}).get("outcome")}
        view = await self.view(ticket_id)
        yield {"final": _view_dict(view)}

    async def exists(self, ticket_id: str) -> bool:
        snapshot = await self._graph.aget_state(_config(ticket_id))
        return bool(snapshot.values)


def _config(ticket_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": ticket_id}}


async def _settled_from_outbox(
    outbox: OutboxStore, ticket_id: str, outcome: str, reply: str | None, refund_no: str | None
) -> tuple[str, str | None, str | None]:
    """A queued write reads its outcome from the outbox: the worker may have settled it since."""
    items = await outbox.for_ticket(ticket_id)
    if any(item.status == DONE for item in items):
        done = next(item for item in items if item.status == DONE)
        amount = int(done.payload["amount_paise"])
        return (
            "resolved",
            f"Your refund of ₹{amount // 100:,} has been processed.",
            done.result.get("refund_no"),
        )
    if any(item.status == DEAD for item in items):
        return (
            "handed_off",
            "A support specialist will review your request and get back to you shortly.",
            None,
        )
    return outcome, reply, refund_no


def _view_dict(view: TicketView) -> dict[str, Any]:
    return asdict(view)
