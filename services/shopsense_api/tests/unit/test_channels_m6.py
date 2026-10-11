"""M6 channel tests: chat and email share one workflow; email is restricted to registered senders
and refunds from email always wait for a reviewer (channel parity)."""

from fastapi.testclient import TestClient
from test_workflow_m5 import CALM_SMALL, FakeOrders, make_runner, order_json, ticket

from shopsense_api.adapters.http.channels_api import create_app
from shopsense_api.domain.policy.rules_engine import Eligibility
from shopsense_api.domain.ticket.enums import IssueType, RiskFlag, Sentiment
from shopsense_api.domain.workflow.risk import Route, assess

SENDERS = {"priya@example.in": "C0001"}


async def _client(orders: FakeOrders) -> TestClient:
    runner, _ = await make_runner(ticket(), orders)
    app = create_app()
    app.state.runner = runner
    app.state.senders = SENDERS
    return TestClient(app)


async def test_chat_calm_refund_auto_resolves_with_one_write() -> None:
    orders = FakeOrders({"ORD-100002": order_json()})
    client = await _client(orders)
    response = client.post(
        "/v1/chat/tickets",
        json={"customer_no": "C0001", "message": "The kurta ORD-100002 is too tight, refund it."},
    )
    assert response.status_code == 201
    assert response.json()["outcome"] == "resolved"
    assert orders.writes == [("request_refund", CALM_SMALL)]


async def test_email_from_a_registered_sender_refund_always_waits_for_a_reviewer() -> None:
    orders = FakeOrders({"ORD-100002": order_json()})
    client = await _client(orders)
    response = client.post(
        "/v1/channels/email/inbound",
        json={
            "from_address": "Priya@example.in",
            "subject": "Kurta too tight",
            "body": "Please refund ORD-100002.",
            "message_id": "<m-1@mail>",
        },
    )
    body = response.json()
    assert body["outcome"] == "pending_human_approval"
    assert body["route"] == "approval"
    assert "refund requested by email" in body["approval"]["reasons"]
    assert orders.writes == []


async def test_email_from_an_unregistered_sender_is_ignored() -> None:
    orders = FakeOrders({"ORD-100002": order_json()})
    client = await _client(orders)
    response = client.post(
        "/v1/channels/email/inbound",
        json={"from_address": "stranger@example.com", "subject": "refund", "message_id": "<x@y>"},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "ignored"
    assert orders.writes == []


async def test_redelivered_email_is_not_processed_twice() -> None:
    orders = FakeOrders({"ORD-100002": order_json()})
    client = await _client(orders)
    payload = {"from_address": "priya@example.in", "subject": "s", "message_id": "<dup@mail>"}
    first = client.post("/v1/channels/email/inbound", json=payload).json()
    second = client.post("/v1/channels/email/inbound", json=payload).json()
    assert first["outcome"] == "pending_human_approval"
    assert second["status"] == "duplicate"
    assert second["ticket_id"] == first["ticket_id"]


async def test_chat_and_email_reach_the_same_eligibility_and_rule() -> None:
    orders = FakeOrders({"ORD-100002": order_json()})
    client = await _client(orders)
    chat = client.post(
        "/v1/chat/tickets",
        json={"customer_no": "C0001", "message": "Refund ORD-100002 please."},
    ).json()
    email = client.post(
        "/v1/channels/email/inbound",
        json={
            "from_address": "priya@example.in",
            "subject": "refund",
            "message_id": "<p-1>",
            "body": "Refund ORD-100002 please.",
        },
    ).json()
    assert chat["eligibility"] == email["eligibility"] == "eligible"
    assert chat["rule_id"] == email["rule_id"] == "APP-RET-45"
    assert (chat["route"], email["route"]) == ("auto", "approval")


async def test_reviewer_approval_over_the_api_settles_the_email_refund() -> None:
    orders = FakeOrders({"ORD-100002": order_json()})
    client = await _client(orders)
    created = client.post(
        "/v1/channels/email/inbound",
        json={"from_address": "priya@example.in", "subject": "s", "message_id": "<r-1>"},
    ).json()
    decided = client.post(
        f"/v1/tickets/{created['ticket_id']}/decision",
        json={"approve": True, "reviewer": "reviewer-1"},
    ).json()
    assert decided["outcome"] == "resolved"
    # Under the cap the order system approves at once, so the reviewer adds no second write
    assert orders.writes == [("request_refund", CALM_SMALL)]


def test_email_rule_forces_approval_for_any_calm_refund() -> None:
    support = ticket(sentiment=Sentiment.NEUTRAL, flags=[])
    assert assess(support, Eligibility.ELIGIBLE, CALM_SMALL).route is Route.AUTO
    verdict = assess(support, Eligibility.ELIGIBLE, CALM_SMALL, channel="email")
    assert verdict.route is Route.APPROVAL


def test_email_rule_does_not_change_non_refund_or_blocked_routes() -> None:
    info = ticket(issue=IssueType.ORDER_STATUS)
    assert assess(info, Eligibility.ELIGIBLE, 0, channel="email").route is Route.REPLY
    flagged = ticket(flags=[RiskFlag.LEGAL_THREAT])
    assert assess(flagged, Eligibility.ELIGIBLE, CALM_SMALL, channel="email").route is Route.HUMAN
