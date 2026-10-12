"""M7 tests: masking, traced spans, outbox draining, parking to a human queue and the write path
during an order-system outage. The order system is a fake that fails on command."""

from dataclasses import replace
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from test_policy_m3 import MemoryPolicyStore, corpus, index_with
from test_workflow_m5 import CALM_SMALL, NOW, FakeOrders, FakeTriage, order_json, ticket

from shopsense_api.adapters.workflow.langgraph_ticket import build_graph
from shopsense_api.adapters.workflow.runner import TicketRunner
from shopsense_api.adapters.workflow.tracing import traced
from shopsense_api.application.ports.outbox import DEAD, DONE, PENDING, OutboxItem
from shopsense_api.application.ports.tracing import TraceEvent
from shopsense_api.application.use_cases.decide_return import DecideReturn
from shopsense_api.application.use_cases.drain_outbox import DrainOutbox
from shopsense_api.application.workflow.flow import TicketFlow
from shopsense_api.domain.exceptions import OrderToolError
from shopsense_api.domain.guardrails.masking import mask
from shopsense_api.domain.ticket.enums import IssueType


class InMemoryOutbox:
    def __init__(self) -> None:
        self.items: dict[str, OutboxItem] = {}

    async def enqueue(self, item: OutboxItem) -> None:
        self.items.setdefault(item.key, item)

    async def get(self, key: str) -> OutboxItem | None:
        return self.items.get(key)

    async def pending(self, limit: int) -> list[OutboxItem]:
        return [i for i in self.items.values() if i.status == PENDING][:limit]

    async def for_ticket(self, ticket_id: str) -> list[OutboxItem]:
        return [i for i in self.items.values() if i.ticket_id == ticket_id]

    async def update(self, item: OutboxItem) -> None:
        self.items[item.key] = item


