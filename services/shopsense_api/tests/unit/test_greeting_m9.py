"""Greetings get a fixed automated reply: no model call, no handoff, no memory record."""

import pytest

from shopsense_api.domain.ticket.greeting import GREETING_REPLY, is_greeting


@pytest.mark.parametrize(
    "text", ["Hello", "hi", "Hey!", "good morning", "Hi there", "namaste", "hello, support"]
)
def test_greetings_are_detected(text: str) -> None:
    assert is_greeting(text)


@pytest.mark.parametrize(
    "text",
    [
        "Hello, my order ORD-100002 arrived damaged",
        "Can I return an opened serum?",
        "hi I want a refund",
        "",
    ],
)
def test_real_messages_are_not_greetings(text: str) -> None:
    assert not is_greeting(text)


async def test_greeting_never_reaches_triage_or_memory() -> None:
    from langgraph.checkpoint.memory import MemorySaver
    from test_workflow_m5 import FakeOrders, FakeRemember

    from shopsense_api.adapters.workflow.langgraph_ticket import build_graph
    from shopsense_api.adapters.workflow.runner import TicketRunner
    from shopsense_api.application.workflow.flow import TicketFlow
    from shopsense_api.domain.exceptions import TriageFailed
    from shopsense_api.domain.policy.rules_engine import Eligibility  # noqa: F401

    class ExplodingTriage:
        async def execute(self, command: object) -> object:
            raise TriageFailed("triage must not run for a greeting")

    from test_policy_m3 import MemoryPolicyStore, corpus, index_with

    from shopsense_api.application.use_cases.decide_return import DecideReturn

    store = MemoryPolicyStore()
    docs = corpus()
    store.docs = {d.doc_id: d for d in docs}
    index = await index_with(docs)
    hashes = {s.chunk_id: s.content_hash for d in docs for s in d.sections}
    remember = FakeRemember()
    flow = TicketFlow(
        ExplodingTriage(),  # type: ignore[arg-type]
        FakeOrders({}),
        DecideReturn(store, index, hashes),
        remember=remember,
    )
    view = await TicketRunner(build_graph(flow, MemorySaver())).start("TKT-G1", "C0001", "Hello")
    assert view.reply == GREETING_REPLY
    assert view.outcome == "greeting"
    assert remember.calls == []
