"""Span per workflow node (M7-1). Tracing never changes a ticket's outcome: a failed trace write
is dropped, and a node error is recorded and re-raised unchanged."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import wraps
from time import perf_counter
from typing import Any

from langgraph.errors import GraphInterrupt

from shopsense_api.application.ports.tracing import TraceEvent, Tracer
from shopsense_api.application.workflow.state import TicketState
from shopsense_api.domain.guardrails.masking import mask

Node = Callable[[TicketState], Awaitable[dict[str, Any]]]
TEXT_OUTPUT_KEYS = frozenset({"reply", "reason", "summary"})


def traced(name: str, node: Node, tracer: Tracer) -> Node:
    @wraps(node)
    async def run(state: TicketState) -> dict[str, Any]:
        started = datetime.now(UTC)
        clock = perf_counter()
        out: dict[str, Any] = {}
        status, error = "ok", None
        try:
            out = await node(state)
            return out
        except GraphInterrupt:
            status = "paused"  # waiting for a reviewer: a normal stop, not an error
            raise
        except Exception as exc:
            status, error = "error", mask(str(exc))[:300]
            raise
        finally:
            event = TraceEvent(
                trace_id=str(state.get("ticket_id", "unknown")),
                name=name,
                started_at=started.isoformat(),
                duration_ms=round((perf_counter() - clock) * 1000, 1),
                status=status,
                input=_input(state),
                output=_output(out),
                error=error,
            )
            await _safe_record(tracer, event)

    return run


def _input(state: TicketState) -> dict[str, Any]:
    return {
        "channel": state.get("channel"),
        "route": state.get("route"),
        "outcome": state.get("outcome"),
        "message": mask(str(state.get("message", "")))[:200],
    }


def _output(out: dict[str, Any]) -> dict[str, Any]:
    shown: dict[str, Any] = {}
    for key, value in out.items():
        if key in TEXT_OUTPUT_KEYS:
            shown[key] = mask(str(value))[:200]
        elif isinstance(value, (str, int, float, bool)) or value is None:
            shown[key] = value
        else:
            shown[key] = type(value).__name__
    return shown


async def _safe_record(tracer: Tracer, event: TraceEvent) -> None:
    try:
        await tracer.record(event)
    except Exception:
        return
