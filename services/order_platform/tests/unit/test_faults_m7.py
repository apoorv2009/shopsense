"""M7 fault-injection tests for the Order Platform: admin-only, injected errors on /v1 only, and
faults that expire by themselves."""

import random
from dataclasses import replace
from typing import Any

from fastapi.testclient import TestClient
from test_use_cases_and_api import setup

from order_platform.adapters.http.app import create_app
from order_platform.adapters.http.faults import FaultState

TOKEN = "admin-test-token"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _client(token: str | None = TOKEN) -> tuple[TestClient, FaultState, Clock]:
    services, _ = setup()
    clock = Clock()
    faults = FaultState(clock=clock, rng=_Always())
    services = replace(services, faults=faults, admin_token=token)
    return TestClient(create_app(services)), faults, clock


class _Always(random.Random):
    """A deterministic sampler that always fails when the rate is 1.0."""

    def random(self) -> float:
        return 0.0


def _admin(client: TestClient, token: str = TOKEN) -> Any:
    return client, {"X-Admin-Token": token}


def test_admin_routes_do_not_exist_without_a_token() -> None:
    services, _ = setup()
    client = TestClient(create_app(services))
    assert client.get("/admin/faults", headers={"X-Admin-Token": "x"}).status_code == 404


def test_wrong_admin_token_is_refused() -> None:
    client, _, _ = _client()
    response = client.get("/admin/faults", headers={"X-Admin-Token": "wrong"})
    assert response.status_code == 404


def test_injected_error_hits_the_api_but_not_health() -> None:
    client, _, _ = _client()
    set_fault = client.post(
        "/admin/faults",
        json={"mode": "error", "rate": 1.0, "duration_s": 60},
        headers={"X-Admin-Token": TOKEN},
    )
    assert set_fault.status_code == 200
    api = client.get("/v1/orders", headers={"X-Customer-Id": "C0001"})
    assert api.status_code == 503
    assert api.json() == {
        "code": "ORDER_SYSTEM_UNAVAILABLE",
        "message": "injected fault",
        "retryable": True,
    }
    assert client.get("/health/live").status_code == 200


def test_clearing_the_fault_restores_the_api() -> None:
    client, _, _ = _client()
    headers = {"X-Admin-Token": TOKEN}
    client.post("/admin/faults", json={"mode": "error", "rate": 1.0}, headers=headers)
    client.delete("/admin/faults", headers=headers)
    assert client.get("/v1/orders", headers={"X-Customer-Id": "C0001"}).status_code == 200


def test_fault_expires_on_its_own() -> None:
    client, faults, clock = _client()
    headers = {"X-Admin-Token": TOKEN}
    client.post(
        "/admin/faults", json={"mode": "error", "rate": 1.0, "duration_s": 30}, headers=headers
    )
    clock.now += 31
    assert faults.current() is None
    assert client.get("/v1/orders", headers={"X-Customer-Id": "C0001"}).status_code == 200


def test_fault_duration_is_bounded() -> None:
    client, _, _ = _client()
    response = client.post(
        "/admin/faults",
        json={"mode": "error", "rate": 1.0, "duration_s": 10_000},
        headers={"X-Admin-Token": TOKEN},
    )
    assert response.status_code == 422