class FlakyOrders(FakeOrders):
    """Fails the next `fail_reads` reads and `fail_writes` writes with a retryable error."""

    def __init__(self, orders: dict[str, dict[str, Any]]) -> None:
        super().__init__(orders)
        self.fail_reads = 0
        self.fail_writes = 0

    async def get_order(self, customer_id: str, order_no: str) -> dict[str, Any]:
        if self.fail_reads > 0:
            self.fail_reads -= 1
            raise OrderToolError("ORDER_SYSTEM_UNAVAILABLE", "down", retryable=True)
        return await super().get_order(customer_id, order_no)

    async def request_refund(
        self,
        customer_id: str,
        order_no: str,
        item_sku: str,
        amount_paise: int,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if self.fail_writes > 0:
            self.fail_writes -= 1
            raise OrderToolError("ORDER_SYSTEM_UNAVAILABLE", "down", retryable=True)
        return await super().request_refund(
            customer_id, order_no, item_sku, amount_paise, reason, idempotency_key
        )


async def _flow_graph(support: Any, orders: FlakyOrders, outbox: InMemoryOutbox) -> TicketRunner:
    store = MemoryPolicyStore()
    docs = corpus()
    store.docs = {d.doc_id: d for d in docs}
    index = await index_with(docs)
    hashes = {s.chunk_id: s.content_hash for d in docs for s in d.sections}
    decide = DecideReturn(store, index, hashes)
    flow = TicketFlow(
        FakeTriage(support),
        orders,
        decide,
        clock=lambda: NOW,
        outbox=outbox,
        drainer=DrainOutbox(outbox, orders),
    )
    return TicketRunner(build_graph(flow, MemorySaver()), outbox)


# --- masking -----------------------------------------------------------------------------


def test_masks_contact_and_payment_details() -> None:
    text = "mail priya.s@example.in, call 9876543210, card 4111 1111 1111 1111, PAN ABCDE1234F"
    masked = mask(text)
    assert "priya.s@example.in" not in masked
    assert "9876543210" not in masked
    assert "4111" not in masked
    assert "ABCDE1234F" not in masked
    assert "[email]" in masked
    assert "[phone]" in masked
    assert "[number]" in masked


def test_order_numbers_and_amounts_are_not_masked() -> None:
    assert mask("refund ORD-100002 of 1499") == "refund ORD-100002 of 1499"


# --- traced spans ------------------------------------------------------------------------


class ListTracer:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    async def record(self, event: TraceEvent) -> None:
        self.events.append(event)


class BrokenTracer:
    async def record(self, event: TraceEvent) -> None:
        raise RuntimeError("sink down")


async def test_span_records_masked_input_and_the_outcome() -> None:
    tracer = ListTracer()

    async def node(state: Any) -> dict[str, Any]:
        return {"reply": "ok for priya.s@example.in"}

    run = traced("respond", node, tracer)
    await run({"ticket_id": "TKT-1", "message": "mail 9876543210"})
    [event] = tracer.events
    assert event.trace_id == "TKT-1"
    assert event.status == "ok"
    assert "9876543210" not in event.input["message"]
    assert "priya.s@example.in" not in event.output["reply"]


async def test_node_errors_are_recorded_and_reraised() -> None:
    tracer = ListTracer()

    async def node(state: Any) -> dict[str, Any]:
        raise OrderToolError("NOT_ALLOWED", "nope")

    run = traced("execute_auto", node, tracer)
    try:
        await run({"ticket_id": "TKT-2"})
    except OrderToolError:
        pass
    else:
        raise AssertionError("the error must propagate")
    assert tracer.events[0].status == "error"


async def test_a_failing_trace_sink_never_changes_the_result() -> None:
    async def node(state: Any) -> dict[str, Any]:
        return {"outcome": "answered"}

    run = traced("respond", node, BrokenTracer())
    assert await run({"ticket_id": "TKT-3"}) == {"outcome": "answered"}


# --- outbox ------------------------------------------------------------------------------


def _item(key: str = "k-1", approved: bool = True) -> OutboxItem:
    payload = {
        "customer_no": "C0001",
        "order_no": "ORD-100002",
        "sku": "APP-KURTA",
        "amount_paise": CALM_SMALL,
        "reason": "changed_mind",
        "approved": approved,
    }
    return OutboxItem(key=key, ticket_id="TKT-O", action="refund", payload=payload)


async def test_pending_refund_is_sent_and_settled() -> None:
    orders = FlakyOrders({"ORD-100002": order_json()})
    outbox = InMemoryOutbox()
    await outbox.enqueue(_item())
    settled = await DrainOutbox(outbox, orders).drain_item(_item())
    assert settled.status == DONE
    assert settled.result["status"] == "approved"


async def test_retryable_failure_stays_pending_until_the_system_recovers() -> None:
    orders = FlakyOrders({"ORD-100002": order_json()})
    orders.fail_writes = 1
    outbox = InMemoryOutbox()
    await outbox.enqueue(_item())
    drainer = DrainOutbox(outbox, orders)
    first = await drainer.drain_item(_item())
    assert first.status == PENDING
    assert first.attempts == 1
    second = await drainer.drain_pending()
    assert [i.status for i in second] == [DONE]


async def test_non_retryable_refusal_goes_dead_and_is_not_retried() -> None:
    class Refusing(FlakyOrders):
        async def request_refund(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise OrderToolError("VALIDATION_ERROR", "amount above paid", retryable=False)

    orders = Refusing({"ORD-100002": order_json()})
    settled = await DrainOutbox(InMemoryOutbox(), orders).drain_item(_item())
    assert settled.status == DEAD


async def test_decision_that_already_settled_is_done_not_dead() -> None:
    class LostResponse(FlakyOrders):
        async def decide_refund(
            self, refund_no: str, approve: bool, grant: str | None = None
        ) -> dict[str, Any]:
            raise OrderToolError("NOT_ALLOWED", "already processed")

        async def get_refund_status(self, customer_id: str, order_no: str) -> list[dict[str, Any]]:
            return [{"refund_no": "RF-9", "status": "processed"}]

        async def request_refund(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            return {"refund_no": "RF-9", "status": "pending_approval"}

    settled = await DrainOutbox(InMemoryOutbox(), LostResponse({})).drain_item(_item(approved=True))
    assert settled.status == DONE


async def test_enqueue_is_idempotent_on_the_key() -> None:
    outbox = InMemoryOutbox()
    await outbox.enqueue(_item("same"))
    await outbox.enqueue(replace(_item("same"), attempts=5))
    assert outbox.items["same"].attempts == 0


# --- the workflow during an outage -------------------------------------------------------


async def test_outage_on_lookup_parks_the_ticket_for_a_human() -> None:
    orders = FlakyOrders({"ORD-100002": order_json()})
    orders.fail_reads = 99
    runner = await _flow_graph(ticket(), orders, InMemoryOutbox())
    view = await runner.start("TKT-P1", "C0001", "Refund ORD-100002")
    assert view.outcome == "parked_human_queue"
    assert orders.writes == []


async def test_approved_refund_during_an_outage_is_queued_then_settled() -> None:
    orders = FlakyOrders({"ORD-100002": order_json()})
    orders.fail_writes = 99
    outbox = InMemoryOutbox()
    runner = await _flow_graph(ticket(), orders, outbox)
    view = await runner.start("TKT-Q1", "C0001", "The kurta ORD-100002 is too tight, refund it.")
    assert view.outcome == "queued_for_retry"
    [pending] = [i for i in outbox.items.values() if i.status == PENDING]
    orders.fail_writes = 0
    await DrainOutbox(outbox, orders).drain_item(pending)
    assert outbox.items[pending.key].status == DONE
    assert len(orders.writes) == 1


async def test_outbox_path_for_an_undisturbed_refund_resolves_at_once() -> None:
    orders = FlakyOrders({"ORD-100002": order_json()})
    outbox = InMemoryOutbox()
    runner = await _flow_graph(ticket(issue=IssueType.REFUND_REQUEST), orders, outbox)
    view = await runner.start("TKT-R1", "C0001", "Refund the kurta ORD-100002")
    assert view.outcome == "resolved"
    assert [i.status for i in outbox.items.values()] == [DONE]


async def test_a_queued_ticket_reads_its_settlement_from_the_outbox() -> None:
    orders = FlakyOrders({"ORD-100002": order_json()})
    orders.fail_writes = 99
    outbox = InMemoryOutbox()
    runner = await _flow_graph(ticket(), orders, outbox)
    await runner.start("TKT-V1", "C0001", "The kurta ORD-100002 is too tight, refund it.")
    assert (await runner.view("TKT-V1")).outcome == "queued_for_retry"
    orders.fail_writes = 0
    [pending] = [i for i in outbox.items.values() if i.status == PENDING]
    await DrainOutbox(outbox, orders).drain_item(pending)
    view = await runner.view("TKT-V1")
    assert view.outcome == "resolved"
    assert "1,499" in (view.reply or "")
