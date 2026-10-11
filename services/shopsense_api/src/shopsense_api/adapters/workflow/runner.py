"""Start, inspect and resume ticket workflows by ticket ID (the LangGraph thread ID, D9a)."""

from dataclasses import dataclass, field
from typing import Any

from langgraph.types import Command

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


class TicketRunner:
    def __init__(self, graph: Any) -> None:
        self._graph = graph

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
        return TicketView(
            ticket_id=ticket_id,
            outcome=outcome,
            paused=paused,
            route=values.get("route"),
            reply=values.get("reply"),
            approval=approval,
            eligibility=values.get("eligibility"),
            rule_id=values.get("rule_id"),
            amount_paise=values.get("amount_paise"),
        )

    async def exists(self, ticket_id: str) -> bool:
        snapshot = await self._graph.aget_state(_config(ticket_id))
        return bool(snapshot.values)


def _config(ticket_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": ticket_id}}
