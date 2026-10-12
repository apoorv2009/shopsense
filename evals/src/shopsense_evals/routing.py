"""M5 routing evaluation: does each ticket take the expected route, and is every write behind the
risk gate? Each case runs the real workflow (live triage, live Order Platform) with an
in-memory checkpointer; every order write is counted by a wrapper around the order tools.

Gate: a case expecting zero writes must produce zero writes, which covers pauses, hand-offs,
replies and unresolved requests. The gate is zero-tolerance."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from shopsense_api.application.ports.orders import OrderTools
from shopsense_api.domain.policy.model import PolicyDocument
from shopsense_api.entrypoints.composition import Container


@dataclass(frozen=True, slots=True)
class RoutingCase:
    case_id: str
    note: str
    customer_no: str
    message: str
    expect_outcome: str
    expect_route: str | None
    expect_writes: int


class CountingOrders:
    """Delegates every call and counts the writes that change money or orders."""

    def __init__(self, inner: OrderTools) -> None:
        self._inner = inner
        self.writes = 0

    async def list_my_orders(self, customer_id: str, limit: int) -> list[dict[str, Any]]:
        return await self._inner.list_my_orders(customer_id, limit)

    async def get_order(self, customer_id: str, order_no: str) -> dict[str, Any]:
        return await self._inner.get_order(customer_id, order_no)

    async def track_shipment(self, customer_id: str, order_no: str) -> dict[str, Any]:
        return await self._inner.track_shipment(customer_id, order_no)

    async def get_refund_status(self, customer_id: str, order_no: str) -> list[dict[str, Any]]:
        return await self._inner.get_refund_status(customer_id, order_no)

    async def calculate_refund(
        self, customer_id: str, order_no: str, item_sku: str, reason: str
    ) -> dict[str, Any]:
        return await self._inner.calculate_refund(customer_id, order_no, item_sku, reason)

    async def request_refund(
        self,
        customer_id: str,
        order_no: str,
        item_sku: str,
        amount_paise: int,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.writes += 1
        return await self._inner.request_refund(
            customer_id, order_no, item_sku, amount_paise, reason, idempotency_key
        )

    async def decide_refund(
        self, refund_no: str, approve: bool, grant: str | None = None
    ) -> dict[str, Any]:
        self.writes += 1
        return await self._inner.decide_refund(refund_no, approve, grant)

    async def request_replacement(
        self, customer_id: str, order_no: str, item_sku: str, reason: str, idempotency_key: str
    ) -> dict[str, Any]:
        self.writes += 1
        return await self._inner.request_replacement(
            customer_id, order_no, item_sku, reason, idempotency_key
        )


def load_routing(path: Path) -> list[RoutingCase]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        row = json.loads(line)
        e = row["expect"]
        out.append(
            RoutingCase(
                row["id"],
                row["note"],
                row["customer_no"],
                row["message"],
                e["outcome"],
                e["route"],
                e["writes"],
            )
        )
    return out


async def run_routing(
    app: Container, corpus: list[PolicyDocument], cases: list[RoutingCase], run: str
) -> list[dict[str, Any]]:
    results = []
    for case in cases:
        counting = CountingOrders(app.order_tools())
        runner = app.ticket_runner(corpus, MemorySaver(), orders=counting)
        ticket_id = f"TKT-{case.case_id}-{run}"
        view = await runner.start(ticket_id, case.customer_no, case.message)
        outcome_ok = view.outcome == case.expect_outcome
        route_ok = view.route == case.expect_route or (
            case.expect_route is None and view.route is None
        )
        writes_ok = counting.writes == case.expect_writes
        results.append(
            {
                "id": case.case_id,
                "note": case.note,
                "expected": [case.expect_outcome, case.expect_route, case.expect_writes],
                "got": [view.outcome, view.route, counting.writes],
                "correct": outcome_ok and route_ok and writes_ok,
                "gate_ok": counting.writes == 0 or case.expect_writes > 0,
                "reply": view.reply,
            }
        )
    return results
