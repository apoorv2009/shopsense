from typing import Any

import pytest
from fastapi.testclient import TestClient

from order_platform.adapters.http.app import Services, create_app
from order_platform.application.use_cases import (
    OrderQueries,
    RefundCommand,
    RequestRefund,
    RequestReplacement,
)
from order_platform.domain.errors import DuplicateRequestError, NotFoundError
from order_platform.domain.model import RefundReason

from memory import KURTA, CountingIds, FixedClock, MemoryIdempotency, MemoryRepo, MemoryUoW, order


def setup() -> tuple[Services, MemoryRepo]:
    repo = MemoryRepo([order(), order("ORD-100002", "C0001", KURTA, 149_900)])
    uow = MemoryUoW(repo, MemoryIdempotency())
    clock, ids = FixedClock(), CountingIds()
    services = Services(
        queries=OrderQueries(lambda: uow),
        refunds=RequestRefund(lambda: uow, clock, ids),
        replacements=RequestReplacement(lambda: uow, clock, ids),
    )
    return services, repo


def refund_cmd(**kw: Any) -> RefundCommand:
    base: dict[str, Any] = {
        "customer_no": "C0001",
        "order_no": "ORD-100002",
        "item_sku": "APP-KURTA",
        "amount_paise": 149_900,
        "reason": RefundReason.SIZE_ISSUE,
        "idempotency_key": "key-00000001",
    }
    return RefundCommand(**(base | kw))


async def test_small_refund_approved_and_applied() -> None:
    services, repo = setup()
    body = await services.refunds.execute(refund_cmd())
    assert body["status"] == "approved"
    assert repo.orders["ORD-100002"].items[0].refunded_paise == 149_900


async def test_same_key_replays_without_refunding_twice() -> None:
    services, repo = setup()
    first = await services.refunds.execute(refund_cmd())
    second = await services.refunds.execute(refund_cmd())
    assert first == second
    assert len(repo.orders["ORD-100002"].refunds) == 1


async def test_same_key_different_request_is_rejected() -> None:
    services, _ = setup()
    await services.refunds.execute(refund_cmd())
    with pytest.raises(DuplicateRequestError):
        await services.refunds.execute(refund_cmd(amount_paise=100))


async def test_large_refund_held_and_not_applied() -> None:
    services, repo = setup()
    cmd = refund_cmd(
        customer_no="C0002",
        order_no="ORD-100003",
        item_sku="ELE-LAPTOP14",
        amount_paise=5_499_000,
        reason=RefundReason.DEFECTIVE,
    )
    body = await services.refunds.execute(cmd)
    assert body["status"] == "pending_approval"
    assert repo.orders["ORD-100003"].items[0].refunded_paise == 0


async def test_other_customers_order_is_not_found() -> None:
    services, _ = setup()
    with pytest.raises(NotFoundError):
        await services.queries.get_order("C0001", "ORD-100003")


def client() -> TestClient:
    return TestClient(create_app(setup()[0]))


def test_api_requires_customer_header() -> None:
    response = client().get("/v1/orders/ORD-100002")
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_api_order_and_quote() -> None:
    c, headers = client(), {"X-Customer-Id": "C0001"}
    order_json = c.get("/v1/orders/ORD-100002", headers=headers).json()
    assert order_json["items"][0]["paid_paise"] == 149_900
    assert "email" not in str(order_json)
    quote = c.post(
        "/v1/orders/ORD-100002/refund-quote",
        json={"item_sku": "APP-KURTA", "reason": "damaged"},
        headers=headers,
    )
    assert quote.json()["refundable_paise"] == 149_900


def test_api_not_owned_returns_404_error_body() -> None:
    response = client().get("/v1/orders/ORD-100003", headers={"X-Customer-Id": "C0001"})
    assert response.status_code == 404
    assert response.json() == {
        "code": "NOT_FOUND",
        "message": "order ORD-100003 not found",
        "retryable": False,
    }


def test_api_refund_needs_idempotency_key_and_blocks_over_refund() -> None:
    c, headers = client(), {"X-Customer-Id": "C0001"}
    body = {
        "order_no": "ORD-100002",
        "item_sku": "APP-KURTA",
        "amount_paise": 999_999,
        "reason": "damaged",
    }
    assert c.post("/v1/refunds", json=body, headers=headers).status_code == 422
    over = c.post("/v1/refunds", json=body, headers=headers | {"Idempotency-Key": "abcdefgh1"})
    assert over.status_code == 409
    assert over.json()["code"] == "NOT_ALLOWED"
