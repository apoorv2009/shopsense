"""M7 resilience tests for the MCP server: circuit breaker transitions, retries and fast fail."""

import httpx
import pytest
from mcp_server.order_client import OrderClient, ToolFailureError
from mcp_server.resilience import CircuitBreaker


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_breaker_opens_after_consecutive_failures() -> None:
    breaker = CircuitBreaker(threshold=3, open_s=10, clock=Clock())
    for _ in range(2):
        breaker.record_failure()
    assert breaker.snapshot()["state"] == "closed"
    breaker.record_failure()
    assert breaker.snapshot()["state"] == "open"
    assert breaker.allow() is False


def test_breaker_half_opens_after_the_wait_and_closes_on_success() -> None:
    clock = Clock()
    breaker = CircuitBreaker(threshold=1, open_s=10, clock=clock)
    breaker.record_failure()
    clock.now = 9.9
    assert breaker.allow() is False
    clock.now = 10.0
    assert breaker.allow() is True
    assert breaker.state == "half_open"
    breaker.record_success()
    assert breaker.snapshot()["state"] == "closed"
    assert breaker.trips == 1


def test_failed_probe_reopens_the_breaker() -> None:
    clock = Clock()
    breaker = CircuitBreaker(threshold=1, open_s=5, clock=clock)
    breaker.record_failure()
    clock.now = 5.0
    breaker.allow()
    breaker.record_failure()
    assert breaker.snapshot()["state"] == "open"
    assert breaker.trips == 2


def test_success_resets_the_failure_count() -> None:
    breaker = CircuitBreaker(threshold=3, clock=Clock())
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    assert breaker.state == "closed"


def _client(handler: httpx.MockTransport, breaker: CircuitBreaker | None = None) -> OrderClient:
    http = httpx.AsyncClient(base_url="http://order.test", transport=handler)
    return OrderClient(http, breaker, backoff_s=0.0)


async def test_transient_error_is_retried_and_recovers() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, json={"code": "X", "message": "busy", "retryable": True})
        return httpx.Response(200, json={"order_no": "ORD-1"})

    result = await _client(httpx.MockTransport(handler)).get("C0001", "/v1/orders/ORD-1")
    assert result["order_no"] == "ORD-1"
    assert calls["n"] == 3


async def test_business_refusal_is_not_retried_and_does_not_trip_the_breaker() -> None:
    breaker = CircuitBreaker(threshold=1, clock=Clock())
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(404, json={"code": "NOT_FOUND", "message": "no", "retryable": False})

    with pytest.raises(ToolFailureError):
        await _client(httpx.MockTransport(handler), breaker).get("C0001", "/v1/orders/x")
    assert calls["n"] == 1
    assert breaker.snapshot()["state"] == "closed"


async def test_open_breaker_fails_fast_without_calling_the_order_system() -> None:
    clock = Clock()
    breaker = CircuitBreaker(threshold=1, open_s=60, clock=clock)
    breaker.record_failure()
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={})

    with pytest.raises(ToolFailureError, match="circuit open") as exc:
        await _client(httpx.MockTransport(handler), breaker).get("C0001", "/v1/orders")
    assert exc.value.retryable is True
    assert calls["n"] == 0


async def test_unkeyed_write_is_not_retried() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, json={"code": "X", "message": "busy", "retryable": True})

    with pytest.raises(ToolFailureError):
        await _client(httpx.MockTransport(handler)).post("C0001", "/v1/refunds", {"a": 1})
    assert calls["n"] == 1


async def test_keyed_write_is_retried_because_a_replay_is_safe() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, json={"code": "X", "message": "busy", "retryable": True})
        return httpx.Response(201, json={"refund_no": "RF-1", "status": "approved"})

    result = await _client(httpx.MockTransport(handler)).post(
        "C0001", "/v1/refunds", {"a": 1}, idempotency_key="key-00000001"
    )
    assert result["status"] == "approved"
    assert calls["n"] == 2
