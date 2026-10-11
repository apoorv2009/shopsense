"""Order Platform against a real PostgreSQL (Docker locally, service container in CI).

Set ORDER_PLATFORM_TEST_DATABASE_URL, e.g.
postgresql+asyncpg://shopsense:shopsense@localhost:5432/order_platform_test
"""

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from order_platform.adapters.http.app import Services
from order_platform.application.use_cases import RefundCommand, ReplacementCommand
from order_platform.domain.errors import NotAllowedError, NotFoundError
from order_platform.domain.model import RefundReason
from order_platform.entrypoints.composition import build_services
from order_platform.entrypoints.seed import seed

URL = os.environ.get("ORDER_PLATFORM_TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not URL, reason="ORDER_PLATFORM_TEST_DATABASE_URL not set"),
]
ANCHOR = date(2026, 10, 7)


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    assert URL
    engine = create_async_engine(URL)
    await seed(engine, ANCHOR, reset=True)
    yield engine
    await engine.dispose()


@pytest.fixture
def services(engine: AsyncEngine) -> Services:
    return build_services(engine)


def refund(key: str, **kw: object) -> RefundCommand:
    base: dict[str, object] = {
        "customer_no": "C0001",
        "order_no": "ORD-100002",
        "item_sku": "APP-KURTA",
        "amount_paise": 149_900,
        "reason": RefundReason.SIZE_ISSUE,
        "idempotency_key": key,
    }
    return RefundCommand(**(base | kw))  # type: ignore[arg-type]


async def test_seed_fixtures_and_ownership(services: Services) -> None:
    orders = await services.queries.list_orders("C0001", 10)
    assert {o.order_no for o in orders} >= {"ORD-100001", "ORD-100002"}
    laptop = await services.queries.get_order("C0002", "ORD-100003")
    assert laptop.items[0].paid_paise == 5_499_000
    with pytest.raises(NotFoundError):
        await services.queries.get_order("C0001", "ORD-100003")


async def test_small_refund_applies_and_replays(services: Services) -> None:
    first = await services.refunds.execute(refund("db-key-0001"))
    replay = await services.refunds.execute(refund("db-key-0001"))
    assert first == replay
    assert first["status"] == "approved"
    order = await services.queries.get_order("C0001", "ORD-100002")
    assert order.items[0].refunded_paise == 149_900
    assert len(order.refunds) == 1


async def test_large_refund_is_held_not_applied(services: Services) -> None:
    cmd = refund(
        "db-key-0002",
        customer_no="C0002",
        order_no="ORD-100003",
        item_sku="ELE-LAPTOP14",
        amount_paise=5_499_000,
        reason=RefundReason.DEFECTIVE,
    )
    body = await services.refunds.execute(cmd)
    assert body["status"] == "pending_approval"
    order = await services.queries.get_order("C0002", "ORD-100003")
    assert order.items[0].refunded_paise == 0


async def test_concurrent_full_refunds_cannot_both_succeed(services: Services) -> None:
    results = await asyncio.gather(
        services.refunds.execute(refund("race-key-0001")),
        services.refunds.execute(refund("race-key-0002")),
        return_exceptions=True,
    )
    successes = [r for r in results if isinstance(r, dict)]
    failures = [r for r in results if isinstance(r, NotAllowedError)]
    assert len(successes) == 1
    assert len(failures) == 1
    order = await services.queries.get_order("C0001", "ORD-100002")
    assert order.items[0].refunded_paise == 149_900


async def test_shipment_tracking_and_lost_parcel(services: Services) -> None:
    stuck = await services.queries.shipment("C0005", "ORD-100006")
    assert stuck.status.value == "in_transit"
    lost_quote = await services.queries.quote(
        "C0010", "ORD-100011", "ELE-POWERBANK", RefundReason.LOST_IN_TRANSIT
    )
    assert lost_quote.refundable_paise == 179_900


async def test_replacement_cap(services: Services) -> None:
    cmd = ReplacementCommand(
        "C0002", "ORD-100003", "ELE-LAPTOP14", RefundReason.DEFECTIVE, "db-key-0003"
    )
    assert (await services.replacements.execute(cmd))["status"] == "pending_approval"
