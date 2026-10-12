"""Ports implemented by adapters (database, clock, ids)."""

from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Any, Protocol, Self

from order_platform.domain.model import Order, Refund, Replacement


@dataclass(frozen=True, slots=True)
class StoredResponse:
    request_hash: str
    body: dict[str, Any]


class OrderRepository(Protocol):
    async def list_for_customer(self, customer_no: str, limit: int) -> list[Order]: ...

    async def get(
        self, customer_no: str, order_no: str, *, for_update: bool = False
    ) -> Order | None:
        """Return the order only if it belongs to the customer; lock its items if for_update."""
        ...

    async def add_refund(self, refund: Refund) -> None:
        """Persist the refund; approved refunds also increase the item's refunded amount."""
        ...

    async def add_replacement(self, replacement: Replacement) -> None: ...

    async def refund_scope(self, refund_no: str) -> tuple[str, str, int]:
        """Order number, item SKU and amount of a refund (for grant checks)."""
        ...

    async def decide_refund(self, refund_no: str, approve: bool) -> Refund:
        """Settle a pending refund: approve (processed, counted against the item) or reject."""
        ...


class IdempotencyStore(Protocol):
    async def get(self, key: str) -> StoredResponse | None: ...

    async def save(self, key: str, request_hash: str, body: dict[str, Any]) -> None: ...


class UnitOfWork(Protocol):
    @property
    def orders(self) -> OrderRepository: ...

    @property
    def idempotency(self) -> IdempotencyStore: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> UnitOfWork: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdGenerator(Protocol):
    def new(self, prefix: str) -> str: ...
