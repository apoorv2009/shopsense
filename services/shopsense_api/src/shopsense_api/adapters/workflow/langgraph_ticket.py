"""LangGraph adapter for the ticket workflow (M5; LLD-1: LangGraph is an adapter, not the domain).

Graph: triage -> lookup -> assess -> (auto | approval interrupt | reply/hand-off) -> respond.
The approval node calls `interrupt()`; the run pauses with a checkpoint until a reviewer
resumes it. Every write lives in the flow's execute steps, which only the risk gate can reach."""

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from shopsense_api.application.workflow.flow import TicketFlow
from shopsense_api.application.workflow.state import TicketState


def build_graph(flow: TicketFlow, checkpointer: BaseCheckpointSaver[Any]) -> Any:
    graph: StateGraph[TicketState] = StateGraph(TicketState)
    graph.add_node("triage", flow.triage_step)
    graph.add_node("lookup", flow.lookup_step)
    graph.add_node("assess", flow.assess_step)
    graph.add_node("execute_auto", flow.execute_auto)
    graph.add_node("approval", _approval)
    graph.add_node("execute_approved", flow.execute_approved)
    graph.add_node("respond", flow.respond_step)
    graph.add_edge(START, "triage")
    graph.add_edge("triage", "lookup")
    graph.add_conditional_edges("lookup", _after_lookup, {"assess": "assess", "respond": "respond"})
    graph.add_conditional_edges(
        "assess",
        _after_assess,
        {"auto": "execute_auto", "approval": "approval", "respond": "respond"},
    )
    graph.add_edge("execute_auto", "respond")
    graph.add_edge("approval", "execute_approved")
    graph.add_edge("execute_approved", "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer)


def _after_lookup(state: TicketState) -> str:
    return "respond" if state.get("outcome") else "assess"


def _after_assess(state: TicketState) -> str:
    route = state.get("route")
    if route in ("auto", "approval"):
        return route
    return "respond"


async def _approval(state: TicketState) -> dict[str, Any]:
    decision = interrupt(
        {
            "ticket_id": state["ticket_id"],
            "order_no": state.get("order_no"),
            "sku": state.get("sku"),
            "amount_paise": state.get("amount_paise"),
            "reasons": state.get("reasons", []),
        }
    )
    return {"decision": decision}
