"""LangGraph adapter for the ticket workflow (M5; LLD-1: LangGraph is an adapter, not the domain).

Graph: triage -> lookup -> assess -> (auto | approval interrupt | reply/hand-off) -> respond.
The approval node calls `interrupt()`; the run pauses with a checkpoint until a reviewer
resumes it. Every write lives in the flow's execute steps, which only the risk gate can reach."""

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from shopsense_api.adapters.workflow.tracing import Node, traced
from shopsense_api.application.ports.tracing import Tracer
from shopsense_api.application.workflow.flow import TicketFlow
from shopsense_api.application.workflow.state import TicketState


def build_graph(
    flow: TicketFlow, checkpointer: BaseCheckpointSaver[Any], tracer: Tracer | None = None
) -> Any:
    def node(name: str, fn: Node) -> Any:
        # LangGraph's node overloads are narrower than our awaitable alias; the callable is the same
        return traced(name, fn, tracer) if tracer is not None else fn

    graph: StateGraph[TicketState] = StateGraph(TicketState)
    graph.add_node("triage", node("triage", flow.triage_step))
    graph.add_node("lookup", node("lookup", flow.lookup_step))
    graph.add_node("advise", node("advise", flow.advise_step))
    graph.add_node("assess", node("assess", flow.assess_step))
    graph.add_node("review", node("review", flow.review_step))
    graph.add_node("execute_auto", node("execute_auto", flow.execute_auto))
    graph.add_node("approval", node("approval", _approval))
    graph.add_node("execute_approved", node("execute_approved", flow.execute_approved))
    graph.add_node("respond", node("respond", flow.respond_step))
    graph.add_edge(START, "triage")
    graph.add_conditional_edges("triage", _after_triage, {"lookup": "lookup", "respond": "respond"})
    graph.add_conditional_edges("lookup", _after_lookup, {"advise": "advise", "respond": "respond"})
    graph.add_edge("advise", "assess")
    graph.add_conditional_edges(
        "assess",
        _after_assess,
        {"auto": "execute_auto", "review": "review", "respond": "respond"},
    )
    graph.add_conditional_edges(
        "review", _after_review, {"approval": "approval", "respond": "respond"}
    )
    graph.add_edge("execute_auto", "respond")
    graph.add_edge("approval", "execute_approved")
    graph.add_edge("execute_approved", "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer)


def _after_triage(state: TicketState) -> str:
    return "respond" if state.get("outcome") else "lookup"


def _after_lookup(state: TicketState) -> str:
    return "respond" if state.get("outcome") else "advise"


def _after_assess(state: TicketState) -> str:
    route = state.get("route")
    if route == "auto":
        return "auto"
    if route in ("approval", "human"):
        return "review"
    return "respond"


def _after_review(state: TicketState) -> str:
    return "approval" if state.get("route") == "approval" else "respond"


async def _approval(state: TicketState) -> dict[str, Any]:
    decision = interrupt(
        {
            "ticket_id": state["ticket_id"],
            "order_no": state.get("order_no"),
            "sku": state.get("sku"),
            "amount_paise": state.get("amount_paise"),
            "reasons": state.get("reasons", []),
            "brief": state.get("brief"),
        }
    )
    return {"decision": decision}
