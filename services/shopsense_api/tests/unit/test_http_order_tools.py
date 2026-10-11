import httpx
import pytest

from shopsense_api.adapters.orders.http_order_tools import HttpOrderTools
from shopsense_api.domain.exceptions import OrderToolError


def tools(handler: httpx.MockTransport) -> HttpOrderTools:
    return HttpOrderTools(
        httpx.AsyncClient(transport=handler, base_url="http://op.test"), backoff_s=0
    )


async def test_sends_identity_and_idempotency_headers() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201, json={"refund_no": "RF-1", "status": "approved"})

    result = await tools(httpx.MockTransport(handle)).request_refund(
        "C0001", "ORD-100002", "APP-KURTA", 149_900, "size_issue", "key-123456789"
    )
    assert result["status"] == "approved"
    assert seen[0].headers["X-Customer-Id"] == "C0001"
    assert seen[0].headers["Idempotency-Key"] == "key-123456789"
    assert seen[0].url.path == "/v1/refunds"


async def test_structured_error_body_becomes_order_tool_error() -> None:
    body = {"code": "NOT_FOUND", "message": "order ORD-1 not found", "retryable": False}
    transport = httpx.MockTransport(lambda _: httpx.Response(404, json=body))
    with pytest.raises(OrderToolError) as err:
        await tools(transport).get_order("C0001", "ORD-100001")
    assert err.value.code == "NOT_FOUND"
    assert not err.value.retryable


async def test_server_errors_and_outages_are_retryable() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(503, text="busy"))
    with pytest.raises(OrderToolError) as err:
        await tools(transport).track_shipment("C0001", "ORD-100006")
    assert err.value.code == "ORDER_SYSTEM_UNAVAILABLE"
    assert err.value.retryable

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(OrderToolError) as err2:
        await tools(httpx.MockTransport(down)).list_my_orders("C0001", 5)
    assert err2.value.retryable


async def test_write_retries_with_same_idempotency_key_after_timeout() -> None:
    keys: list[str] = []

    def flaky(request: httpx.Request) -> httpx.Response:
        keys.append(request.headers["Idempotency-Key"])
        if len(keys) == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(201, json={"refund_no": "RF-1", "status": "approved"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(flaky), base_url="http://op.test")
    result = await HttpOrderTools(client, backoff_s=0).request_refund(
        "C0001", "ORD-100002", "APP-KURTA", 149_900, "size_issue", "key-123456789"
    )
    assert result["status"] == "approved"
    assert keys == ["key-123456789", "key-123456789"]


async def test_non_retryable_errors_are_not_retried() -> None:
    calls: list[int] = []

    def reject(_: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(
            409, json={"code": "NOT_ALLOWED", "message": "no", "retryable": False}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(reject), base_url="http://op.test")
    with pytest.raises(OrderToolError):
        await HttpOrderTools(client, backoff_s=0).get_order("C0001", "ORD-100002")
    assert len(calls) == 1
