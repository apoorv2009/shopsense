"""M7 resilience evaluation: a scripted outage against the live Order Platform and MCP server.

Scenarios, in order:
  A. Transient errors (50%): retries recover most reads.
  B. Sustained outage (100%): the circuit breaker opens; calls fail fast after that.
  C. A ticket during the outage: parked for a human, not answered wrongly.
  D. An approved refund during the outage: queued in the outbox, then settled exactly once.

Gates: the breaker opens; the parked ticket is parked; the approved refund is queued during the
outage and reaches the order system exactly once; no approved action is lost (outbox empty)."""

import asyncio
import time
from pathlib import Path
from typing import Any

import httpx

from shopsense_api.application.use_cases.drain_outbox import DrainOutbox
from shopsense_api.domain.exceptions import OrderToolError
from shopsense_api.entrypoints.composition import Container

OUTAGE_S = 60
ADMIN_TOKEN_ENV = "ORDER_PLATFORM_ADMIN_TOKEN"  # noqa: S105 - the name of the variable, not a secret


async def set_fault(
    admin: httpx.AsyncClient, token: str, mode: str, rate: float, seconds: int
) -> None:
    response = await admin.post(
        "/admin/faults",
        json={"mode": mode, "rate": rate, "duration_s": seconds},
        headers={"X-Admin-Token": token},
    )
    response.raise_for_status()


async def clear_fault(admin: httpx.AsyncClient, token: str) -> None:
    await admin.delete("/admin/faults", headers={"X-Admin-Token": token})


async def breaker(mcp: httpx.AsyncClient) -> dict[str, Any]:
    return dict((await mcp.get("/health/breaker")).json())


async def recover(app: Container, mcp: httpx.AsyncClient, timeout_s: float = 60.0) -> bool:
    """Wait until the order path answers again (the breaker closes on a successful probe)."""
    tools = app.order_tools()
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            await tools.get_order("C0001", "ORD-100002")
            return bool((await breaker(mcp))["state"] == "closed")
        except OrderToolError:
            await asyncio.sleep(2.0)
    return False


async def scenario_transient(app: Container) -> dict[str, Any]:
    tools = app.order_tools()
    outcomes: list[str] = []
    for _ in range(10):
        try:
            await tools.get_order("C0001", "ORD-100002")
            outcomes.append("ok")
        except OrderToolError as exc:
            outcomes.append(exc.code)
    return {"reads": len(outcomes), "ok": outcomes.count("ok"), "outcomes": outcomes}


async def scenario_outage(app: Container, mcp: httpx.AsyncClient) -> dict[str, Any]:
    tools = app.order_tools()
    outcomes: list[str] = []
    for _ in range(4):
        try:
            await tools.get_order("C0001", "ORD-100002")
            outcomes.append("ok")
        except OrderToolError as exc:
            outcomes.append(exc.message if exc.code == "ORDER_SYSTEM_UNAVAILABLE" else exc.code)
    state = await breaker(mcp)
    return {"outcomes": outcomes, "breaker": state, "breaker_opened": state["trips"] >= 1}


async def scenario_parked(runner: Any) -> dict[str, Any]:
    view = await runner.start("TKT-M7-PARK", "C0002", "Please refund ORD-100003, it is dead.")
    return {"outcome": view.outcome, "parked": view.outcome == "parked_human_queue"}


async def drain_until_settled(
    drainer: DrainOutbox, outbox: Any, timeout_s: float
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        await drainer.drain_pending()
        if not await outbox.pending(10):
            break
        await asyncio.sleep(3.0)
    items = await outbox.pending(10)
    return {"pending_left": len(items)}


async def run_resilience(
    app: Container,
    runner: Any,
    admin_url: str,
    admin_token: str,
    mcp_url: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    outbox = app.outbox_store()
    tools = app.order_tools()
    drainer = DrainOutbox(outbox, tools)
    async with (
        httpx.AsyncClient(base_url=admin_url, timeout=10) as admin,
        httpx.AsyncClient(base_url=mcp_url, timeout=10) as mcp,
    ):
        # The approval request is created before the outage, so it can be decided during it
        await runner.start(
            "TKT-M7-APPROVE",
            "C0001",
            "Please refund ORD-100002, it is too tight.",
            "email",
        )
        await set_fault(admin, admin_token, "error", 0.5, 15)
        result["A_transient"] = await scenario_transient(app)
        await clear_fault(admin, admin_token)
        result["A_recovered"] = await recover(app, mcp)

        await set_fault(admin, admin_token, "error", 1.0, OUTAGE_S)
        started = time.monotonic()
        result["B_outage"] = await scenario_outage(app, mcp)
        result["C_parked"] = await scenario_parked(runner)
        decided = await runner.resume("TKT-M7-APPROVE", approve=True, reviewer="reviewer-m7")
        result["D_approved_during_outage"] = {"outcome": decided.outcome}
        result["D_queued"] = decided.outcome == "queued_for_retry"
        remaining = OUTAGE_S - (time.monotonic() - started)
        await asyncio.sleep(max(remaining + 1, 0))
        result["D_drain"] = await drain_until_settled(drainer, outbox, timeout_s=120)
        await recover(app, mcp)
        result["breaker_after"] = await breaker(mcp)

    order = await tools.get_order("C0001", "ORD-100002")
    refunded = sum(int(i["refunded_paise"]) for i in order["items"])
    result["D_refunded_paise"] = refunded
    result["D_refunded_once"] = refunded == int(order["items"][0]["paid_paise"])
    result["gates"] = {
        "breaker_opened": bool(result["B_outage"]["breaker_opened"]),
        "ticket_parked": bool(result["C_parked"]["parked"]),
        "approved_refund_queued": bool(result["D_queued"]),
        "approved_refund_settled_once": bool(result["D_refunded_once"]),
        "no_approved_action_lost": result["D_drain"]["pending_left"] == 0,
    }
    result["passed"] = all(result["gates"].values())
    return result


def trace_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.read_text(encoding="utf-8").splitlines())
